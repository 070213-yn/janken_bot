@echo off
cd /d %~dp0

echo === 通常じゃんけんBotを起動します ===
start "" python janken_bot.py
timeout /t 1

echo === あっち向いてホイBotを起動します ===
start "" python jankenhoitour_bot.py
timeout /t 1

echo === ヒットアンドブローBotを起動します ===
start "" python hit_and_blow.py
timeout /t 1

echo === オセロBotを起動します ===
start "" python osero.py
timeout /t 1

echo === コネクトフォーBotを起動します ===
start "" python connect4_bot.py
timeout /t 1

pause
