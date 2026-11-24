"""Local-only CLI and browser dashboard for Fast HD Downloader."""
import argparse
import json
import shutil
import sys
import threading
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Fast HD Downloader", docs_url=None, redoc_url=None)
jobs = {}
lock = threading.Lock()
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
BIN = Path(sys.executable).resolve().parent / "bin" if getattr(sys, "frozen", False) else BASE / "bin"
def tool(name):
    local = BIN / (name + ".exe")
    return str(local) if local.is_file() else shutil.which(name)

DEST = Path.home() / "Downloads" / "FastHDDownloader"
QUALITIES = {"best": None, "2160": 2160, "1440": 1440, "1080": 1080, "720": 720, "480": 480}
FORMATS = {"mp4", "mkv", "mp3", "m4a"}

def check_url(value):
    p = urlparse(value)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("A valid public HTTP(S) media URL is required")
    host = p.hostname.lower().rstrip(".")
    if host not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"):
        raise ValueError("Only YouTube URLs are supported in this local dashboard")
    return value

class Request(BaseModel):
    url: str = Field(max_length=2048)
    quality: str = "1080"
    format: str = "mp4"

def run_download(job_id, request):
    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            with lock:
                jobs[job_id].update(
                    status="downloading",
                    percent=round(100 * d.get("downloaded_bytes", 0) / total, 1) if total else 0,
                    speed=d.get("speed"),
                    eta=d.get("eta"),
                )
        elif d.get("status") == "finished":
            with lock:
                jobs[job_id]["status"] = "processing"
    try:
        DEST.mkdir(parents=True, exist_ok=True)
        fmt, quality = request.format, request.quality
        height = QUALITIES[quality]
        selector = ("bestaudio/best" if fmt in ("mp3", "m4a")
                    else "bv*+ba/b" if height is None
                    else f"bv*[height<={height}]+ba/b[height<={height}]")
        opts = {
            "format": selector,
            "outtmpl": str(DEST / "%(title).180B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "windowsfilenames": True,
            "concurrent_fragment_downloads": 8,
            "retries": 5,
            "fragment_retries": 5,
            "progress_hooks": [hook],
        }
        opts["ffmpeg_location"] = str(BIN) if (BIN / "ffmpeg.exe").is_file() else (tool("ffmpeg") or "ffmpeg")
        if fmt in ("mp3", "m4a"):
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": fmt,
                                        "preferredquality": "192" if fmt == "mp3" else "0"}]
        else:
            opts["merge_output_format"] = fmt
            opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": fmt}]
        if tool("aria2c"):
            opts["external_downloader"] = {"http": tool("aria2c"), "https": tool("aria2c")}
            opts["external_downloader_args"] = {"aria2c": ["-x", "8", "-s", "8", "-k", "1M", "--console-log-level=error"]}
        with yt_dlp.YoutubeDL(opts) as ydl:
            code = ydl.download([request.url])
        with lock:
            jobs[job_id].update(status="completed" if code == 0 else "failed", percent=100 if code == 0 else jobs[job_id]["percent"])
    except Exception as exc:
        with lock:
            jobs[job_id].update(status="failed", error=str(exc))

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (BASE / "web" / "index.html").read_text(encoding="utf-8")

@app.post("/api/download")
def download(req: Request):
    try:
        check_url(req.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if req.quality not in QUALITIES or req.format not in FORMATS:
        raise HTTPException(400, "Unsupported quality or format")
    if not tool("ffmpeg"):
        raise HTTPException(503, "FFmpeg is required and must be available on PATH")
    with lock:
        if sum(j["status"] not in ("completed", "failed") for j in jobs.values()) >= 1:
            raise HTTPException(429, "One download at a time")
        job_id = uuid.uuid4().hex
        jobs[job_id] = {"status": "queued", "percent": 0, "speed": None, "eta": None, "error": None}
    threading.Thread(target=run_download, args=(job_id, req), daemon=True).start()
    return {"id": job_id}

@app.get("/api/jobs/{job_id}")
def status(job_id: str):
    with lock:
        if job_id not in jobs:
            raise HTTPException(404, "Job not found")
        return dict(jobs[job_id])

def main():
    parser = argparse.ArgumentParser(description="Fast HD Downloader local dashboard")
    parser.add_argument("--video", metavar="URL")
    parser.add_argument("--audio", metavar="URL")
    parser.add_argument("--quality", choices=list(QUALITIES), default="1080")
    parser.add_argument("--format", choices=sorted(FORMATS))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.video and args.audio:
        parser.error("Choose --video or --audio, not both")
    if args.video or args.audio:
        req = Request(url=args.video or args.audio, quality=args.quality,
                      format=args.format or ("mp3" if args.audio else "mp4"))
        check_url(req.url)
        if not tool("ffmpeg"):
            parser.error("FFmpeg must be on PATH")
        job_id = uuid.uuid4().hex
        jobs[job_id] = {"status": "queued", "percent": 0, "speed": None, "eta": None, "error": None}
        run_download(job_id, req)
        print(json.dumps(jobs[job_id], indent=2))
        raise SystemExit(0 if jobs[job_id]["status"] == "completed" else 1)
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)

if __name__ == "__main__":
    main()
