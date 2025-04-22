@echo off
chcp 65001 >nul
echo GitHub にアップロードを開始します...  (Starting upload to GitHub...)

:: git 初期化（必要な場合） (Initialize git if not yet)
IF NOT EXIST .git (
    git init
)

:: .env を除外（まだなら .gitignore に追加） (Exclude .env by adding to .gitignore if missing)
findstr /C:".env" .gitignore >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo .env>>.gitignore
    echo .env を .gitignore に追加しました。  (Added .env to .gitignore)
)

:: すべての変更をステージング (Stage all changes)
git add hit_and_blow.py
git add --all

:: コミット（日時で一意のコメント） (Commit with timestamp in message)
for /f "tokens=1-3 delims=/: " %%a in ("%date%") do set d=%%c-%%a-%%b
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do set t=%%a-%%b-%%c
set datetime=%d%_%t%
git commit -m "Update on %datetime%"

:: リモートリポジトリ設定の確認 (Check if remote is set)
git remote -v >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo. 
    echo ⚠️ リモートリポジトリが設定されていません。  (Remote not set)
    echo git remote add origin https://github.com/USERNAME/REPO.git を実行してください。  (Please run git remote add ...)
    pause
    exit /b
)

:: プッシュ (Push to GitHub)
git push origin main

echo.
echo ✅ アップロードが完了しました！  (Upload complete!)
pause
