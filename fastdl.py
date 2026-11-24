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

def runtime_options():
    deno = tool("deno")
    return {"js_runtimes": {"deno": {"path": deno}}} if deno else {"js_runtimes": {}}

def inspect_media(info):
    if info.get("availability") in ("premium_only", "subscriber_only", "needs_auth", "private"):
        raise ValueError("Restricted content: use the official authorized viewing service.")
    formats = info.get("formats") or []
    usable = [f for f in formats if not f.get("has_drm") and f.get("url")]
    if info.get("has_drm") is True or (formats and all(f.get("has_drm") for f in formats)):
        raise ValueError("DRM-protected content is not supported.")
    if not usable:
        raise ValueError("No downloadable formats found. Check access and the portable Deno runtime.")
    return sorted({f["height"] for f in usable if isinstance(f.get("height"), int) and f.get("vcodec") != "none"})

def explain_error(exc):
    msg = str(exc)
    lower = msg.lower()
    if "drm" in lower:
        return "DRM-protected content is not supported."
    if any(s in lower for s in ("purchase", "rent this", "paid content", "members-only", "premium-only")):
        return "Restricted content: use the official authorized viewing service."
    if "requested format" in lower or "no video formats" in lower:
        return "No matching format. Check available resolutions and whether portable Deno is present."
    return msg

def probe(url):
    check_url(url)
    with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "skip_download": True,
                          "retries": 0, "extractor_retries": 0, "socket_timeout": 20,
                          **runtime_options()}) as ydl:
        info = ydl.extract_info(url, download=False)
    return {"resolutions": inspect_media(info), "deno_available": bool(tool("deno"))}

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
        with lock:
            jobs[job_id]["status"] = "checking"
        metadata = probe(request.url)
        with lock:
            jobs[job_id].update(metadata)
        opts = {
            **runtime_options(),
            "extractor_retries": 0,
            "socket_timeout": 20,
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
            jobs[job_id].update(status="failed", error=explain_error(exc))

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (BASE / "web" / "index.html").read_text(encoding="utf-8")

@app.post("/api/formats")
def available_formats(req: Request):
    try:
        return probe(req.url)
    except Exception as exc:
        raise HTTPException(400, explain_error(exc))

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
    parser.add_argument("--list-formats", metavar="URL")
    parser.add_argument("--video", metavar="URL")
    parser.add_argument("--audio", metavar="URL")
    parser.add_argument("--quality", choices=list(QUALITIES), default="1080")
    parser.add_argument("--format", choices=sorted(FORMATS))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("url", nargs="?", help="Short form: fstdl URL")
    parser.add_argument("-a", action="store_true", help="Download audio from positional URL")
    parser.add_argument("-4k", dest="four_k", action="store_true")
    parser.add_argument("-hd", dest="hd", action="store_true")
    args = parser.parse_args()
    if args.url == "update":
        print("Check releases: https://github.com/Applicationz2/Fast-HD-Downloader/releases")
        return
    if args.url:
        if args.video or args.audio:
            parser.error("Use either positional URL or explicit --video/--audio")
        if args.a:
            args.audio = args.url
        else:
            args.video = args.url
    elif args.a or args.four_k or args.hd:
        parser.error("A URL is required with short download flags")
    if args.four_k and args.hd:
        parser.error("Choose -4k or -hd")
    if args.four_k:
        args.quality = "2160"
    elif args.hd:
        args.quality = "1080"
    if args.list_formats:
        try:
            print(json.dumps(probe(args.list_formats), indent=2))
        except Exception as exc:
            print(explain_error(exc), file=sys.stderr)
            raise SystemExit(1)
        return
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
