import os
import json
import time
import subprocess
import psutil
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import redis

# ---------------- CONFIG ----------------
APP_NAME = "Ytttt Ultra"
CACHE_TTL = 1800  # 30 minutes
COOKIES = "cookies.txt"
YTDLP = "yt-dlp"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ---------------- APP -------------------
app = FastAPI(title=APP_NAME)

# ---------------- REDIS -----------------
try:
    rdb = redis.from_url(REDIS_URL, decode_responses=True)
    rdb.ping()
    REDIS_OK = True
except Exception:
    rdb = {}
    REDIS_OK = False

# ---------------- UTILS -----------------
def run(cmd, timeout=30):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def cache_get(key):
    if REDIS_OK:
        return rdb.get(key)
    return rdb.get(key)

def cache_set(key, value):
    if REDIS_OK:
        rdb.setex(key, CACHE_TTL, value)
    else:
        rdb[key] = value

# ---------------- FORMAT CACHE -----------------
def fetch_formats(url: str):
    cache_key = f"formats:{url}"
    cached = cache_get(cache_key)
    if cached:
        return json.loads(cached)

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--dump-json",
        "--no-playlist",
        url
    ]
    p = run(cmd, timeout=40)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    info = json.loads(p.stdout)

    formats = []
    for f in info.get("formats", []):
        if f.get("protocol") != "m3u8_native":
            continue
        if f.get("acodec") == "none":
            continue

        formats.append({
            "height": f.get("height"),
            "quality": f"{f.get('height')}p",
            "url": f.get("manifest_url"),
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    payload = {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "formats": formats
    }

    cache_set(cache_key, json.dumps(payload))
    return payload

# ---------------- ROOT -----------------
@app.get("/")
def home():
    return {
        "app": APP_NAME,
        "cache": "redis" if REDIS_OK else "memory",
        "endpoints": [
            "/audio",
            "/video",
            "/video/qualities",
            "/stats"
        ]
    }

# ---------------- STATS -----------------
@app.get("/stats")
def stats():
    return {
        "cpu": psutil.cpu_percent(interval=0.3),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
        "cache": "redis" if REDIS_OK else "memory"
    }

# ---------------- AUDIO (DIRECT LINK ONLY) -----------------
@app.get("/audio")
def audio(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--no-playlist",
        "-f", "bestaudio",
        "-g",
        url
    ]
    p = run(cmd, timeout=20)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    return {
        "type": "audio",
        "direct_url": p.stdout.strip()
    }

# ---------------- VIDEO QUALITIES -----------------
@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    return fetch_formats(url)

# ---------------- VIDEO STREAM (QUALITY + AUTO FALLBACK) -----------------
@app.get("/video")
def video(
    url: str = Query(...),
    quality: str = Query("1080p")
):
    data = fetch_formats(url)

    target = int(quality.replace("p", ""))
    for f in data["formats"]:
        if f["height"] <= target:
            return JSONResponse({
                "selected_quality": f["quality"],
                "stream_url": f["url"]
            })

    # fallback to best available
    if data["formats"]:
        best = data["formats"][0]
        return JSONResponse({
            "selected_quality": best["quality"],
            "stream_url": best["url"]
        })

    raise HTTPException(404, "No stream available")
