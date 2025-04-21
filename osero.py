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

def count_flippable(board, x, y, color):
    temp = [row[:] for row in board]
    before = sum(row.count(color) for row in temp)
    if not make_move(temp, x, y, color):
        return -1
    after = sum(row.count(color) for row in temp)
    return after - before

async def simulate_bot_turn(channel_id):
    game = games.get(channel_id)
    if not game or game["stage"] != "playing":
        return

    await asyncio.sleep(2)

    channel = bot.get_channel(channel_id)
    board = game["board"]
    color = BLACK if game["turn"] == 0 else WHITE
    opponent_color = WHITE if color == BLACK else BLACK
    legal_moves = list(valid_moves(board, color))

    if "bot_turn_count" not in game:
        game["bot_turn_count"] = 0
    game["bot_turn_count"] += 1
    turn = game["bot_turn_count"]

    cheat_chance = 0.1 if turn <= 6 else 0.15 if turn <= 12 else 0.2
    do_override = random.random() < cheat_chance

    if do_override:

        # ── 上書きカウンタをインクリメント ──
        game["override_count"] = game.get("override_count", 0) + 1
        # ── 残り回数を自動送信 ──
        rem = 10 - game["override_count"]
        await channel.send(f"上書きはあと{rem}回可能です。／You can override {rem} more times.")

        override_candidates = [(x, y) for y in range(SIZE) for x in range(SIZE) if board[y][x] == opponent_color]
        best_pos = None
        max_flips = -1
        for x, y in override_candidates:
            flips = count_flippable(board, x, y, color)
            if flips > max_flips:
                best_pos = (x, y)
                max_flips = flips

        if best_pos and max_flips > 0:
            col, row = best_pos
            board[row][col] = color
            game["last_pos"] = (col, row)
            game["turn"] = 1 - game["turn"]

            col_label = chr(ord("A") + col)
            row_label = str(row + 1)
            await channel.send(f"Bot は {col_label}{row_label} に上書きしました！")

            path = board_to_file(board)
            await channel.send(file=discord.File(path))

            next_player = game["players"][game["turn"]]
            if next_player == bot.user.id:
                await simulate_bot_turn(channel_id)
            else:
                await channel.send(f"<@{next_player}> の番です。例：'D3' のように送信してください。")
            return

        if not legal_moves:
            other_color = opponent_color
            if not valid_moves(board, other_color):
                # 両方合法手なし→ゲーム終了
                blacks = sum(row.count(BLACK) for row in board)
                whites = sum(row.count(WHITE) for row in board)
                result = f"黒({BLACK}): {blacks} 石\n白({WHITE}): {whites} 石\n"
                if blacks > whites:
                    result += f"<@{game['players'][0]}> の勝ち！"
                elif whites > blacks:
                    result += f"<@{game['players'][1]}> の勝ち！"
                else:
                    result += "引き分け！"
                await channel.send(result)
                del games[channel_id]
                return
            else:
                # 自分は打てないが相手は打てる → スキップ
                await channel.send(f"<@{game['players'][game['turn']]}> に合法手がないため、スキップされます。")
                game["turn"] = 1 - game["turn"]
                next_player = game["players"][game["turn"]]

                if next_player == bot.user.id:
                    await asyncio.sleep(2)
                    await simulate_bot_turn(channel_id)
                else:
                    await channel.send(f"<@{next_player}> の番です。例：'D3' のように送信してください。")
                return

    col, row = random.choice(legal_moves)
    make_move(board, col, row, color)
    game["last_pos"] = (col, row)
    game["turn"] = 1 - game["turn"]

    col_label = chr(ord("A") + col)
    row_label = str(row + 1)
    await channel.send(f"Bot は {col_label}{row_label} に置きました。")

    path = board_to_file(board)
    await channel.send(file=discord.File(path))

    next_color = BLACK if game["turn"] == 0 else WHITE
    next_player = game["players"][game["turn"]]
    valid = valid_moves(board, next_color)

    if not valid:
        other_color = WHITE if next_color == BLACK else BLACK
        if not valid_moves(board, other_color):
            blacks = sum(row.count(BLACK) for row in board)
            whites = sum(row.count(WHITE) for row in board)
            result = f"黒({BLACK}): {blacks} 石\n白({WHITE}): {whites} 石\n"
            if blacks > whites:
                result += f"<@{game['players'][0]}> の勝ち！"
            elif whites > blacks:
                result += f"<@{game['players'][1]}> の勝ち！"
            else:
                result += "引き分け！"
            await channel.send(result)
            del games[channel_id]
            return
        else:
            await channel.send(f"<@{next_player}> に合法手がないため、スキップされます。")
            game["turn"] = 1 - game["turn"]
            next_player = game["players"][game["turn"]]

    if next_player == bot.user.id:
        await simulate_bot_turn(channel_id)
    else:
        await channel.send(f"<@{next_player}> の番です。例：'D3' のように送信してください。")

from discord.ui import View, Button

