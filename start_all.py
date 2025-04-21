import discord
from discord.ext import commands
import hit_and_blow
import janken_bot
import jankenhoitour_bot
import osero

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 各モジュールのコマンドをBotにセットアップ
hit_and_blow.setup(bot)
janken_bot.setup(bot)
jankenhoitour_bot.setup(bot)
osero.setup(bot)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

bot.run('YOUR_TOKEN')
