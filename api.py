import json
import subprocess
import hashlib
import redis
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse, JSONResponse

app = FastAPI(title="Ytttt Ultra-Fast API")

# ---------------- CONFIG ----------------
REDIS_HOST = "localhost"
REDIS_PORT = 6379
CACHE_TTL = 300  # 5 minutes

rdb = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

# ---------------- HELPERS ----------------
def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def cache_key(prefix: str, url: str, quality: str = ""):
    raw = f"{prefix}:{url}:{quality}"
    return hashlib.md5(raw.encode()).hexdigest()

def ytdlp_json(url: str):
    cmd = [
        "yt-dlp",
        "--cookies", "cookies.txt",
        "--no-warnings",
        "--dump-json",
        url
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise Exception(p.stderr)
    return json.loads(p.stdout)

# ---------------- HOME ----------------
@app.get("/")
def home():
    return {
        "app": "Ytttt",
        "endpoints": [
            "/video",
            "/video?quality=1080p",
            "/video/qualities",
            "/audio"
        ],
        "cache": "Redis enabled"
    }

# ---------------- VIDEO QUALITIES ----------------
@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    key = cache_key("qualities", url)
    cached = rdb.get(key)
    if cached:
        return json.loads(cached)

    info = ytdlp_json(url)

    formats = []
    for f in info.get("formats", []):
        stream = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")
        if not stream:
            continue
        formats.append({
            "format_id": f.get("format_id"),
            "height": f.get("height"),
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "is_hls": f.get("protocol") == "m3u8_native",
            "url": stream
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    data = {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{formats[0]['height']}p" if formats else None,
        "formats": formats
    }

    rdb.setex(key, CACHE_TTL, json.dumps(data))
    return data

# ---------------- VIDEO WITH QUALITY + AUTO FALLBACK ----------------
@app.get("/video")
def video(
    url: str = Query(...),
    quality: str = Query(None)  # ex: 2160p, 1080p
):
    key = cache_key("video", url, quality or "best")
    cached = rdb.get(key)
    if cached:
        return RedirectResponse(cached)

    info = ytdlp_json(url)

    wanted_height = int(quality.replace("p", "")) if quality else None
    best = None

    for f in info.get("formats", []):
        if f.get("acodec") == "none":
            continue
        if wanted_height and f.get("height") == wanted_height:
            best = f
            break

    if not best:
        for f in reversed(info.get("formats", [])):
            if f.get("acodec") != "none":
                best = f
                break

    if not best or not best.get("url"):
        return JSONResponse({"error": "No playable format"}, status_code=404)

    rdb.setex(key, CACHE_TTL, best["url"])
    return RedirectResponse(best["url"])

# ---------------- AUDIO (BEST) ----------------
@app.get("/audio")
def audio(url: str = Query(...)):
    key = cache_key("audio", url)
    cached = rdb.get(key)
    if cached:
        return RedirectResponse(cached)

    info = ytdlp_json(url)

    for f in info.get("formats", []):
        if f.get("vcodec") == "none" and f.get("url"):
            rdb.setex(key, CACHE_TTL, f["url"])
            return RedirectResponse(f["url"])

    return JSONResponse({"error": "No audio found"}, status_code=404)