class JankenView(View):
    def __init__(self, p1, p2):
        super().__init__(timeout=None)
        self.p1 = p1
        self.p2 = p2
        self.choices = {}

    @discord.ui.button(label="✊", style=discord.ButtonStyle.primary)
    async def rock(self, interaction, button):
        await self.choose(interaction, "rock")

    @discord.ui.button(label="✌", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction, button):
        await self.choose(interaction, "scissors")

    @discord.ui.button(label="✋", style=discord.ButtonStyle.primary)
    async def paper(self, interaction, button):
        await self.choose(interaction, "paper")

    async def choose(self, interaction, choice):
        user = interaction.user.id
        if user not in (self.p1, self.p2):
            return
        self.choices[user] = choice
        await interaction.response.defer()
        if len(self.choices) == 2:
            await self.resolve(interaction.channel)

    async def resolve(self, channel):
        p1_choice = self.choices[self.p1]
        p2_choice = self.choices[self.p2]

        result_map = {
            ("rock", "scissors"): self.p1,
            ("scissors", "paper"): self.p1,
            ("paper", "rock"): self.p1,
            ("scissors", "rock"): self.p2,
            ("paper", "scissors"): self.p2,
            ("rock", "paper"): self.p2,
        }

        if p1_choice == p2_choice:
            await channel.send("引き分けです。もう一度！", view=JankenView(self.p1, self.p2))
        else:
            winner = result_map[(p1_choice, p2_choice)]
            loser = self.p1 if winner == self.p2 else self.p2

            # ゲーム開始
            games[channel.id] = {
                "players": [winner, loser],
                "board": create_board(),
                "stage": "playing",
                "turn": 0,
                "last_pos": None
            }
            await channel.send(f"<@{winner}> が先攻（{BLACK}）です！")
            path = board_to_file(games[channel.id]["board"])
            await channel.send(file=discord.File(path))
            await channel.send(f"<@{winner}> の番です。例：'D3' のように送信してください。")

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

        # Botと対戦する場合
        if opponent.bot:
            p1, p2 = message.author.id, opponent.id
            players = [p1, p2]
            random.shuffle(players)
            game["players"] = players
            game["board"]   = create_board()
            game["stage"]   = "playing"
            game["turn"]    = 0
            game["last_pos"]= None
            # 上書き回数初期化
            game["override_count"] = 0

            await message.channel.send(f"<@{players[0]}> が先攻（{BLACK}）です！")
            path = board_to_file(game["board"])
            await message.channel.send(file=discord.File(path))
            await message.channel.send(f"<@{players[0]}> の番です。例：'D3' のように送信してください。")

            # Botが先攻なら即打ち
            if players[0] == bot.user.id:
                await simulate_bot_turn(cid)
            return

        # 人間同士ならじゃんけんフェーズへ
        else:
            await message.channel.send(
                f"<@{message.author.id}> vs <@{opponent.id}> でじゃんけんを始めます。ボタンで選んでください！",
                view=JankenView(message.author.id, opponent.id)
            )
            game["stage"] = "janken"
            return

    # ── ゲーム進行中以外は無視 ──
    if game.get("stage") != "playing":
        return

    # Botの番なら無視
    current_player_id = game["players"][game["turn"]]
    if current_player_id == bot.user.id:
        return
    # 他の人のメッセージも無視
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
    opponent_color = WHITE if color == BLACK else BLACK

    # ── 人間プレイヤーの上書き回数制限 ──
    if board[row][col] == opponent_color:
        if "override_count" not in game:
            game["override_count"] = {game["players"][0]: 0, game["players"][1]: 0}

        # プレイヤーの上書き回数を確認
        current_player = game["players"][game["turn"]]
        if game["override_count"][current_player] >= 10:
            await message.channel.send("上書きは10回まで可能です。")
            return

        # 上書き回数をインクリメント
        game["override_count"][current_player] += 1

        # 残り回数を自動送信
        rem = 10 - game["override_count"][current_player]
        await message.channel.send(f"上書きはあと{rem}回可能です。／You can override {rem} more times.")

    # 自分の石への上書きは禁止
    if board[row][col] == color:
        await message.channel.send("自分の石がある場所には置けません。")
        return

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

    # 次がBotならBotに移譲、そうでなければメンション
    if next_player == bot.user.id:
        await simulate_bot_turn(cid)
    else:
        await message.channel.send(
            f"<@{next_player}> の番です。例：'D3' のように送信してください。"
        )

@bot.command()
async def osero(ctx):
    games[ctx.channel.id] = {
        "stage": "await_opponent"
    }
    await ctx.send("対戦相手を `@ユーザー名` で指定してください（または @Bot と対戦）。")

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

@bot.command()
async def c(ctx):
    """上書き残回数を表示するコマンド / Show remaining override count"""
    game = games.get(ctx.channel.id)
    # ゲーム進行中でなければ
    if not game or game.get("stage") != "playing":
        await ctx.send("進行中のゲームがありません")
        return

    # 現在の上書き使用回数を取得（未定義なら0）
    used = game.get("override_count", 0)
    remaining = max(0, 10 - used)
    await ctx.send(f"上書きはあと{remaining}回可能です！")


bot.run(TOKEN)