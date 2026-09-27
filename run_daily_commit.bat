@echo off
cd /d D:\VSCode\shared-budget-bot
"D:\VSCode\shared-budget-bot\.venv\Scripts\python.exe" daily_commit.py
exit /b %ERRORLEVEL%