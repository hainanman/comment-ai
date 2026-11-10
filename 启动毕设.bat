@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\waitress-serve.exe" (
  echo [ERROR] .venv not found.
  echo Run: pip install -r requirements.txt
  pause
  exit /b 1
)

start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:5000/products/'"

echo.
echo Starting CommentAI on http://127.0.0.1:5000/products/
echo Login: user / user123
echo Press Ctrl+C to stop.
echo.

".venv\Scripts\waitress-serve.exe" --listen=127.0.0.1:5000 --threads=8 wsgi:app
pause
