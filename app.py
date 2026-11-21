"""Fast HD Downloader — Windows desktop application."""
from __future__ import annotations

import os
import queue
import shutil
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from urllib.parse import urlparse

import customtkinter as ctk
import yt_dlp
from yt_dlp.utils import DownloadCancelled

APP_NAME = "Fast HD Downloader"
QUALITY = {"Best available": None, "4K (2160p)": 2160, "1440p": 1440,
           "1080p": 1080, "720p": 720, "480p": 480}
FORMATS = ("MP4", "MKV", "MP3", "M4A")


def find_binary(name: str) -> str | None:
    """Look beside the EXE, in PyInstaller bundle, then on PATH."""
    exe = name + (".exe" if os.name == "nt" else "")
    roots = [Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
             else Path(__file__).resolve().parent]
    if getattr(sys, "_MEIPASS", None):
        roots.append(Path(sys._MEIPASS))
    for root in roots:
        for candidate in (root / exe, root / "bin" / exe):
            if candidate.is_file():
                return str(candidate)
    return shutil.which(name)


def valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class FastHDApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_NAME)
        self.geometry("750x580")
        self.minsize(660, 530)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.last_ui_update = 0.0

        self.url_var = ctk.StringVar()
        self.quality_var = ctk.StringVar(value="1080p")
        self.format_var = ctk.StringVar(value="MP4")
        self.accel_var = ctk.BooleanVar(value=True)
        self.folder_var = ctk.StringVar(value=str(Path.home() / "Downloads" / "YouTube"))
        self.status_var = ctk.StringVar(value="Ready")
        self.detail_var = ctk.StringVar(value="Paste a URL to begin")

        self._build_ui()
        self.after(100, self._process_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=25, pady=20)
        ctk.CTkLabel(main, text="Fast HD Downloader", font=ctk.CTkFont(size=27, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(main, text="Download videos you own or have permission to save", text_color="gray70").pack(anchor="w", pady=(1, 19))

        ctk.CTkLabel(main, text="Video URL", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.url_entry = ctk.CTkEntry(main, textvariable=self.url_var, height=40,
                                       placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.pack(fill="x", pady=(5, 15))

        controls = ctk.CTkFrame(main, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 12))
        controls.grid_columnconfigure((0, 1), weight=1, uniform="controls")
        ctk.CTkLabel(controls, text="Quality", anchor="w").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(controls, text="Format", anchor="w").grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.quality_menu = ctk.CTkOptionMenu(controls, values=list(QUALITY), variable=self.quality_var, height=37)
        self.quality_menu.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.format_menu = ctk.CTkOptionMenu(controls, values=list(FORMATS), variable=self.format_var,
                                             command=self._format_changed, height=37)
        self.format_menu.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.accel_switch = ctk.CTkSwitch(main, text="Use aria2 acceleration when available", variable=self.accel_var)
        self.accel_switch.pack(anchor="w", pady=(2, 15))

        ctk.CTkLabel(main, text="Save to", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        folder_row = ctk.CTkFrame(main, fg_color="transparent")
        folder_row.pack(fill="x", pady=(5, 15))
        self.folder_entry = ctk.CTkEntry(folder_row, textvariable=self.folder_var, height=37)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.browse_button = ctk.CTkButton(folder_row, text="Browse", width=92, command=self._browse)
        self.browse_button.pack(side="left")

        progress_frame = ctk.CTkFrame(main)
        progress_frame.pack(fill="x", pady=(0, 15))
        self.status_label = ctk.CTkLabel(progress_frame, textvariable=self.status_var,
                                         font=ctk.CTkFont(size=15, weight="bold"))
        self.status_label.pack(anchor="w", padx=15, pady=(13, 5))
        self.progress = ctk.CTkProgressBar(progress_frame, height=13)
        self.progress.pack(fill="x", padx=15, pady=(0, 8))
        self.progress.set(0)
        self.detail_label = ctk.CTkLabel(progress_frame, textvariable=self.detail_var, text_color="gray70", anchor="w")
        self.detail_label.pack(fill="x", padx=15, pady=(0, 13))

        buttons = ctk.CTkFrame(main, fg_color="transparent")
        buttons.pack(fill="x")
        self.download_button = ctk.CTkButton(buttons, text="Download", height=42, command=self._start)
        self.download_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.cancel_button = ctk.CTkButton(buttons, text="Cancel", height=42, width=110,
                                           fg_color="#a33d3d", hover_color="#812c2c",
                                           state="disabled", command=self._cancel)
        self.cancel_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Open folder", height=42, width=110,
                      fg_color="#444b56", hover_color="#353b45", command=self._open_folder).pack(side="left")
        ctk.CTkLabel(main, text="Requires yt-dlp and FFmpeg; aria2 is optional. Available resolutions depend on the source.",
                     text_color="gray60", wraplength=650).pack(anchor="w", pady=(16, 0))

    def _format_changed(self, fmt: str):
        if fmt in ("MP3", "M4A"):
            self.quality_menu.configure(state="disabled")
        else:
            self.quality_menu.configure(state="normal")

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() if Path(self.folder_var.get()).exists() else str(Path.home()))
        if folder:
            self.folder_var.set(folder)

    def _open_folder(self):
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(folder)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Folder error", str(exc))

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        url = self.url_var.get().strip()
        if not valid_url(url):
            messagebox.showwarning("Invalid URL", "Enter a complete https:// video URL.")
            return
        fmt = self.format_var.get()
        if not find_binary("ffmpeg"):
            messagebox.showerror("FFmpeg missing", "Install FFmpeg or place ffmpeg.exe beside the app.\n\nwinget install Gyan.FFmpeg")
            return
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Folder error", str(exc))
            return
        self.stop_event.clear()
        self.progress.set(0)
        self.status_var.set("Starting download...")
        self.detail_var.set("Connecting to server")
        self.download_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.worker = threading.Thread(target=self._download_worker,
                                       args=(url, fmt, self.quality_var.get(), folder, self.accel_var.get()),
                                       daemon=True)
        self.worker.start()

    def _cancel(self):
        self.stop_event.set()
        self.status_var.set("Cancelling...")
        self.cancel_button.configure(state="disabled")

    def _progress_hook(self, data):
        if self.stop_event.is_set():
            raise DownloadCancelled("Cancelled by user")
        status = data.get("status")
        if status == "downloading":
            now = time.monotonic()
            if now - self.last_ui_update < 0.18:
                return
            self.last_ui_update = now
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            done = data.get("downloaded_bytes", 0)
            ratio = min(done / total, 1.0) if total else 0.0
            speed = data.get("speed")
            eta = data.get("eta")
            self.events.put(("progress", (ratio, speed, eta, bool(total))))
        elif status == "finished":
            self.events.put(("status", "Processing / merging media..."))

    def _download_worker(self, url, fmt, quality, folder, accelerate):
        try:
            height = QUALITY[quality]
            if fmt in ("MP3", "M4A"):
                format_selector = "bestaudio/best"
            elif height is None:
                format_selector = "bv*+ba/b"
            else:
                format_selector = f"bv*[height<={height}]+ba/b[height<={height}]"

            opts = {
                "format": format_selector,
                "outtmpl": str(folder / "%(title).180B [%(id)s].%(ext)s"),
                "noplaylist": True,
                "windowsfilenames": True,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "retries": 8,
                "fragment_retries": 8,
                "socket_timeout": 25,
                "continuedl": True,
                "concurrent_fragment_downloads": 8,
                "progress_hooks": [self._progress_hook],
                "ffmpeg_location": find_binary("ffmpeg"),
                "overwrites": False,
            }
            if fmt in ("MP3", "M4A"):
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": fmt.lower(),
                    "preferredquality": "192" if fmt == "MP3" else "0",
                }]
            else:
                opts["merge_output_format"] = fmt.lower()
                # Recode only if necessary: ensure the requested container.
                opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": fmt.lower()}]

            aria = find_binary("aria2c") if accelerate else None
            if aria:
                opts["external_downloader"] = {"http": aria, "https": aria}
                opts["external_downloader_args"] = {
                    "aria2c": ["-x", "8", "-s", "8", "-k", "1M",
                               "--file-allocation=none", "--summary-interval=0",
                               "--console-log-level=error"]
                }
                self.events.put(("status", "Downloading with aria2..."))
            else:
                self.events.put(("status", "Downloading..."))
            with yt_dlp.YoutubeDL(opts) as ydl:
                result = ydl.download([url])
            if self.stop_event.is_set():
                self.events.put(("cancelled", None))
            elif result == 0:
                self.events.put(("done", str(folder)))
            else:
                self.events.put(("error", "yt-dlp reported a download failure."))
        except DownloadCancelled:
            self.events.put(("cancelled", None))
        except Exception as exc:
            if self.stop_event.is_set():
                self.events.put(("cancelled", None))
            else:
                self.events.put(("error", str(exc)))

    def _process_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    ratio, speed, eta, has_total = payload
                    self.progress.set(ratio if has_total else 0)
                    speed_text = f"{speed / (1024 * 1024):.2f} MiB/s" if speed else "—"
                    eta_text = f"{int(eta)} s" if eta is not None else "—"
                    self.status_var.set(f"Downloading... {ratio * 100:.1f}%" if has_total else "Downloading...")
                    self.detail_var.set(f"Speed: {speed_text}    |    ETA: {eta_text}")
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind in ("done", "error", "cancelled"):
                    self.download_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    if kind == "done":
                        self.progress.set(1)
                        self.status_var.set("Download completed")
                        self.detail_var.set(f"Saved in: {payload}")
                    elif kind == "cancelled":
                        self.status_var.set("Download cancelled")
                        self.detail_var.set("Partial files may remain for resuming later")
                    else:
                        self.status_var.set("Download failed")
                        self.detail_var.set("See error dialog")
                        messagebox.showerror("Download failed", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Download in progress", "Cancel the current download and exit?"):
                return
            self.stop_event.set()
        self.destroy()


if __name__ == "__main__":
    FastHDApp().mainloop()
