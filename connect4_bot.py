import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

EMOJIS = {
    "empty": "<:space:1385582681118478388>",
    "red": "<:red:1362318988365004870>",
    "blue": "<:blue:1362318775990616215>",
}

COLUMNS = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
ROWS = 6

games = {}

class Connect4Game:
    def __init__(self, player1, player2):
        self.board = [['empty' for _ in range(7)] for _ in range(ROWS)]
        self.players = [player1, player2]
        random.shuffle(self.players)
        self.current = 0
        self.winner = None
        self.active = True

    def place_piece(self, column_letter):
        if column_letter not in COLUMNS:
            return False, "無効な列でございますわ。"

        col = COLUMNS.index(column_letter)
        for row in reversed(range(ROWS)):
            if self.board[row][col] == 'empty':
                self.board[row][col] = 'red' if self.current == 0 else 'blue'
                if self.check_win(row, col):
                    self.winner = self.players[self.current]
                    self.active = False
                else:
                    self.current = 1 - self.current
                return True, None
        return False, "この列はすでに埋まっておりますわ。"

    def check_win(self, r, c):
        color = self.board[r][c]
        directions = [(1,0), (0,1), (1,1), (1,-1)]
        for dr, dc in directions:
            count = 1
            for d in [-1, 1]:
                for i in range(1, 4):
                    nr, nc = r + dr*i*d, c + dc*i*d
                    if 0 <= nr < ROWS and 0 <= nc < 7 and self.board[nr][nc] == color:
                        count += 1
                    else:
                        break
            if count >= 4:
                return True
        return False

    def get_board_display(self):
        board_str = '\n'.join(''.join(EMOJIS[cell] for cell in row) for row in self.board)
        footer = (
                "<:A_:1385608608913293322>"
                "<:B_:1385608616064712917>"
                "<:C_:1385608624818356325>"
                "<:D_:1385608635476082819>"
                "<:E_:1385608646372622457>"
                "<:F_:1385608657747574876>"
                "<:G_:1385608684683399250>"
        )
        return f"{board_str}\n{footer}"


class JoinView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author
        self.opponent = None

    @discord.ui.button(label="参加する", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user == self.author:
            await interaction.response.send_message("自分自身とは戦えませんわ。", ephemeral=True)
            return
        self.opponent = interaction.user
        self.stop()

@bot.command()
async def con(ctx):
    if ctx.channel.id in games:
        await ctx.send("既にゲームが進行中でございますわ。")
        return

    view = JoinView(ctx.author)
    await ctx.send(f"{ctx.author.mention} がコネクトフォーを開始しましたわ。参加者は下のボタンを押して下さいませ。", view=view)
    await view.wait()

    if not view.opponent:
        await ctx.send("参加者が現れませんでしたわ。")
        return

    game = Connect4Game(ctx.author, view.opponent)
    games[ctx.channel.id] = game
    await ctx.send(f"{game.players[0].mention} vs {game.players[1].mention} ゲーム開始ですわ！\n{game.players[game.current].mention} が先攻ですわ。\n{game.get_board_display()}")

@bot.command()
async def end(ctx):
    if ctx.channel.id not in games:
        await ctx.send("ゲームは進行しておりませんわ。")
        return
    del games[ctx.channel.id]
    await ctx.send("ゲームを中断いたしましたわ。")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    game = games.get(message.channel.id)
    if game and game.active and message.author == game.players[game.current]:
        content = message.content.strip().upper()
        if content in COLUMNS:
            success, error = game.place_piece(content)
            if not success:
                await message.channel.send(error)
                return

            board_display = game.get_board_display()
            if game.winner:
                await message.channel.send(f"{board_display}\n{game.winner.mention} の勝利でございますわ！🎉")
                del games[message.channel.id]
            else:
                await message.channel.send(f"{board_display}\n次は {game.players[game.current].mention} の番でございますわ。")
            return

    await bot.process_commands(message)

# 起動処理
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
