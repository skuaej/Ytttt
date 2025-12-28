import json
import time
import subprocess
import shutil
import psutil
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse

app = FastAPI(title="Ytttt API", version="2.0.0")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ===============================
# CONFIG — YOU CAN EDIT THIS
# ===============================

QUALITY_FALLBACK = [
    4320,  # 8K
    2160,  # 4K
    1440,  # 2K
    1080,
    720,
    480,
    360,
    240,
    144
]

# ===============================
# HELPERS
# ===============================

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
        "--user-agent", "Mozilla/5.0",
        "--dump-json"
    ]

# ===============================
# ROOT / INFO
# ===============================

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

# ===============================
# STATS
# ===============================

@app.get("/stats")
def stats():
    return {
        "ping_ms": round(time.time() * 1000) % 1000,
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent
    }

# ===============================
# AUDIO
# ===============================

@app.get("/audio")
def audio(url: str):
    p = run(base_cmd() + [url])
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    for f in info["formats"]:
        if f.get("acodec") != "none" and f.get("vcodec") == "none":
            return RedirectResponse(f["url"])

    return JSONResponse({"error": "No audio found"}, 404)

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    p = run(base_cmd() + [url])
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    for f in info["formats"]:
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No audio m3u8 found"}, 404)

# ===============================
# VIDEO (QUALITY + AUTO FALLBACK)
# ===============================

@app.get("/video")
def video(url: str, quality: str = "best"):
    p = run(base_cmd() + [url])
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)

    videos = [
        f for f in info["formats"]
        if f.get("vcodec") != "none" and f.get("url")
    ]

    if not videos:
        return JSONResponse({"error": "No video found"}, 404)

    # BEST
    if quality == "best":
        videos.sort(key=lambda x: x.get("height") or 0, reverse=True)
        return RedirectResponse(videos[0]["url"])

    # parse quality like 2160p
    try:
        requested = int(quality.replace("p", ""))
    except:
        return JSONResponse({"error": "Invalid quality"}, 400)

    # auto fallback
    for q in QUALITY_FALLBACK:
        if q > requested:
            continue
        for v in videos:
            if v.get("height") == q:
                return RedirectResponse(v["url"])

    # final fallback
    videos.sort(key=lambda x: x.get("height") or 0, reverse=True)
    return RedirectResponse(videos[0]["url"])

# ===============================
# VIDEO M3U8 (WITH AUDIO)
# ===============================

@app.get("/video.m3u8")
def video_m3u8(url: str):
    p = run(base_cmd() + [url])
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    for f in info["formats"]:
        if (
            f.get("protocol") == "m3u8_native"
            and f.get("acodec") != "none"
        ):
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No video m3u8 found"}, 404)

# ===============================
# VIDEO QUALITIES LIST
# ===============================

@app.get("/video/qualities")
def video_qualities(url: str):
    p = run(base_cmd() + [url])
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    formats = []

    for f in info["formats"]:
        stream_url = f.get("manifest_url") or f.get("url")
        if not stream_url:
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": stream_url
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{formats[0]['height']}p" if formats else None,
        "formats": formats
    }

# ===============================
# PLAYLIST
# ===============================

@app.get("/playlist")
def playlist(url: str):
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        url
    ]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    entries = [json.loads(line) for line in p.stdout.splitlines()]
    return {"entries": entries}

# ===============================
# DOWNLOAD (OPTIONAL)
# ===============================

@app.get("/download")
def download(url: str, format_id: str = "best"):
    out = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    cmd = [
        "yt-dlp",
        "--cookies", "cookies.txt",
        "-f", format_id,
        "-o", out,
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    files = sorted(
        os.scandir(DOWNLOAD_DIR),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    return FileResponse(files[0].path, filename=files[0].name) 
