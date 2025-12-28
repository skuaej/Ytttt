import os, json, time, subprocess, psutil
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Ytttt Stable API")

YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
START_TIME = time.time()

# ---------------- UTILS ----------------

def run(cmd, timeout=60):
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None

def uptime():
    return int(time.time() - START_TIME)

# ---------------- ROOT ----------------

@app.get("/")
def root():
    return {
        "status": "running",
        "endpoints": [
            "/audio",
            "/video",
            "/video/qualities",
            "/playlist",
            "/download",
            "/stats"
        ]
    }

# ---------------- STATS ----------------

@app.get("/stats")
def stats():
    return {
        "uptime_sec": uptime(),
        "cpu": psutil.cpu_percent(interval=0.3),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
    }

# ---------------- AUDIO (SAFE) ----------------

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

    p = run(cmd, timeout=60)
    if not p:
        raise HTTPException(504, "Audio extraction timeout (YouTube slow)")

    if p.returncode != 0 or not p.stdout.strip():
        raise HTTPException(500, p.stderr or "Audio URL not found")

    return {
        "type": "audio",
        "direct_url": p.stdout.strip()
    }

# ---------------- VIDEO (QUALITY + FALLBACK) ----------------

@app.get("/video")
def video(
    url: str = Query(...),
    quality: str = Query("1080p")
):
    max_h = int(quality.replace("p", ""))

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--no-playlist",
        "-f", f"bestvideo[height<={max_h}]+bestaudio/best",
        "-g",
        url
    ]

    p = run(cmd, timeout=60)
    if not p:
        raise HTTPException(504, "Video extraction timeout")

    if p.returncode != 0 or not p.stdout.strip():
        raise HTTPException(500, p.stderr or "Video URL not found")

    return {
        "quality": quality,
        "stream_url": p.stdout.strip()
    }

# ---------------- VIDEO QUALITIES ----------------

@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--dump-json",
        "--no-playlist",
        url
    ]

    p = run(cmd, timeout=60)
    if not p:
        raise HTTPException(504, "Metadata timeout")

    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            formats.append({
                "height": f.get("height"),
                "quality": f"{f.get('height')}p",
                "url": f.get("manifest_url")
            })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "formats": formats
    }

# ---------------- PLAYLIST ----------------

@app.get("/playlist")
def playlist(url: str = Query(...), limit: int = 50):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(limit),
        url
    ]

    p = run(cmd, timeout=90)
    if not p:
        raise HTTPException(504, "Playlist timeout")

    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    entries = []
    for line in p.stdout.splitlines():
        v = json.loads(line)
        entries.append({
            "title": v.get("title"),
            "url": f"https://youtu.be/{v.get('id')}"
        })

    return {
        "count": len(entries),
        "videos": entries
    }

# ---------------- DOWNLOAD (OPTIONAL) ----------------

@app.get("/download")
def download(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", "best",
        "-g",
        url
    ]

    p = run(cmd, timeout=60)
    if not p:
        raise HTTPException(504, "Download link timeout")

    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    return {
        "direct_download_url": p.stdout.strip()
    }
