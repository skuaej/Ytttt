import json
import subprocess
import redis
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse, JSONResponse

app = FastAPI(title="Ytttt API + Redis Cache")

COOKIES = "cookies.txt"
REDIS_URL = "redis://localhost:6379"
CACHE_TTL = 60  # seconds

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# ------------------------
# Helpers
# ------------------------

def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def fetch_info(url: str):
    cache_key = f"yt:{url}"
    cached = r.get(cache_key)

    if cached:
        return json.loads(cached)

    p = run([
        "yt-dlp",
        "--cookies", COOKIES,
        "--no-warnings",
        "--dump-json",
        url
    ])

    if p.returncode != 0:
        raise Exception(p.stderr)

    info = json.loads(p.stdout)

    # ❗ Strip direct URLs before caching
    for f in info.get("formats", []):
        f.pop("url", None)
        f.pop("manifest_url", None)

    r.setex(cache_key, CACHE_TTL, json.dumps(info))
    return info

def fetch_live_info(url: str):
    p = run([
        "yt-dlp",
        "--cookies", COOKIES,
        "--no-warnings",
        "--dump-json",
        url
    ])
    if p.returncode != 0:
        raise Exception(p.stderr)
    return json.loads(p.stdout)

# ------------------------
# Root
# ------------------------

@app.get("/")
def home():
    return {
        "status": "running",
        "cache": "redis",
        "endpoints": [
            "/video",
            "/video.m3u8",
            "/audio",
            "/audio.m3u8",
            "/video/qualities",
            "/playlist"
        ]
    }

# ------------------------
# VIDEO (progressive)
# ------------------------

@app.get("/video")
def video(url: str, quality: str | None = None):
    info = fetch_live_info(url)

    vids = [
        f for f in info["formats"]
        if f.get("url")
        and f.get("vcodec") != "none"
        and f.get("protocol") != "m3u8_native"
    ]

    if quality:
        q = int(quality.replace("p", ""))
        vids.sort(key=lambda f: abs((f.get("height") or 0) - q))
    else:
        vids.sort(key=lambda f: f.get("height") or 0, reverse=True)

    return RedirectResponse(vids[0]["url"])

# ------------------------
# VIDEO HLS
# ------------------------

@app.get("/video.m3u8")
def video_m3u8(url: str, quality: str | None = None):
    info = fetch_live_info(url)

    hls = [
        f for f in info["formats"]
        if f.get("protocol") == "m3u8_native"
        and f.get("acodec") != "none"
    ]

    if not hls:
        return JSONResponse({"error": "No HLS video"}, status_code=404)

    if quality:
        q = int(quality.replace("p", ""))
        hls.sort(key=lambda f: abs((f.get("height") or 0) - q))
    else:
        hls.sort(key=lambda f: f.get("height") or 0, reverse=True)

    return RedirectResponse(hls[0]["manifest_url"])

# ------------------------
# AUDIO
# ------------------------

@app.get("/audio")
def audio(url: str):
    info = fetch_live_info(url)
    aud = [f for f in info["formats"] if f.get("vcodec") == "none" and f.get("url")]
    aud.sort(key=lambda f: f.get("abr") or 0, reverse=True)
    return RedirectResponse(aud[0]["url"])

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    info = fetch_live_info(url)
    for f in info["formats"]:
        if f.get("protocol") == "m3u8_native" and f.get("vcodec") == "none":
            return RedirectResponse(f["manifest_url"])
    return JSONResponse({"error": "No audio HLS"}, status_code=404)

# ------------------------
# VIDEO QUALITIES
# ------------------------

@app.get("/video/qualities")
def video_qualities(url: str):
    info = fetch_live_info(url)
    out = []

    for f in info["formats"]:
        stream = f.get("manifest_url") or f.get("url")
        if not stream:
            continue
        out.append({
            "height": f.get("height"),
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "has_audio": f.get("acodec") != "none",
            "is_hls": f.get("protocol") == "m3u8_native",
            "url": stream
        })

    out.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "formats": out
    }

# ------------------------
# PLAYLIST
# ------------------------

@app.get("/playlist")
def playlist(url: str):
    p = run([
        "yt-dlp",
        "--cookies", COOKIES,
        "--flat-playlist",
        "--dump-json",
        url
    ])

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "entries": [json.loads(line) for line in p.stdout.splitlines()]
    }
