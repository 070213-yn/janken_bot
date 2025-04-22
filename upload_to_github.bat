@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo GitHub にアップロードを開始します...

:: リモート origin の URL を取得（存在しない場合はエラー）
git remote get-url origin >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    set /p "REMOTE_URL=⚠️ リモートリポジトリURLを入力してください (例: https://github.com/070213-yn/janken_bot): "
    git remote add origin %REMOTE_URL%
    echo origin を %REMOTE_URL% に設定しました。
)

:: git 初期化（必要な場合）
IF NOT EXIST .git (
    git init
)

:: .env を .gitignore に追加（未登録時のみ）
findstr /C:".env" .gitignore >nul 2>&1 || (
    echo .env>>.gitignore
    echo .env を .gitignore に追加しました。
)

:: 全ての変更をステージング
git add --all

:: タイムスタンプ付きコミット
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do set d=%%c-%%a-%%b
for /f "tokens=1-3 delims=:. "     %%a in ("%time%") do set t=%%a-%%b-%%c
set datetime=%d%_%t%
git commit -m "Update on %datetime%"

:: プッシュ
git push origin main

echo.
echo ✅ アップロードが完了しました！
pause
