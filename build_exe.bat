@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed & pause & exit /b 1)
py -m PyInstaller --noconfirm --clean --onefile --windowed --name FastHDDownloader --collect-all customtkinter --collect-all yt_dlp app.py
if errorlevel 1 (echo EXE build failed & pause & exit /b 1)
echo.
echo EXE created: %~dp0dist\FastHDDownloader.exe
echo FFmpeg is required at runtime. aria2 is optional.
echo Install with: winget install Gyan.FFmpeg
pause
