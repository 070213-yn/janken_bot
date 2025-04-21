import discord
from discord.ext import commands
import random
import asyncio
from dotenv import load_dotenv
import os
from PIL import Image
from pathlib import Path

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
# osero.py と同じ階層の image フォルダを指す
IMAGE_DIR = Path(__file__).resolve().parent / "image"
BASE_IMAGE = IMAGE_DIR / "hit_board.png" 

active_games = {}
COLOR_EMOJIS = {
    "r": "<:red:1362318988365004870>",
    "y": "<:yellow:1362318962041425930>",
    "g": "<:green:1362318888817131530>",
    "b": "<:blue:1362318775990616215>",
    "p": "<:purple:1362318974792241192>",
    "w": "<:white:1362319002541490218>"
}

# 座標（画像内の配置順）
GUESS_POSITIONS = [
    (170, 376),
    (485, 376),
    (802, 376),
    (1120, 376),
]

COLOR_IMAGE_FILES = {
    "r": IMAGE_DIR / "red.png",
    "y": IMAGE_DIR / "yellow.png",
    "g": IMAGE_DIR / "green.png",
    "b": IMAGE_DIR / "blue.png",
    "p": IMAGE_DIR / "purple.png",
    "w": IMAGE_DIR / "white.png",
}

def generate_guess_image(guess) -> Path:
    """
    guess: 'rygb' or ['r','y','g','b']
    returns: Path to the generated image file
    """
    if isinstance(guess, list):
        guess_abbr = [abbr.lower() for abbr in guess]
        guess_str  = ''.join(guess_abbr)
    else:
        guess_str  = str(guess).lower()
        guess_abbr = list(guess_str)

    base = Image.open(BASE_IMAGE).convert("RGBA")

    icon_size = (235, 235)
    for i, abbr in enumerate(guess_abbr):
        if abbr not in COLOR_IMAGE_FILES or i >= len(GUESS_POSITIONS):
            continue
        piece = Image.open(COLOR_IMAGE_FILES[abbr]).convert("RGBA").resize(icon_size)
        cx, cy = GUESS_POSITIONS[i]
        pw, ph = piece.size
        pos = (cx - pw // 2, cy - ph // 2)
        base.paste(piece, pos, piece)

    output_path = IMAGE_DIR / f"guess_{guess_str}.png"
    base.save(output_path)

    return output_path

EMOJI_LIST = list(COLOR_EMOJIS.values())

class HitBlowGame:
    def __init__(self, ctx, players, allow_duplicates, max_turns):
        self.ctx = ctx
        self.players = players
        self.allow_duplicates = allow_duplicates
        self.max_turns = max_turns
        self.turn_index = 0
        self.turn_count = 0
        self.secret = self.generate_secret()
        self.guess_log = []
        self.running = True
        self.current_player = None

    def generate_secret(self):
        if self.allow_duplicates:
            duplicated = random.choice(EMOJI_LIST)
            others = random.sample([e for e in EMOJI_LIST if e != duplicated], 2)
            secret = [duplicated, duplicated] + others
            random.shuffle(secret)
            return secret
        else:
            return random.sample(EMOJI_LIST, 4)

    async def start(self):
        emoji_list = ' '.join(COLOR_EMOJIS[c] for c in 'rygbpw')
        abbreviation = ' '.join(f"{c}={COLOR_EMOJIS[c]}" for c in 'rygbpw')

        await self.ctx.send(
            f"🎯 ヒットアンドブロー開始！（{'色かぶり⭕' if self.allow_duplicates else '色かぶり❌'}、最大{self.max_turns}ターン）\n"
            f"使える色: {emoji_list}\n"
            f"略称: {abbreviation}\n"
            "例: `rbgy` → 実際の色で画像が送られます"
        )
        await self.next_turn()

    async def next_turn(self):
        if not self.running:
            return

        if self.turn_count >= self.max_turns:
            await self.ctx.send(f"💀 ターン数上限に達しました！\n答えは：{''.join(self.secret)}\n残念ch！")
            await self.show_results(None)
            return

        player = self.players[self.turn_index % len(self.players)]
        self.current_player = player

        remaining = self.max_turns - self.turn_count
        abbreviation = ' '.join(f"{c}={COLOR_EMOJIS[c]}" for c in 'rygbpw')
        await self.ctx.send(
            f"🌀 {player.mention} さんのターン！（残り {remaining} ターン）\n"
            f"略称: {abbreviation}"
        )

        self.turn_index += 1
        self.turn_count += 1

    async def handle_guess(self, user, message):
        if not self.running or user != self.current_player:
            return

        raw = message.content.strip().lower()
        if len(raw) != 4 or any(c not in COLOR_IMAGE_FILES for c in raw):
            return await message.channel.send("❌ 無効な入力です。r/b/g/y/p/w の略称で4文字を入力してください。")
        if not self.allow_duplicates and len(set(raw)) < 4:
            return await message.channel.send("❌ 色はかぶらせずに4つ選んでください。")

        guess = list(raw)
        hits, blows = calculate_hit_blow(self.secret, [COLOR_EMOJIS[c] for c in guess])
        self.guess_log.append((guess, hits, blows))  # ← ここ修正

        # 画像生成 → Discordに送信
        image_path = generate_guess_image(guess)
        await message.channel.send(
            content=f"🎯 {hits}ヒット {blows}ブロー",
            file=discord.File(image_path)
        )

        if hits == 4:
            await self.show_results(winner=user)
            return

        await self.next_turn()
        await self.show_history()

    async def show_results(self, winner):
        if winner:
            await self.ctx.send(f"🏆 {winner.mention} さんが正解しました！天才ちゃんねる🎉")

        if not self.guess_log:
            await self.ctx.send("📜 結果がありません。")
            return

        lines = []
        for i, (guess_abbr, hits, blows) in enumerate(self.guess_log, 1):
            emoji_guess = ''.join(COLOR_EMOJIS[c] for c in guess_abbr)
            lines.append(f"{i}. {emoji_guess} → {hits}H {blows}B")

        await self.ctx.send("📜 **最終結果：**\n" + "\n".join(lines) + "\n")

        self.running = False
        active_games.pop(self.ctx.guild.id, None)

    async def show_history(self):
        if not self.guess_log:
            await self.ctx.send("📭 まだ履歴がありません。")
            return

        lines = []
        for i, (guess_abbr, hits, blows) in enumerate(self.guess_log, 1):
            emoji_guess = ''.join(COLOR_EMOJIS[c] for c in guess_abbr)
            lines.append(f"{i}. {emoji_guess} → {hits}H {blows}B")

        await self.ctx.send("📝 **現在の履歴：**\n" + "\n".join(lines) + "\n")

    async def exit_player(self, user):
        if user in self.players:
            self.players.remove(user)
            await self.ctx.send(f"👋 {user.display_name} さんが退出しました。")
            if not self.players:
                await self.force_end()

    async def force_end(self):
        await self.ctx.send(f"🛑 ゲームが中断されました！答えは：{''.join(self.secret)}")
        await self.show_results(None)



def calculate_hit_blow(secret, guess):
    hits = sum(s == g for s, g in zip(secret, guess))
    blows = sum(min(secret.count(c), guess.count(c)) for c in set(guess)) - hits
    return hits, blows

@bot.command()
async def hit(ctx):
    if ctx.guild.id in active_games:
        return await ctx.send("🚫 ゲームが既に進行中です。")
    await ctx.send("🎮 ヒットアンドブローを始めます！色かぶりの⭕❌を選んでください：", view=ModeSelectView(ctx))

@bot.command()
async def end(ctx):
    game = active_games.get(ctx.guild.id)
    if game and game.running:
        await game.force_end()

@bot.command()
async def his(ctx):
    game = active_games.get(ctx.guild.id)
    if game and game.running:
        await game.show_history()

@bot.command()
async def exit(ctx):
    game = active_games.get(ctx.guild.id)
    if game and game.running:
        await game.exit_player(ctx.author)

@bot.command()
async def join(ctx):
    game = active_games.get(ctx.guild.id)
    # ゲーム中かどうかチェック
    if game and game.running:
        # すでに参加済みなら弾く
        if ctx.author in game.players:
            return await ctx.send("🚫 既に参加しています。")
        # 新しい人数
        new_len = len(game.players) + 1
        # 次のターンに join した人が来るよう、挿入位置を計算
        pos = game.turn_index % new_len
        game.players.insert(pos, ctx.author)
        await ctx.send(f"🎉 {ctx.author.mention} さんが途中参加しました！")
    else:
        await ctx.send("🚫 現在途中参加可能なゲームはありません。")

# UIビュー：色かぶり選択 → ターン数選択
class ModeSelectView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=10)
        self.ctx = ctx

    @discord.ui.button(label="色かぶり⭕", style=discord.ButtonStyle.success)
    async def allow_dup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_turn(interaction, True)

    @discord.ui.button(label="色かぶり❌", style=discord.ButtonStyle.primary)
    async def no_dup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ask_turn(interaction, False)

    async def ask_turn(self, interaction, allow_dup):
        await interaction.response.defer()  # ✅ 応答予約（インタラクション失敗防止）
        await interaction.message.delete()  # ✅ ボタン付きメッセージを削除
        await self.ctx.send("🎯 ターン数を選んでください：", view=TurnSelectView(self.ctx, allow_dup))  # ✅ 新規に表示

