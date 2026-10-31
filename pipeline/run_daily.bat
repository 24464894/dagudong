@echo off
chcp 65001 >nul
rem 大股東在幹嘛：更新資料並推上 GitHub（在 repo 的 pipeline 資料夾裡執行）
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 call conda activate openwebui

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%d

echo [1/4] 下載政府公開資料...
python fetch_datagov.py
if errorlevel 1 goto fail

echo [2/4] 整理成 data.json...
python build_data.py raw\%TODAY% ..\data.json
if errorlevel 1 goto fail
if not exist ..\history mkdir ..\history
copy /y ..\data.json ..\history\%TODAY%.json >nul

echo [3/4] 匯進本機資料庫 history.db...
python to_sqlite.py
if errorlevel 1 echo （資料庫匯入失敗，不影響發布，繼續）

echo [4/4] 推上 GitHub...
cd /d "%~dp0.."
git add data.json content.json history
git commit -m "data %TODAY%" >nul
git push
if errorlevel 1 goto fail
echo 完成：%TODAY% 的資料已發布。
goto end

:fail
echo 失敗了，請看上面的訊息。
:end
if /i not "%1"=="auto" pause
