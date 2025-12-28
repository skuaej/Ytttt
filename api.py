import json
import subprocess
import hashlib
import redis
import psutil
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from pathlib import Path

# =====================
# CONFIG
# =====================

REDIS_URL = "redis://localhost:6379"
CACHE_TTL = 60  # seconds
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="UltraFast YT API", version="3.0")

rdb = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# =====================
# HELPERS
# =====================

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
        "--dump-json",
        "--no-warnings",
        "--cookies", "cookies.txt",
        "--user-agent", "Mozilla/5.0"
    ]

def cache_key(url):
    return "yt:" + hashlib.md5(url.encode()).hexdigest()

def fetch_info(url: str):
    key = cache_key(url)
    cached = rdb.get(key)
    if cached:
        return json.loads(cached)

    p = run(base_cmd() + [url])
    if p.returncode != 0:
        raise Exception(p.stderr)

    info = json.loads(p.stdout)
    rdb.setex(key, CACHE_TTL, json.dumps(info))
    return info

def pick_best_quality(formats, target_height):
    formats = [f for f in formats if f.get("height")]
    formats.sort(key=lambda x: x["height"], reverse=True)

    for f in formats:
        if f["height"] <= target_height:
            return f

    return formats[0] if formats else None

# =====================
# ROOT
# =====================

@app.get("/")
def home():
    return {
        "status": "running",
        "endpoints": [
            "/stats",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/audio",
            "/audio.m3u8",
            "/playlist",
            "/download"
        ]
    }

# =====================
# STATS
# =====================

@app.get("/stats")
def stats():
    return {
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
    }

# =====================
# VIDEO (QUALITY + FALLBACK)
# =====================

@app.get("/video")
def video(
    url: str,
    quality: str = "1080p"
):
    target = int(quality.replace("p", ""))

    info = fetch_info(url)

    formats = []
    for f in info.get("formats", []):
        stream = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")
        if not stream:
            continue
        formats.append({**f, "stream": stream})

    selected = pick_best_quality(formats, target)
    if not selected:
        return JSONResponse({"error": "No playable format"}, 404)

    return RedirectResponse(selected["stream"])

# =====================
# VIDEO M3U8 ONLY
# =====================

@app.get("/video.m3u8")
def video_m3u8(
    url: str,
    quality: str = "1080p"
):
    target = int(quality.replace("p", ""))

    info = fetch_info(url)

    hls = [
        f for f in info.get("formats", [])
        if f.get("protocol") == "m3u8_native" and f.get("height")
    ]

    selected = pick_best_quality(hls, target)
    if not selected:
        return JSONResponse({"error": "No HLS found"}, 404)

    return RedirectResponse(selected["manifest_url"])

# =====================
# VIDEO QUALITIES
# =====================

@app.get("/video/qualities")
def video_qualities(url: str):
    info = fetch_info(url)

    formats = []
    for f in info.get("formats", []):
        if not f.get("height"):
            continue

        stream = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")
        if not stream:
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "height": f.get("height"),
            "quality": f"{f.get('height')}p",
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "is_hls": f.get("protocol") == "m3u8_native",
            "url": stream
        })

    formats.sort(key=lambda x: x["height"], reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": formats[0]["quality"] if formats else None,
        "formats": formats
    }

# =====================
# AUDIO
# =====================

@app.get("/audio")
def audio(url: str):
    info = fetch_info(url)

    for f in info.get("formats", []):
        if f.get("acodec") != "none" and f.get("vcodec") == "none":
            return RedirectResponse(f["url"])

    return JSONResponse({"error": "No audio"}, 404)

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    info = fetch_info(url)

    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native" and f.get("vcodec") == "none":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No audio HLS"}, 404)

# =====================
# PLAYLIST
# =====================

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

    return {
        "entries": [json.loads(line) for line in p.stdout.splitlines()]
    }

# =====================
# DOWNLOAD
# =====================

@app.get("/download")
def download(
    url: str,
    quality: str = "best"
):
    out = DOWNLOAD_DIR / "%(title)s.%(ext)s"

    cmd = [
        "yt-dlp",
        "-f", quality,
        "-o", str(out),
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    files = sorted(DOWNLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    return FileResponse(files[0], filename=files[0].name)
