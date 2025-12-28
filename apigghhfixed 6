import json
import time
import subprocess
import shutil
import psutil
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse

app = FastAPI(title="Ytttt API", version="1.0.0")

DOWNLOAD_DIR = "downloads"
shutil.os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# -------------------------
# Helpers
# -------------------------

def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def base_cmd():
    return [
        "yt-dlp",
        "--no-warnings",
        "--cookies", "cookies.txt",
        "--user-agent", "Mozilla/5.0"
    ]

# -------------------------
# Health / Stats
# -------------------------

@app.get("/")
def home():
    return {
        "app": "Ytttt",
        "status": "running",
        "endpoints": [
            "/stats",
            "/audio",
            "/audio.m3u8",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/playlist",
            "/download"
        ]
    }

@app.get("/stats")
def stats():
    return {
        "ping_ms": round(psutil.cpu_times().idle, 2),
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent
    }

# -------------------------
# AUDIO
# -------------------------

@app.get("/audio")
def audio(url: str):
    cmd = base_cmd() + [
        "-f", "bestaudio",
        "--dump-json",
        url
    ]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    return RedirectResponse(info["url"])

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    cmd = base_cmd() + [
        "-f", "bestaudio",
        "--dump-json",
        url
    ]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No audio m3u8 found"}, status_code=404)

# -------------------------
# VIDEO (AUTO BEST)
# -------------------------

@app.get("/video")
def video(url: str):
    cmd = base_cmd() + [
        "-f", "best",
        "--dump-json",
        url
    ]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    return RedirectResponse(info["url"])

@app.get("/video.m3u8")
def video_m3u8(url: str):
    cmd = base_cmd() + [
        "--dump-json",
        url
    ]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No video m3u8 found"}, status_code=404)

# -------------------------
# VIDEO QUALITIES (FIXED)
# -------------------------

@app.get("/video/qualities")
def video_qualities(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        stream_url = (
            f.get("manifest_url")
            if f.get("protocol") == "m3u8_native"
            else f.get("url")
        )

        if not stream_url:
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "height": f.get("height"),
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "is_hls": f.get("protocol") == "m3u8_native",
            "url": stream_url
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{formats[0]['height']}p" if formats else None,
        "formats": formats
    }

# -------------------------
# PLAYLIST
# -------------------------

@app.get("/playlist")
def playlist(url: str):
    cmd = base_cmd() + [
        "--flat-playlist",
        "--dump-json",
        url
    ]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    items = []
    for line in p.stdout.splitlines():
        items.append(json.loads(line))

    return {"entries": items}

# -------------------------
# DOWNLOAD (VPS MODE)
# -------------------------

@app.get("/download")
def download(url: str, format_id: str = "best"):
    out = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    cmd = base_cmd() + [
        "-f", format_id,
        "-o", out,
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    files = list(shutil.os.scandir(DOWNLOAD_DIR))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    return FileResponse(
        files[0].path,
        filename=files[0].name
    )
