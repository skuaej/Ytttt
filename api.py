import os
import json
import time
import psutil
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Ytttt – YouTube Merge API")

BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YTDLP = "yt-dlp"
FFMPEG = "ffmpeg"
START_TIME = time.time()


# -----------------------------
# UTILITIES
# -----------------------------
def run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"


def system_stats():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


# -----------------------------
# ROOT
# -----------------------------
@app.get("/")
async def root():
    return {
        "app": "Ytttt",
        "status": "running",
        "uptime": uptime(),
        "stats": system_stats(),
        "endpoints": [
            "/video?url=&quality=720p",
            "/video/qualities?url=",
            "/audio?url="
        ],
    }


# -----------------------------
# GET AVAILABLE QUALITIES
# -----------------------------
@app.get("/video/qualities")
async def video_qualities(url: str = Query(...)):
    cmd = [YTDLP, "--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)

    qualities = set()
    for f in info.get("formats", []):
        h = f.get("height")
        if h:
            qualities.add(f"{h}p")

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "available_qualities": sorted(
            qualities, key=lambda x: int(x.replace("p", ""))
        )
    }


# -----------------------------
# AUDIO ONLY
# -----------------------------
@app.get("/audio")
async def audio(url: str = Query(...)):
    out = os.path.join(DOWNLOAD_DIR, "audio.m4a")

    cmd = [
        YTDLP,
        "-f", "bestaudio[ext=m4a]/bestaudio",
        "-o", out,
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    return FileResponse(out, filename="audio.m4a", media_type="audio/mp4")


# -----------------------------
# VIDEO + AUDIO MERGED
# -----------------------------
@app.get("/video")
async def video(
    url: str = Query(...),
    quality: str = Query("best")
):
    video_file = os.path.join(DOWNLOAD_DIR, "video.mp4")
    audio_file = os.path.join(DOWNLOAD_DIR, "audio.m4a")
    output_file = os.path.join(DOWNLOAD_DIR, "output.mp4")

    # CLEAN OLD FILES
    for f in [video_file, audio_file, output_file]:
        if os.path.exists(f):
            os.remove(f)

    # FORMAT SELECTOR
    if quality == "best":
        fmt = "bestvideo+bestaudio/best"
    else:
        q = int(quality.replace("p", ""))
        fmt = f"bestvideo[height<={q}]+bestaudio/best"

    # DOWNLOAD VIDEO
    p1 = run([
        YTDLP,
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", output_file,
        url
    ])

    if p1.returncode != 0:
        return JSONResponse({"error": p1.stderr}, status_code=500)

    return FileResponse(
        output_file,
        filename=f"video_{quality}.mp4",
        media_type="video/mp4"
                             )
