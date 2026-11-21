# Fast HD Downloader — Windows 11

A CustomTkinter desktop app using yt-dlp, FFmpeg and optional aria2. Download only media you own or have permission to save, consistent with applicable platform terms.

## Install on Windows 11

1. Install Python 3.11+ from python.org. Enable **Add Python to PATH** and the Python launcher.
2. Open PowerShell and install FFmpeg: `winget install Gyan.FFmpeg`.
3. Optionally install aria2: `winget install aria2.aria2`.
4. Restart PowerShell/IDLE after installing external programs.
5. Extract this ZIP and double-click `run_windows.bat` to install Python dependencies and launch the app.

If `py` is unavailable, replace `py` with `python` in the BAT files.

## Build the Windows EXE

Double-click `build_exe.bat`. The output is `dist\FastHDDownloader.exe`.
You must build the EXE **on Windows**. The EXE includes Python and Python packages, but **does not bundle FFmpeg or aria2**. Install them on target PCs, or place `ffmpeg.exe`, `ffprobe.exe`, and optionally `aria2c.exe` beside the EXE. FFmpeg binaries must be obtained from their legitimate distributors, subject to their licenses.

The EXE is not code-signed; Windows SmartScreen may show an unrecognized-app warning. Only run software you trust.

## Features

- MP4/MKV video and MP3/M4A audio
- Best available, 4K, 1440p, 1080p, 720p, 480p caps
- Silent download engine with real-time GUI progress
- Optional aria2 HTTP acceleration; yt-dlp concurrent fragment downloads
- Cancel, retry, and resume support (where server permits)
- Configurable output folder

## Notes

- Selected quality is a **maximum**; the actual video depends on source availability.
- MP4/MKV conversion may take additional time. MP4 conversion cannot improve the original image quality.
- When aria2 is used, its progress may not be reported by yt-dlp's hooks continuously. The progress bar may pause and then jump; downloading continues in the background.
- Cancellation during an external aria2/FFmpeg process may take time to finish; use the cancel button and wait.
- Some videos may require account authorization, may be DRM protected, or may not be available to download. This app does not bypass DRM.
- Speed depends on the host and network. More connections are not always faster.