class TurnSelectView(discord.ui.View):
    def __init__(self, ctx, allow_dup):
        super().__init__(timeout=10)
        self.ctx = ctx
        self.allow_dup = allow_dup

    async def start_entry(self, interaction, max_turns):
        await self.ctx.send("📢 ヒットアンドブロ―参加者受付中！（5秒間）", view=EntryView(self.ctx, self.allow_dup, max_turns))
        await interaction.message.delete()

    @discord.ui.button(label="4ターン", style=discord.ButtonStyle.secondary)
    async def t4(self, i, b): await self.start_entry(i, 4)
    @discord.ui.button(label="5ターン", style=discord.ButtonStyle.secondary)
    async def t5(self, i, b): await self.start_entry(i, 5)
    @discord.ui.button(label="6ターン", style=discord.ButtonStyle.secondary)
    async def t6(self, i, b): await self.start_entry(i, 6)
    @discord.ui.button(label="7ターン", style=discord.ButtonStyle.secondary)
    async def t7(self, i, b): await self.start_entry(i, 7)
    @discord.ui.button(label="8ターン", style=discord.ButtonStyle.secondary)
    async def t8(self, i, b): await self.start_entry(i, 8)

class EntryView(discord.ui.View):
    def __init__(self, ctx, allow_duplicates, max_turns):
        super().__init__(timeout=5)
        self.ctx = ctx
        self.entries = set()
        self.allow_duplicates = allow_duplicates
        self.max_turns = max_turns

    @discord.ui.button(label="参加する！", style=discord.ButtonStyle.success)
    async def entry(self, interaction, b):
        self.entries.add(interaction.user)
        await interaction.response.send_message("🆗 参加登録しました", ephemeral=True)

    async def on_timeout(self):
        if len(self.entries) < 1:
            return await self.ctx.send("❌ 参加者がいませんでした。")
        players = list(self.entries)
        random.shuffle(players)
        game = HitBlowGame(self.ctx, players, self.allow_duplicates, self.max_turns)
        active_games[self.ctx.guild.id] = game
        await game.start()

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if (
        message.guild and
        message.guild.id in active_games and
        not message.content.startswith("!")  # ← ここでコマンドは除外
    ):
        await active_games[message.guild.id].handle_guess(message.author, message)

# 起動処理
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))

