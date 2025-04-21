@echo off
echo GitHub にアップロードを開始します...

:: git 初期化（必要な場合）
IF NOT EXIST .git (
    git init
)

:: .env を除外（まだなら .gitignore に追加）
findstr /C:".env" .gitignore >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo .env>>.gitignore
    echo .env を .gitignore に追加しました。
)

:: すべての変更をステージング
git add .

:: コミット（日時で一意のコメントをつけます）
set datetime=%date%_%time%
set datetime=%datetime::=-%
set datetime=%datetime: =_%
git commit -m "Update on %datetime%"

:: リモートリポジトリが設定されているか確認（必要であれば設定を促す）
git remote -v >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ リモートリポジトリが設定されていません。
    echo git remote add origin https://github.com/USERNAME/REPO.git を使って設定してください。
    pause
    exit /b
)

:: プッシュ
git push origin main

echo.
echo ✅ アップロードが完了しました！
pause
