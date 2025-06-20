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

# アクティブゲーム格納
active_games = {}

# 画像フォルダのパス
IMAGE_DIR = Path(__file__).resolve().parent / "image"

# 色絵文字マッピング
COLOR_EMOJIS = {
    "r": "<:red:1362318988365004870>",
    "y": "<:yellow:1362318962041425930>",
    "g": "<:green:1362318888817131530>",
    "b": "<:blue:1362318775990616215>",
    "p": "<:purple:1362318974792241192>",
    "w": "<:white:1362319002541490218>"
}

# 画像合成用ファイルパス
COLOR_IMAGE_FILES = {
    "r": IMAGE_DIR / "red.png",
    "y": IMAGE_DIR / "yellow.png",
    "g": IMAGE_DIR / "green.png",
    "b": IMAGE_DIR / "blue.png",
    "p": IMAGE_DIR / "purple.png",
    "w": IMAGE_DIR / "white.png",
}


# EMOJI_LIST の定義
EMOJI_LIST = list(COLOR_EMOJIS.values())

def generate_guess_emoji(guess):
    """
    guess: ['r', 'y', 'g', 'b']
    returns: 絵文字で表現された結果文字列
    """
    return ''.join(COLOR_EMOJIS[c] for c in guess)

def calculate_hit_blow(secret, guess):
    hits = sum(s == g for s, g in zip(secret, guess))
    blows = sum(min(secret.count(c), guess.count(c)) for c in set(guess)) - hits
    return hits, blows

class HitBlowGame:
    def __init__(self, ctx, players, allow_duplicates, max_turns):
        self.ctx = ctx
        self.players = players
        self.allow_duplicates = allow_duplicates  # True:⭕, False:❌, None:ランダム
        self.max_turns = max_turns
        self.turn_index = 0
        self.turn_count = 0
        self.secret = self.generate_secret()
        self.guess_log = []
        self.running = True
        self.current_player = None

    def generate_secret(self):
        """
        allow_duplicates:
         - True  → 色かぶり⭕（必ずどこかに重複あり）
         - False → 色かぶり❌（完全にユニーク）
         - None  → ランダム：重複あり or なし をランダム選択、
                     重複ありの場合も必ずとはせずランダムで作成
        """
        mode = self.allow_duplicates
        if mode is None:
            mode = random.choice([True, False])

        if mode:
            # 重複を許可しつつ、重複が発生するかどうかも半分の確率で決定
            if random.choice([True, False]):
                # ２つだけ必ず重複させる
                duplicated = random.choice(EMOJI_LIST)
                others = random.sample([e for e in EMOJI_LIST if e != duplicated], 2)
                secret = [duplicated, duplicated] + others
            else:
                # 重複なしで生成
                secret = random.sample(EMOJI_LIST, 4)
        else:
            # 完全に重複なし
            secret = random.sample(EMOJI_LIST, 4)

        random.shuffle(secret)
        return secret

    async def start(self):
        emoji_list   = ' '.join(COLOR_EMOJIS[c] for c in 'rygbpw')
        abbreviation = ' '.join(f"{c}={COLOR_EMOJIS[c]}" for c in 'rygbpw')
        mode_text    = ('色かぶりランダム' if self.allow_duplicates is None
                        else '色かぶり⭕' if self.allow_duplicates
                        else '色かぶり❌')

        await self.ctx.send(
            f"🎯**Lets!ヒットアンドブロー!**（**{mode_text}**、**{self.max_turns}ターン制**）!joinで途中参加可\n"
        )
        await self.next_turn()

    async def next_turn(self):
        if not self.running:
            return

        if self.turn_count >= self.max_turns:
            await self.ctx.send(f"💀 ターン数上限に達しました！\n正解は：{''.join(self.secret)}\nでした")
            await self.show_results(None)
            return

        player = self.players[self.turn_index % len(self.players)]
        self.current_player = player

        remaining = self.max_turns - self.turn_count
        abbreviation = ' '.join(f"{c}={COLOR_EMOJIS[c]}" for c in 'rygbpw')
        await self.ctx.send(
            f"⏳ {player.mention} さんのターン！（残り**{remaining}**ターン）\n"
            f"Color: {abbreviation}"
        )

        self.turn_index += 1
        self.turn_count += 1

    async def handle_guess(self, user, message):
           if not self.running or user != self.current_player:
               return

           # ユーザーの入力を取得
           raw = message.content.strip().lower()

           # 入力の検証
           if len(raw) != 4 or any(c not in COLOR_IMAGE_FILES for c in raw):
               return  # メッセージ送信をスキップ

           guess = list(raw)
           hits, blows = calculate_hit_blow(self.secret, [COLOR_EMOJIS[c] for c in guess])
           self.guess_log.append((guess, hits, blows))

           # 絵文字結果を生成
           emoji_result = generate_guess_emoji(guess)
           await message.channel.send(
               content=f"🎯 **{hits}ヒット {blows}ブロー** {emoji_result}"
           )

           if hits == 4:
               await self.show_results(winner=user)
               return

           await self.next_turn()
           await self.show_history()

    async def show_results(self, winner):
        if winner:
            await self.ctx.send(f"🏆 {winner.mention} さんが正解しました！🎉")

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

        await self.ctx.send("📜 **現在の履歴**\n" + "\n".join(lines) + "\n")

    async def exit_player(self, user):
        if user in self.players:
            self.players.remove(user)
            await self.ctx.send(f"👋 {user.display_name} さんが退出しました。")
            if not self.players:
                await self.force_end()

    async def force_end(self):
        await self.ctx.send(f"🛑 ゲームが中断されました！答えは：{''.join(self.secret)}")
        await self.show_results(None)
        self.running = False
        active_games.pop(self.ctx.guild.id, None)  # ゲームを確実に削除

