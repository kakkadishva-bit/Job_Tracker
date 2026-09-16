@echo off
echo ==========================================
echo  PreciousMetals AI - Investment Platform
echo ==========================================
echo.
echo Starting server on http://localhost:5000
echo Press Ctrl+C to stop
echo.
cd /d "%~dp0"
python app.py
pause