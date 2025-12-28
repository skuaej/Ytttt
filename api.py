import time
import json
import subprocess
import shutil
import psutil
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, FileResponse

# ======================================================
# APP
# ======================================================
app = FastAPI(title="Ytttt – YouTube Streaming & Download API")

# ======================================================
# CONFIG (AUTO)
# ======================================================
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

START_TIME = time.time()

# ======================================================
# UTILS
# ======================================================
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=None):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

def base_cmd():
    return [
        YTDLP,
        "--cookies", COOKIES,
        "--remote-components", "ejs:github",
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0"
    ]

# ======================================================
# SYSTEM STATS
# ======================================================
def system_stats():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage("/")

    return {
        "cpu": {
            "usage_percent": cpu,
            "cores": psutil.cpu_count(logical=True)
        },
        "ram": {
            "total_mb": round(ram.total / 1024 / 1024),
            "used_mb": round(ram.used / 1024 / 1024),
            "free_mb": round(ram.available / 1024 / 1024),
            "usage_percent": ram.percent
        },
        "storage": {
            "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
            "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
            "free_gb": round(disk.free / 1024 / 1024 / 1024, 2)
        }
    }

# ======================================================
# ROOT
# ======================================================
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": [
            "/ping",
            "/status",
            "/audio",
            "/audio.m3u8",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/playlist",
            "/download"
        ]
    }

# ======================================================
# PING
# ======================================================
@app.get("/ping")
async def ping():
    return {
        "status": "ok",
        "uptime": uptime(),
        "timestamp": int(time.time())
    }

# ======================================================
# STATUS (CPU / RAM / DISK)
# ======================================================
@app.get("/status")
async def status():
    return {
        "app": "Ytttt",
        "uptime": uptime(),
        "system": system_stats()
    }

# ======================================================
# AUDIO (DIRECT)
# ======================================================
@app.get("/audio")
async def audio(url: str = Query(...)):
    cmd = base_cmd() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {"type": "audio", "url": p.stdout.strip()}

# ======================================================
# AUDIO HLS
# ======================================================
@app.get("/audio.m3u8")
async def audio_m3u8(url: str = Query(...)):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    audio = [
        f for f in info["formats"]
        if f.get("protocol") == "m3u8_native"
        and f.get("vcodec") == "none"
    ]

    if not audio:
        return JSONResponse({"error": "No HLS audio"}, status_code=404)

    best = max(audio, key=lambda x: x.get("tbr", 0))
    return {"type": "audio", "format": "hls", "url": best["url"]}

# ======================================================
# VIDEO (MP4)
# ======================================================
@app.get("/video")
async def video(url: str, quality: str | None = None):
    if quality:
        h = int(quality.replace("p", ""))
        fmt = f"b[ext=mp4][height<={h}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + ["-f", fmt, "-g", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "type": "video",
        "format": "mp4",
        "quality": quality or "best",
        "url": p.stdout.strip()
    }

# ======================================================
# VIDEO HLS
# ======================================================
@app.get("/video.m3u8")
async def video_m3u8(url: str, quality: str | None = None):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    videos = [
        f for f in info["formats"]
        if f.get("protocol") == "m3u8_native"
        and f.get("vcodec") != "none"
    ]

    if quality:
        h = int(quality.replace("p", ""))
        videos = [f for f in videos if f.get("height") == h]

    if not videos:
        return JSONResponse({"error": "No HLS video"}, status_code=404)

    best = max(videos, key=lambda x: x.get("height", 0))
    return {
        "type": "video",
        "format": "hls",
        "quality": f"{best.get('height')}p",
        "url": best["url"]
    }

# ======================================================
# VIDEO QUALITIES
# ======================================================
@app.get("/video/qualities")
async def video_qualities(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    formats = []

    for f in info["formats"]:
        if not f.get("url"):
            continue
        formats.append({
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "is_hls": f.get("protocol") == "m3u8_native",
            "url": f.get("url")
        })

    formats.sort(key=lambda x: x["quality"] or "", reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "total_formats": len(formats),
        "formats": formats
    }

# ======================================================
# PLAYLIST
# ======================================================
@app.get("/playlist")
async def playlist(url: str):
    cmd = base_cmd() + ["--flat-playlist", "--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    videos = [
        {
            "title": json.loads(line).get("title"),
            "url": f"https://youtu.be/{json.loads(line).get('id')}"
        }
        for line in p.stdout.splitlines()
    ]

    return {"total": len(videos), "videos": videos}

# ======================================================
# DOWNLOAD (UP TO 8K)
# ======================================================
@app.get("/download")
async def download(url: str, quality: str | None = None):
    if quality:
        h = int(quality.replace("p", ""))
        fmt = f"bv*[height<={h}]+ba/best"
    else:
        fmt = "bestvideo+bestaudio/best"

    output = DOWNLOAD_DIR / "%(title)s_%(height)sp.%(ext)s"

    cmd = base_cmd() + [
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", str(output),
        url
    ]

    p = run(cmd, timeout=None)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    file = max(DOWNLOAD_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime)

    return FileResponse(file, filename=file.name)
