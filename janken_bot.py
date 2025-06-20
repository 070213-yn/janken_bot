import discord
from discord.ext import commands
import random
import asyncio
from dotenv import load_dotenv
import os


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_games = {}

class GroupJankenSession:
    def __init__(self, ctx):
        self.ctx = ctx
        self.players = set()
        self.hands = {}
        self.collecting = True

    async def start(self):
        await self.ctx.send("最初はグー✊じゃんけん～～\n手を選んでください：", view=GroupJankenView(self))

    async def handle_hand(self, user, hand):
        if not self.collecting:
            return
        if user.id in self.hands:
            return
        self.players.add(user)
        self.hands[user.id] = (user, hand)

    async def finalize(self):
        self.collecting = False
        if len(self.players) < 2:
            await self.ctx.send("相手が見つかりませんでした。")
            return

        await self.ctx.send("🗣️ ポイ！")
        results = [f"{user.display_name}：{hand}" for user, hand in self.hands.values()]
        await self.ctx.send("\n".join(results))

        hands_list = [hand for _, hand in self.hands.values()]
        unique = set(hands_list)
        if len(unique) == 1 or len(unique) == 3:
            await self.ctx.send("🌀 あいこで～～")
            await asyncio.sleep(1)
            await self.start()
            return

        beats = {"グー": "チョキ", "チョキ": "パー", "パー": "グー"}
        winner_hand = None
        for h in unique:
            if all(beats[h] == oh for oh in unique if oh != h):
                winner_hand = h
                break

        winners = [user for user, hand in self.hands.values() if hand == winner_hand]
        names = ', '.join(user.mention for user in winners)
        await self.ctx.send(f"🎉 勝者: {names}（{winner_hand}）🎉")

        if self.ctx.guild:
            del active_games[self.ctx.guild.id]

class GroupJankenView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=10)
        self.session = session
        self.timer_started = False

    async def handle(self, interaction, hand):
        await self.session.handle_hand(interaction.user, hand)
        await interaction.response.send_message(f"{hand} を選びました！", ephemeral=True)

        if not self.timer_started:
            self.timer_started = True
            await asyncio.sleep(5)
            await self.session.finalize()

    @discord.ui.button(label="グー ✊", style=discord.ButtonStyle.primary)
    async def g(self, i, b): await self.handle(i, "グー")
    @discord.ui.button(label="チョキ ✌️", style=discord.ButtonStyle.primary)
    async def c(self, i, b): await self.handle(i, "チョキ")
    @discord.ui.button(label="パー 🖐️", style=discord.ButtonStyle.primary)
    async def p(self, i, b): await self.handle(i, "パー")

@bot.command(name="j")
async def j(ctx):
    if ctx.guild and ctx.guild.id in active_games:
        await ctx.send("現在進行中のじゃんけんがあります。")
        return
    session = GroupJankenSession(ctx)
    if ctx.guild:
        active_games[ctx.guild.id] = True
    await session.start()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # 無視する or 任意のメッセージを送る
        return
    raise error  # 他のエラーは再度 raise する


# 起動処理
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN")) 
