import os
import json
import time
import psutil
import subprocess
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import RedirectResponse, FileResponse

app = FastAPI(title="Ytttt Streaming API", version="2.0")

YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
DOWNLOADS = "downloads"

os.makedirs(DOWNLOADS, exist_ok=True)
START_TIME = time.time()

# ------------------------
# UTILS
# ------------------------
def run(cmd, timeout=120):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def yt_json(url):
    cmd = [YTDLP, "--cookies", COOKIES, "--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)
    return json.loads(p.stdout)

# ------------------------
# ROOT / STATS
# ------------------------
@app.get("/")
def root():
    return {
        "app": "Ytttt",
        "status": "running",
        "endpoints": [
            "/video",
            "/video.m3u8",
            "/audio",
            "/audio.m3u8",
            "/video/qualities",
            "/playlist",
            "/download",
            "/stats",
        ]
    }

@app.get("/stats")
def stats():
    return {
        "uptime": uptime(),
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "disk_free_gb": round(psutil.disk_usage('/').free / 1024**3, 2),
    }

# ------------------------
# AUDIO (STREAM ONLY)
# ------------------------
@app.get("/audio")
def audio(url: str):
    cmd = [
        YTDLP, "--cookies", COOKIES,
        "-f", "bestaudio",
        "-g", url
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)
    return RedirectResponse(p.stdout.strip())

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    info = yt_json(url)
    for f in info["formats"]:
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            return RedirectResponse(f["manifest_url"])
    raise HTTPException(404, "No audio HLS found")

# ------------------------
# VIDEO STREAM (NO DOWNLOAD)
# ------------------------
@app.get("/video")
def video(
    url: str,
    quality: str = "best"   # 2160p / 1080p / 720p / best
):
    info = yt_json(url)
    target = None

    wanted = None
    if quality != "best":
        wanted = int(quality.replace("p", ""))

    # Prefer HLS with audio
    formats = sorted(
        info["formats"],
        key=lambda x: x.get("height") or 0,
        reverse=True
    )

    for f in formats:
        if f.get("protocol") != "m3u8_native":
            continue
        if f.get("acodec") == "none":
            continue
        if wanted and f.get("height", 0) > wanted:
            continue
        target = f
        break

    # Fallback: best progressive
    if not target:
        for f in formats:
            if f.get("url") and f.get("acodec") != "none":
                target = f
                break

    if not target:
        raise HTTPException(404, "No playable stream found")

    return RedirectResponse(
        target.get("manifest_url") or target.get("url")
    )

# ------------------------
# VIDEO HLS ONLY
# ------------------------
@app.get("/video.m3u8")
def video_m3u8(
    url: str,
    quality: str = "best"
):
    info = yt_json(url)
    wanted = None
    if quality != "best":
        wanted = int(quality.replace("p", ""))

    formats = sorted(
        info["formats"],
        key=lambda x: x.get("height") or 0,
        reverse=True
    )

    for f in formats:
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            if wanted and f.get("height", 0) > wanted:
                continue
            return RedirectResponse(f["manifest_url"])

    raise HTTPException(404, "No HLS stream found")

# ------------------------
# VIDEO QUALITIES (FULL LIST)
# ------------------------
@app.get("/video/qualities")
def video_qualities(url: str):
    info = yt_json(url)
    out = []

    for f in info["formats"]:
        stream = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")
        if not stream:
            continue

        out.append({
            "format_id": f.get("format_id"),
            "height": f.get("height"),
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "is_hls": f.get("protocol") == "m3u8_native",
            "url": stream,
        })

    out.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{out[0]['height']}p" if out else None,
        "formats": out,
    }

# ------------------------
# PLAYLIST
# ------------------------
@app.get("/playlist")
def playlist(url: str, limit: int = 50):
    cmd = [
        YTDLP, "--cookies", COOKIES,
        "--flat-playlist",
        "--playlist-end", str(min(limit, 300)),
        "--dump-json", url
    ]
    p = run(cmd, timeout=180)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    vids = []
    for line in p.stdout.splitlines():
        j = json.loads(line)
        vids.append({
            "title": j.get("title"),
            "url": f"https://youtu.be/{j.get('id')}"
        })

    return {"count": len(vids), "videos": vids}

# ------------------------
# DOWNLOAD (ONLY HERE)
# ------------------------
@app.get("/download")
def download(url: str, quality: str = "best"):
    q = "bestvideo+bestaudio/best"
    if quality != "best":
        q = f"bv*[height<={quality.replace('p','')}] + ba"

    out = f"{DOWNLOADS}/%(title)s.%(ext)s"

    cmd = [
        YTDLP, "--cookies", COOKIES,
        "-f", q,
        "--merge-output-format", "mp4",
        "-o", out,
        url
    ]
    p = run(cmd, timeout=600)
    if p.returncode != 0:
        raise HTTPException(500, p.stderr)

    files = sorted(
        os.listdir(DOWNLOADS),
        key=lambda x: os.path.getmtime(os.path.join(DOWNLOADS, x)),
        reverse=True
    )

    return FileResponse(
        os.path.join(DOWNLOADS, files[0]),
        filename=files[0]
    )
