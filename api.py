import json
import time
import subprocess
import os
import shutil
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse

app = FastAPI(title="Ytttt Ultra-Fast API", version="2.0")

# -------------------------
# CONFIG
# -------------------------
COOKIES = "cookies.txt"
DOWNLOAD_DIR = "downloads"
CACHE_TTL = 300  # 5 minutes

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

CACHE = {}

# -------------------------
# UTILS
# -------------------------
def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def yt_cmd():
    return [
        "yt-dlp",
        "--no-warnings",
        "--cookies", COOKIES,
        "--user-agent", "Mozilla/5.0",
        "--extractor-args", "youtube:player_client=tv,web",
        "--extractor-args", "youtube:skip=dash",
        "--no-playlist",
        "--dump-json"
    ]

def get_cache(url):
    c = CACHE.get(url)
    if not c:
        return None
    if time.time() - c["time"] > CACHE_TTL:
        del CACHE[url]
        return None
    return c["info"]

def set_cache(url, info):
    CACHE[url] = {"time": time.time(), "info": info}

def fetch_info(url):
    cached = get_cache(url)
    if cached:
        return cached

    p = run(yt_cmd() + [url])
    if p.returncode != 0:
        raise Exception(p.stderr)

    info = json.loads(p.stdout)
    set_cache(url, info)
    return info

def pick_quality(formats, wanted_height):
    formats = sorted(
        formats,
        key=lambda f: f.get("height") or 0,
        reverse=True
    )

    for f in formats:
        if f.get("height") == wanted_height and f.get("acodec") != "none":
            return f

    for f in formats:
        if f.get("height") and f.get("height") < wanted_height and f.get("acodec") != "none":
            return f

    return formats[0] if formats else None

# -------------------------
# ROOT
# -------------------------
@app.get("/")
def root():
    return {
        "app": "Ytttt Ultra-Fast",
        "status": "running",
        "endpoints": [
            "/audio",
            "/video",
            "/video/qualities",
            "/playlist",
            "/download"
        ]
    }

# -------------------------
# AUDIO (BEST)
# -------------------------
@app.get("/audio")
def audio(url: str):
    info = fetch_info(url)

    for f in info["formats"]:
        if f.get("acodec") != "none" and f.get("vcodec") == "none":
            return RedirectResponse(f["url"], headers={"User-Agent": "Mozilla/5.0"})

    return JSONResponse({"error": "No audio found"}, status_code=404)

# -------------------------
# VIDEO (QUALITY + AUTO FALLBACK)
# -------------------------
@app.get("/video")
def video(
    url: str,
    quality: str = Query("1080p", description="Example: 720p, 1080p, 2160p")
):
    wanted_height = int(quality.replace("p", ""))
    info = fetch_info(url)

    formats = [
        f for f in info["formats"]
        if f.get("protocol") in ("https", "m3u8_native")
    ]

    selected = pick_quality(formats, wanted_height)
    if not selected:
        return JSONResponse({"error": "No video found"}, status_code=404)

    stream_url = selected.get("manifest_url") or selected.get("url")
    return RedirectResponse(stream_url, headers={"User-Agent": "Mozilla/5.0"})

# -------------------------
# VIDEO QUALITIES LIST
# -------------------------
@app.get("/video/qualities")
def video_qualities(url: str):
    info = fetch_info(url)
    items = []

    for f in info["formats"]:
        if not f.get("height"):
            continue

        items.append({
            "format_id": f.get("format_id"),
            "quality": f"{f.get('height')}p",
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": f.get("manifest_url") or f.get("url")
        })

    items.sort(key=lambda x: int(x["quality"].replace("p", "")), reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": items[0]["quality"] if items else None,
        "formats": items
    }

# -------------------------
# PLAYLIST
# -------------------------
@app.get("/playlist")
def playlist(url: str):
    p = run([
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        url
    ])

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "entries": [json.loads(line) for line in p.stdout.splitlines()]
    }

# -------------------------
# DOWNLOAD (VPS MODE)
# -------------------------
@app.get("/download")
def download(
    url: str,
    quality: str = Query("best", description="best / 720p / 1080p / 2160p")
):
    fmt = "best"
    if quality != "best":
        height = quality.replace("p", "")
        fmt = f"bestvideo[height<={height}]+bestaudio/best"

    out = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"

    p = run([
        "yt-dlp",
        "--cookies", COOKIES,
        "-f", fmt,
        "-o", out,
        url
    ])

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    files = sorted(
        os.scandir(DOWNLOAD_DIR),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    return FileResponse(files[0].path, filename=files[0].name)
