import discord
from discord.ext import commands
from discord.ui import Button, View
import os
import random
from dotenv import load_dotenv
from PIL import Image
import asyncio
from pathlib import Path

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
IMAGE_DIR = Path(__file__).resolve().parent / "image"

EMPTY = "🟩"
BLACK = "⚫"
WHITE = "⚪"
SIZE = 6

DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1),          (0, 1),
              (1, -1),  (1, 0), (1, 1)]

GFX_BACKGROUND = IMAGE_DIR / "osero_bord.png"
GFX_BLACK      = IMAGE_DIR / "osero_black.png"
GFX_WHITE      = IMAGE_DIR / "osero_white.png"

games = {}

def create_board():
    board = [[EMPTY for _ in range(SIZE)] for _ in range(SIZE)]
    board[2][2] = WHITE
    board[2][3] = BLACK
    board[3][2] = BLACK
    board[3][3] = WHITE
    return board

def is_on_board(x, y):
    return 0 <= x < SIZE and 0 <= y < SIZE

def valid_moves(board, color):
    other = BLACK if color == WHITE else WHITE
    moves = set()
    for y in range(SIZE):
        for x in range(SIZE):
            if board[y][x] != EMPTY:
                continue
            for dx, dy in DIRECTIONS:
                nx, ny = x + dx, y + dy
                found_other = False
                while is_on_board(nx, ny) and board[ny][nx] == other:
                    nx += dx
                    ny += dy
                    found_other = True
                if found_other and is_on_board(nx, ny) and board[ny][nx] == color:
                    moves.add((x, y))
                    break
    return moves

def make_move(board, x, y, color):
    other = BLACK if color == WHITE else WHITE
    flipped = []
    for dx, dy in DIRECTIONS:
        nx, ny = x + dx, y + dy
        path = []
        while is_on_board(nx, ny) and board[ny][nx] == other:
            path.append((nx, ny))
            nx += dx
            ny += dy
        if path and is_on_board(nx, ny) and board[ny][nx] == color:
            flipped.extend(path)
    if flipped:
        board[y][x] = color
        for fx, fy in flipped:
            board[fy][fx] = color
        return True
    elif board[y][x] == (WHITE if color == BLACK else BLACK):
        board[y][x] = color
        return True
    return False

def generate_osero_image(board, background_path, black_path, white_path, output_path):
    background = Image.open(background_path).convert("RGBA")
    black = Image.open(black_path).convert("RGBA")
    white = Image.open(white_path).convert("RGBA")

    width, height = background.size
    cell_width = width // (SIZE + 2)  # サイズに応じてセル幅を計算
    cell_height = height // (SIZE + 2)

    scale_ratio = 1.0
    piece_width = int(cell_width * scale_ratio)
    piece_height = int(cell_height * scale_ratio)
    offset_x = (cell_width - piece_width) // 2
    offset_y = (cell_height - piece_height) // 2

    def place_piece_scaled(base_img, piece_img, col, row):
        x = col * cell_width + offset_x
        y = row * cell_height + offset_y
        resized = piece_img.resize((piece_width, piece_height))
        base_img.paste(resized, (x, y), resized)

    base = background.copy()
    for y in range(SIZE):  # ループ範囲を SIZE に変更
        for x in range(SIZE):
            cell = board[y][x]
            if cell == BLACK:
                place_piece_scaled(base, black, col=x+1, row=y+1)
            elif cell == WHITE:
                place_piece_scaled(base, white, col=x+1, row=y+1)

    base.save(output_path)
    return output_path

def board_to_file(board):
    path = "osero_output.png"
    generate_osero_image(board, GFX_BACKGROUND, GFX_BLACK, GFX_WHITE, path)
    return path

@bot.event
async def on_message(message):
    # コマンドが優先されるように
    await bot.process_commands(message)
    # Bot自身のメッセージは無視
    if message.author.bot:
        return

    cid = message.channel.id
    # ゲームが開始されていないチャンネルは無視
    if cid not in games:
        return

    game = games[cid]

    # ── 対戦相手待ちフェーズ ──
    if game.get("stage") == "await_opponent" and message.mentions:
        opponent = message.mentions[0]
        # 自分との対戦は禁止
        if opponent.id == message.author.id:
            await message.channel.send("自分自身を対戦相手に指定できません。")
            return

        # 人間同士ならじゃんけんフェーズへ
        await message.channel.send(
            f"<@{message.author.id}> vs <@{opponent.id}> でじゃんけんを始めます。ボタンで選んでください！",
            view=JankenView(message.author.id, opponent.id)
        )
        game["stage"] = "janken"
        return

    # ── ゲーム進行中以外は無視 ──
    if game.get("stage") != "playing":
        return

    # 他の人のメッセージも無視
    current_player_id = game["players"][game["turn"]]
    if message.author.id != current_player_id:
        return

    # === 手入力から座標を取得 ===
    move = message.content.upper().strip()
    if len(move) < 2 or move[0] not in "ABCDEFGH" or not move[1:].isdigit():
        return

    col = ord(move[0]) - ord("A")
    row = int(move[1:]) - 1
    if not is_on_board(col, row):
        return

    board = game["board"]
    color = BLACK if game["turn"] == 0 else WHITE

    # 合法手でなければ無視
    if not make_move(board, col, row, color):
        await message.channel.send("そこには置けません。合法手ではありません。")
        return

    # 手が成功したらターン移行
    game["last_pos"] = (col, row)
    game["turn"]     = 1 - game["turn"]

    # 盤面画像を送信
    path = board_to_file(board)
    await message.channel.send(file=discord.File(path))

    # 次のプレイヤーへ
    next_color  = BLACK if game["turn"] == 0 else WHITE
    next_player = game["players"][game["turn"]]
    valid       = valid_moves(board, next_color)

    # 両者合法手なし→ゲーム終了
    if not valid:
        other_color = WHITE if next_color == BLACK else BLACK
        if not valid_moves(board, other_color):
            blacks = sum(r.count(BLACK) for r in board)
            whites = sum(r.count(WHITE) for r in board)
            result = f"黒({BLACK}): {blacks} 石\n白({WHITE}): {whites} 石\n"
            if   blacks > whites:  result += f"<@{game['players'][0]}> の勝ち！"
            elif whites > blacks:  result += f"<@{game['players'][1]}> の勝ち！"
            else:                  result += "引き分け！"
            await message.channel.send(result)
            del games[cid]
            return
        # 自分は打てないが相手は打てる→スキップ
        else:
            await message.channel.send(
                f"<@{next_player}> に合法手がないため、スキップされます。"
            )
            game["turn"] = 1 - game["turn"]
            next_player  = game["players"][game["turn"]]

    # 次のプレイヤーにメンション
    await message.channel.send(
        f"<@{next_player}> の番です。例：'D3' のように送信してください。"
    )

@bot.command()
async def osero(ctx):
    games[ctx.channel.id] = {
        "stage": "await_opponent"
    }
    await ctx.send("対戦相手を `@ユーザー名` で指定してください。")

@bot.command()
async def end(ctx):
    if ctx.channel.id in games:
        del games[ctx.channel.id]
        await ctx.send("ゲームを強制終了しました。")
    else:
        await ctx.send("進行中のゲームはありません。")

@bot.event
async def on_ready():
    print(f"{bot.user} としてログインしました")

bot.run(TOKEN)