@bot.command()
async def hit(ctx):
     if ctx.guild.id in active_games:
         return await ctx.send("🚫 すでにゲームが進行中でございます。", delete_after=10)

    # チャンネル内でモード選択ビューを表示
     await ctx.send(
         "🎮**ヒットアンドブローを始めます**！\n"
         "🕹️**まずはゲームモードを選択してください!**：",
         view=ModeSelectView(ctx),
     )

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
    if game and game.running:
        if ctx.author in game.players:
            return await ctx.send("🚫 既に参加なさっております。")
        # 次のターンに合流できるよう挿入
        new_len = len(game.players) + 1
        pos = game.turn_index % new_len
        game.players.insert(pos, ctx.author)
        await ctx.send(f"🎉 {ctx.author.mention} さんが参加しました！（次のターンが {ctx.author.mention} さんの番です。） ")
    else:
        await ctx.send("🚫 現在参加可能なゲームはございません。")

class ModeSelectView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx

    async def interaction_check(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "🚫 あなたはこの操作を行えません。", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="色かぶり⭕", style=discord.ButtonStyle.success)
    async def allow_dup(self, interaction, button):
        await self.ask_turn(interaction, True)

    @discord.ui.button(label="色かぶり❌", style=discord.ButtonStyle.primary)
    async def no_dup(self, interaction, button):
        await self.ask_turn(interaction, False)

    @discord.ui.button(label="色かぶりランダム", style=discord.ButtonStyle.danger)
    async def random_dup(self, interaction, button):
        await self.ask_turn(interaction, None)

    async def ask_turn(self, interaction, allow_dup):
        # 次はターン数選択ビューをDMで送信
        await interaction.response.edit_message(
            content="🎯 **ターン数を選択してください**",
            view=TurnSelectView(self.ctx, allow_dup)
        )

class TurnSelectView(discord.ui.View):
    def __init__(self, ctx, allow_dup):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.allow_dup = allow_dup
        self.selected_button = None  # 選択されたボタンを追跡

    async def interaction_check(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "🚫 あなたはこの操作を行えません。", ephemeral=True
            )
            return False
        return True

    async def start_entry(self, interaction, max_turns, button):
        # 選択されたボタンのスタイルを変更
        if self.selected_button:
            self.selected_button.style = discord.ButtonStyle.secondary  # 他のボタンをリセット
        button.style = discord.ButtonStyle.primary  # 選択されたボタンを緑に変更
        self.selected_button = button  # 選択されたボタンを記録

        # ボタンを削除してメッセージを更新
        self.clear_items()
        await interaction.response.edit_message(content="⏳ ゲームを準備中...", view=self)

        # 参加受付ビューをチャンネルに送信
        entry_view = EntryView(self.ctx, self.allow_dup, max_turns)
        entry_view.entries.add(self.ctx.author)  # コマンド実行者を自動登録
        await self.ctx.send(
            f"📢 **10秒間ヒットアンドブロ―参加者受付中！**(ゲームマスターは自動参加)",
            view=entry_view
        )

    @discord.ui.button(label="4ターン", style=discord.ButtonStyle.secondary)
    async def t4(self, interaction, button): await self.start_entry(interaction, 4, button)

    @discord.ui.button(label="5ターン", style=discord.ButtonStyle.secondary)
    async def t5(self, interaction, button): await self.start_entry(interaction, 5, button)

    @discord.ui.button(label="6ターン", style=discord.ButtonStyle.secondary)
    async def t6(self, interaction, button): await self.start_entry(interaction, 6, button)

    @discord.ui.button(label="7ターン", style=discord.ButtonStyle.secondary)
    async def t7(self, interaction, button): await self.start_entry(interaction, 7, button)

    @discord.ui.button(label="8ターン", style=discord.ButtonStyle.secondary)
    async def t8(self, interaction, button): await self.start_entry(interaction, 8, button)

class EntryView(discord.ui.View):
    def __init__(self, ctx, allow_duplicates, max_turns):
        super().__init__(timeout=10)
        self.ctx = ctx
        self.entries = set()
        self.allow_duplicates = allow_duplicates
        self.max_turns = max_turns

    @discord.ui.button(label="✋ 参加する!", style=discord.ButtonStyle.success)
    async def entry(self, interaction, button):
        if interaction.user in self.entries:
            await interaction.response.send_message(
                "🚫 **すでに参加登録済みです！**", ephemeral=True
            )
        else:
            self.entries.add(interaction.user)
            await interaction.response.send_message(
                "🆗 **参加登録完了！**", ephemeral=True
            )

    async def on_timeout(self):
        # ボタンを削除
        self.clear_items()

        if not self.entries:
            return await self.ctx.send("❌ 参加者がおりませんでした。")
        
        # ゲームを開始
        players = list(self.entries)
        random.shuffle(players)
        game = HitBlowGame(self.ctx, players, self.allow_duplicates, self.max_turns)
        active_games[self.ctx.guild.id] = game
        await game.start()

@bot.event
async def on_message(message):
    # 1. 既存のコマンドを処理
    await bot.process_commands(message)

    # 2. Bot自身や他のBotのメッセージは無視
    if message.author.bot:
        return

    # 3. ギルド内ゲームがあり、プレフィックスでないメッセージなら推測ハンドル
    game = active_games.get(message.guild.id) if message.guild else None
    if game and not message.content.startswith("!"):
        await game.handle_guess(message.author, message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # 無視する or 任意のメッセージを送る
        return
    raise error  # 他のエラーは再度 raise する

# 起動処理
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
