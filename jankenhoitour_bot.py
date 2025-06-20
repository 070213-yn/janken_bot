import discord
from discord.ext import commands
import random
import asyncio
from dotenv import load_dotenv
import os


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_tournaments = {}

class JankenHouiSession:
    def __init__(self, ctx, player1, player2):
        self.ctx = ctx
        self.player1 = player1
        self.player2 = player2
        self.hands = {}
        self.winner = None
        self.loser = None
        self.finger_direction = None

    async def start(self):
        self.hands.clear()
        await self.ctx.send(f"🧤 {self.player1.mention} vs {self.player2.mention}\n最初はグー✊じゃんけん～～：", view=JankenView(self))

    async def handle_hand(self, user, hand):
        self.hands[user.id] = hand
        if len(self.hands) == 2:
            await self.resolve_janken()

    async def resolve_janken(self):
        p1_hand = self.hands[self.player1.id]
        p2_hand = self.hands[self.player2.id]
        beats = {"グー": "チョキ", "チョキ": "パー", "パー": "グー"}

        await self.ctx.send(f"{self.player1.display_name}: {p1_hand} vs {self.player2.display_name}: {p2_hand}")

        if p1_hand == p2_hand:
            await self.ctx.send("🌀 あいこで～～ ")
            await self.start()
            return

        if beats[p1_hand] == p2_hand:
            self.winner = self.player1
            self.loser = self.player2
        else:
            self.winner = self.player2
            self.loser = self.player1

        await self.ask_finger_direction()

    async def ask_finger_direction(self):
        await self.ctx.send(f"👉 {self.winner.mention} さん、指の方向を選んでください：", view=FingerView(self))

    async def handle_finger(self, user, direction):
        if user != self.winner:
            return
        self.finger_direction = direction
        await self.ask_face_direction()

    async def ask_face_direction(self):
        await self.ctx.send(f"😳 {self.loser.mention} さん、顔の向きを選んでください：", view=FaceView(self))

    async def handle_face(self, user, direction):
        if user != self.loser:
            return
        if direction == self.finger_direction:
            await self.ctx.send(f"🎯 一致！{self.winner.display_name} さんの勝利！")
            self.ctx.bot.dispatch("tournament_win", self.ctx.guild.id, self.winner)
        else:
            await self.ctx.send(f"😆 指: {self.finger_direction} vs 顔: {direction} → 不一致！再戦します！")
            await self.start()

class JankenView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=60)
        self.session = session

    async def handle(self, interaction, hand):
        if interaction.user.id not in [self.session.player1.id, self.session.player2.id]:
            await interaction.response.send_message("この試合には参加していません。", ephemeral=True)
            return
        await interaction.response.send_message(f"{hand} を選びました。", ephemeral=True)
        await self.session.handle_hand(interaction.user, hand)

    @discord.ui.button(label="グー ✊", style=discord.ButtonStyle.primary)
    async def g(self, i, b): await self.handle(i, "グー")
    @discord.ui.button(label="チョキ ✌️", style=discord.ButtonStyle.primary)
    async def c(self, i, b): await self.handle(i, "チョキ")
    @discord.ui.button(label="パー 🖐️", style=discord.ButtonStyle.primary)
    async def p(self, i, b): await self.handle(i, "パー")

class FingerView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=30)
        self.session = session

    async def handle(self, interaction, direction):
        if interaction.user != self.session.winner:
            await interaction.response.send_message("あなたは指を決める側ではありません。", ephemeral=True)
            return
        await interaction.response.send_message(f"{direction} を選びました。", ephemeral=True)
        await self.session.handle_finger(interaction.user, direction)

    @discord.ui.button(label="↑ 上", style=discord.ButtonStyle.secondary)
    async def up(self, i, b): await self.handle(i, "上")
    @discord.ui.button(label="↓ 下", style=discord.ButtonStyle.secondary)
    async def down(self, i, b): await self.handle(i, "下")
    @discord.ui.button(label="← 左", style=discord.ButtonStyle.secondary)
    async def left(self, i, b): await self.handle(i, "左")
    @discord.ui.button(label="→ 右", style=discord.ButtonStyle.secondary)
    async def right(self, i, b): await self.handle(i, "右")

class FaceView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=30)
        self.session = session

    async def handle(self, interaction, direction):
        if interaction.user != self.session.loser:
            await interaction.response.send_message("あなたは顔の向きを決める側ではありません。", ephemeral=True)
            return
        await interaction.response.send_message(f"{direction} を選びました。", ephemeral=True)
        await self.session.handle_face(interaction.user, direction)

    @discord.ui.button(label="↑ 上", style=discord.ButtonStyle.secondary)
    async def up(self, i, b): await self.handle(i, "上")
    @discord.ui.button(label="↓ 下", style=discord.ButtonStyle.secondary)
    async def down(self, i, b): await self.handle(i, "下")
    @discord.ui.button(label="← 左", style=discord.ButtonStyle.secondary)
    async def left(self, i, b): await self.handle(i, "左")
    @discord.ui.button(label="→ 右", style=discord.ButtonStyle.secondary)
    async def right(self, i, b): await self.handle(i, "右")

@bot.command(name="h")
async def h(ctx):
    if ctx.guild.id in active_tournaments:
        await ctx.send("すでにトーナメントが開催されています！")
        return
    await ctx.send("🎮 【トーナメント制】あっち向いてホイの参加者募集！参加者は下のボタンを押してください！", view=EntryView(ctx))

class EntryView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=5)
        self.ctx = ctx
        self.entries = set()

    @discord.ui.button(label="参加する！", style=discord.ButtonStyle.success)
    async def entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.entries.add(interaction.user)
        await interaction.response.send_message("参加を受け付けました！", ephemeral=True)

    async def on_timeout(self):
        if len(self.entries) < 2:
            await self.ctx.send("参加者が足りませんでした…")
            return
        shuffled = list(self.entries)
        random.shuffle(shuffled)
        active_tournaments[self.ctx.guild.id] = TournamentState(self.ctx, shuffled)
        await active_tournaments[self.ctx.guild.id].run_next_match()

class TournamentState:
    def __init__(self, ctx, players):
        self.ctx = ctx
        self.players = players

    async def run_next_match(self):
        if len(self.players) == 1:
            await self.ctx.send(f"🏆 優勝者は {self.players[0].mention} さんです！おめでとうございます！")
            del active_tournaments[self.ctx.guild.id]
            return
        player1 = self.players.pop(0)
        player2 = self.players.pop(0)
        self.session = JankenHouiSession(self.ctx, player1, player2)
        await self.session.start()

    def winner_advance(self, winner):
        self.players.append(winner)

@bot.event
async def on_tournament_win(guild_id, winner):
    tournament = active_tournaments.get(guild_id)
    if tournament:
        tournament.winner_advance(winner)
        await tournament.run_next_match()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # 無視する or 任意のメッセージを送る
        return
    raise error  # 他のエラーは再度 raise する

# 起動処理
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
