import os
import json
import time
import shutil
import psutil
import subprocess
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Ytttt Streaming API")

START_TIME = time.time()
YTDLP = "yt-dlp"
FFMPEG = "ffmpeg"
COOKIES = "cookies.txt"
DOWNLOADS = "downloads"

os.makedirs(DOWNLOADS, exist_ok=True)

# -------------------------
# UTILS
# -------------------------
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def stats():
    disk = shutil.disk_usage("/")
    return {
        "uptime": uptime(),
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_free_gb": round(disk.free / 1024**3, 2),
    }

# -------------------------
# BASIC
# -------------------------
@app.get("/")
def root():
    return {
        "name": "Ytttt",
        "status": "running",
        "endpoints": [
            "/audio",
            "/audio.m3u8",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/playlist",
            "/download",
            "/stats",
            "/ping",
        ],
    }

@app.get("/ping")
def ping():
    return {"ping": "pong", "uptime": uptime()}

@app.get("/stats")
def server_stats():
    return stats()

# -------------------------
# AUDIO (BEST FOR TELEGRAM)
# -------------------------
@app.get("/audio")
def audio(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", "bestaudio",
        "-g",
        url,
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)
    return {"audio": p.stdout.strip()}

# -------------------------
# AUDIO HLS (STREAMING)
# -------------------------
@app.get("/audio.m3u8")
def audio_hls(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", "bestaudio",
        "--hls-use-mpegts",
        "-g",
        url,
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)
    return {"audio_m3u8": p.stdout.strip()}

# -------------------------
# VIDEO (MERGED → SOUND FIXED)
# -------------------------
@app.get("/video")
def video(url: str = Query(...)):
    out = os.path.join(DOWNLOADS, f"video_{int(time.time())}.mp4")

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", out,
        url,
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    return FileResponse(out, media_type="video/mp4", filename="video.mp4")

# -------------------------
# VIDEO HLS (SABR SAFE)
# -------------------------
@app.get("/video.m3u8")
def video_hls(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", "bv*+ba/b",
        "--hls-use-mpegts",
        "-g",
        url,
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    return {"video_m3u8": p.stdout.strip()}

# -------------------------
# ALL VIDEO QUALITIES
# -------------------------
@app.get("/video/qualities")
def qualities(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--dump-json",
        url,
    ]
    p = run(cmd, timeout=120)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue
        formats.append({
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": f.get("url"),
        })

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "formats": formats,
    }

# -------------------------
# PLAYLIST SUPPORT
# -------------------------
@app.get("/playlist")
def playlist(url: str = Query(...), limit: int = 50):
    limit = min(limit, 300)

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--dump-json",
        "--flat-playlist",
        "--playlist-end", str(limit),
        url,
    ]

    p = run(cmd, timeout=180)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    videos = []
    for line in p.stdout.splitlines():
        v = json.loads(line)
        videos.append({
            "title": v.get("title"),
            "url": f"https://youtu.be/{v.get('id')}",
        })

    return {"count": len(videos), "videos": videos}

# -------------------------
# DOWNLOAD (ANY QUALITY)
# -------------------------
@app.get("/download")
def download(url: str = Query(...), quality: str = "best"):
    out = os.path.join(DOWNLOADS, f"download_{int(time.time())}.mp4")

    fmt = "bv*+ba/b" if quality == "best" else f"bv*[height<={quality.replace('p','')}] + ba"

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", out,
        url,
    ]

    p = run(cmd, timeout=600)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    return FileResponse(out, media_type="video/mp4", filename="video.mp4")
