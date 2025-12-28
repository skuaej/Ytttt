import os
import json
import time
import psutil
import shutil
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse

APP_START = time.time()
DOWNLOAD_DIR = "downloads"
COOKIES = "cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = FastAPI(title="Ytttt – YouTube Audio/Video API")

# ---------------- UTILS ----------------

def uptime():
    s = int(time.time() - APP_START)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def ytdlp_base():
    cmd = [
        "yt-dlp",
        "--remote-components", "ejs:github",
        "--force-ipv4",
        "--no-playlist"
    ]
    if os.path.exists(COOKIES):
        cmd += ["--cookies", COOKIES]
    return cmd

# ---------------- HEALTH ----------------

@app.get("/")
def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "app": "Ytttt"
    }

@app.get("/ping")
def ping():
    return {"ping": "pong"}

@app.get("/stats")
def stats():
    disk = shutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_used_gb": round(disk.used / 1024**3, 2),
        "disk_total_gb": round(disk.total / 1024**3, 2)
    }

# ---------------- AUDIO ----------------

@app.get("/audio")
def audio(url: str):
    cmd = ytdlp_base() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)
    return {"audio_url": p.stdout.strip()}

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    cmd = ytdlp_base() + ["-f", "bestaudio", "--hls-use-mpegts", "-g", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)
    return {"m3u8": p.stdout.strip()}

# ---------------- VIDEO ----------------

@app.get("/video")
def video(url: str):
    cmd = ytdlp_base() + ["-f", "bestvideo+bestaudio/best", "-g", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)
    return {"video_url": p.stdout.strip()}

@app.get("/video.m3u8")
def video_m3u8(url: str):
    cmd = ytdlp_base() + ["-f", "best", "--hls-use-mpegts", "-g", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)
    return {"m3u8": p.stdout.strip()}

# ---------------- QUALITIES ----------------

@app.get("/video/qualities")
def qualities(url: str):
    cmd = ytdlp_base() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue
        formats.append({
            "format_id": f.get("format_id"),
            "quality": f.get("format_note"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": f.get("url")
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f'{formats[0]["height"]}p' if formats else None,
        "formats": formats
    }

# ---------------- DOWNLOAD ----------------

@app.get("/download")
def download(url: str, quality: str = "best"):
    out = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    cmd = ytdlp_base() + [
        "-f", quality,
        "-o", out,
        url
    ]
    p = run(cmd, timeout=0)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    files = os.listdir(DOWNLOAD_DIR)
    if not files:
        return JSONResponse({"error": "Download failed"}, 500)

    file_path = os.path.join(DOWNLOAD_DIR, files[-1])
    return FileResponse(file_path, filename=os.path.basename(file_path))
