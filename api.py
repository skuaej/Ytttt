import subprocess
import json
import time
import psutil
from fastapi import FastAPI, Query, HTTPException

app = FastAPI(title="Ultra-Low-CPU YouTube Streaming API")

YTDLP = "yt-dlp"
START_TIME = time.time()

# -------------------------
# UTILS
# -------------------------
def run(cmd, timeout=30):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout
    )

def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

# -------------------------
# BASIC
# -------------------------
@app.get("/")
def root():
    return {
        "service": "Ytttt Streaming API",
        "endpoints": [
            "/video",
            "/audio",
            "/video/qualities",
            "/playlist",
            "/stats",
            "/ping"
        ]
    }

@app.get("/ping")
def ping():
    return {"ping": "pong", "uptime": uptime()}

@app.get("/stats")
def stats():
    return {
        "uptime": uptime(),
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "ram_percent": psutil.virtual_memory().percent
    }

# -------------------------
# AUDIO (LINK ONLY)
# -------------------------
@app.get("/audio")
def audio(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--no-playlist",
        "-f", "bestaudio",
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    return {
        "type": "audio",
        "audio_url": p.stdout.strip()
    }

# -------------------------
# VIDEO STREAMING (NO DOWNLOAD)
# -------------------------
@app.get("/video")
def video(
    url: str = Query(...),
    quality: str = Query("best")
):
    """
    quality examples:
    2160p, 1440p, 1080p, 720p
    """

    if quality == "best":
        fmt = "best"
    else:
        height = quality.replace("p", "")
        fmt = f"bestvideo[height<={height}]/best"

    cmd = [
        YTDLP,
        "--no-playlist",
        "-f", fmt,
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    lines = p.stdout.strip().splitlines()

    # DASH (video + audio)
    if len(lines) == 2:
        return {
            "type": "dash",
            "quality": quality,
            "video_url": lines[0],
            "audio_url": lines[1]
        }

    # Progressive
    return {
        "type": "progressive",
        "quality": quality,
        "url": lines[0]
    }

# -------------------------
# VIDEO QUALITIES
# -------------------------
@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--no-playlist",
        "--dump-json",
        url
    ]

    p = run(cmd, timeout=60)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        if not f.get("height"):
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": f.get("url")
        })

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{max(f['height'] for f in formats)}p",
        "formats": formats
    }

# -------------------------
# PLAYLIST
# -------------------------
@app.get("/playlist")
def playlist(url: str = Query(...), limit: int = 50):
    cmd = [
        YTDLP,
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(min(limit, 300)),
        url
    ]

    p = run(cmd, timeout=120)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    videos = []
    for line in p.stdout.splitlines():
        v = json.loads(line)
        videos.append({
            "title": v.get("title"),
            "url": f"https://youtu.be/{v.get('id')}"
        })

    return {
        "count": len(videos),
        "videos": videos
    }
