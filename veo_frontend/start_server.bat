@echo off
echo ========================================
echo    VeoVision Frontend - Quick Start
echo ========================================
echo.
echo Starting local web server (range support)...
echo.
echo Once started, open your browser to:
echo http://localhost:5600/veo_frontend/
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

cd /d "%~dp0"
cd ..
python start_video_server.py

pause

