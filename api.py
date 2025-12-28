import os
import time
import uuid
import psutil
import subprocess
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Ytttt API")

DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# -------------------------
# SYSTEM STATS
# -------------------------
@app.get("/stats")
def stats():
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "uptime_seconds": int(time.time() - psutil.boot_time()),
    }


# -------------------------
# GET VIDEO QUALITIES
# -------------------------
@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    cmd = [
        "yt-dlp",
        "-F",
        "--cookies", COOKIES_FILE,
        "--no-warnings",
        url
    ]

    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, e.output.decode())

    return {
        "url": url,
        "formats_raw": out
    }


# -------------------------
# STREAM (MERGED AUDIO+VIDEO)
# -------------------------
@app.get("/video")
def stream_video(
    url: str,
    quality: str = "best"
):
    stream_id = str(uuid.uuid4())
    out_file = f"{DOWNLOAD_DIR}/{stream_id}.mp4"

    # bestvideo+bestaudio MERGE (audio FIX)
    format_selector = (
        f"bestvideo[height<={quality.replace('p','')}]+bestaudio/best"
        if quality != "best"
        else "bestvideo+bestaudio/best"
    )

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "-f", format_selector,
        "--merge-output-format", "mp4",
        "-o", out_file,
        url
    ]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        raise HTTPException(500, "Failed to stream video")

    return FileResponse(out_file, media_type="video/mp4")


# -------------------------
# AUDIO ONLY
# -------------------------
@app.get("/audio")
def audio_only(url: str):
    audio_id = str(uuid.uuid4())
    out_file = f"{DOWNLOAD_DIR}/{audio_id}.mp3"

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "-f", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "-o", out_file,
        url
    ]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        raise HTTPException(500, "Audio extraction failed")

    return FileResponse(out_file, media_type="audio/mpeg")


# -------------------------
# DOWNLOAD VIDEO (USER FILE)
# -------------------------
@app.get("/download")
def download(
    url: str,
    quality: str = "best"
):
    file_id = str(uuid.uuid4())
    out_file = f"{DOWNLOAD_DIR}/{file_id}.mp4"

    format_selector = (
        f"bestvideo[height<={quality.replace('p','')}]+bestaudio/best"
        if quality != "best"
        else "bestvideo+bestaudio/best"
    )

    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "-f", format_selector,
        "--merge-output-format", "mp4",
        "-o", out_file,
        url
    ]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        raise HTTPException(500, "Download failed")

    return FileResponse(
        out_file,
        filename="video.mp4",
        media_type="application/octet-stream"
    )


# -------------------------
# HEALTH CHECK
# -------------------------
@app.get("/")
def root():
    return {
        "service": "Ytttt",
        "status": "running"
    }
