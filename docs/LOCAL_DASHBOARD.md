# Fast HD Downloader — local-first v2 preview

This is an initial local-only CLI and responsive browser dashboard. No Google Cloud resources, paid hosting, or remote services are provisioned.

## Setup

Install Python 3.11+ and FFmpeg on PATH. Optional: aria2.

```powershell
python -m pip install -r requirements-web.txt
python fastdl.py
```

Open http://127.0.0.1:8765 if your browser does not launch automatically.

Direct CLI usage:

```powershell
python fastdl.py --audio "https://www.youtube.com/watch?v=YOUR_ID"
python fastdl.py --video "https://www.youtube.com/watch?v=YOUR_ID" --quality 720
```

This is **not yet a globally installed `fastdl` shell command**. Packaging a launcher is a separate step.

## Security boundaries

- Server binds only to 127.0.0.1; it is **not accessible from a phone** yet.
- URL host allowlist is intentionally limited to YouTube.
- One download at a time; status is held in memory.
- Do not bind this prototype to 0.0.0.0 or expose it to the public internet.
- Local browser access is unauthenticated. Mobile LAN support requires authentication, CSRF protection, origin checks, and a file-transfer design.
- Only download content you own or are authorized to save.

## Limitations

The local web preview is not a production release. It has not been tested on Windows here. It does not include pause/cancel, mobile file transfer, global command registration, or Cloud Run deployment. FFmpeg is required; aria2 is optional.
