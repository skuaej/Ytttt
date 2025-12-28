import os
import time
import json
import uuid
import shutil
import subprocess
import psutil

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse

APP_DIR = os.getcwd()
DOWNLOAD_DIR = f"{APP_DIR}/downloads"
COOKIE_FILE = f"{APP_DIR}/cookies.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = FastAPI(title="Ytttt API", version="1.0.0")


# -----------------------
# UTIL FUNCTIONS
# -----------------------
def run(cmd):
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if p.returncode != 0:
        raise Exception(p.stderr)
    return p.stdout


def yt_formats(url: str):
    cmd = [
        "yt-dlp",
        "--cookies", COOKIE_FILE,
        "-J",
        url
    ]
    out = run(cmd)
    return json.loads(out)


# -----------------------
# HEALTH / STATS
# -----------------------
@app.get("/ping")
def ping():
    return {
        "status": "ok",
        "uptime_sec": int(time.time() - psutil.boot_time()),
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent
    }


# -----------------------
# VIDEO QUALITIES
# -----------------------
@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    info = yt_formats(url)

    formats = []
    for f in info["formats"]:
        if f.get("vcodec") != "none":
            formats.append({
                "format_id": f["format_id"],
                "ext": f["ext"],
                "resolution": f.get("resolution"),
                "fps": f.get("fps"),
                "filesize": f.get("filesize"),
                "has_audio": f.get("acodec") != "none",
                "protocol": f.get("protocol")
            })

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "formats": formats
    }


# -----------------------
# HLS VIDEO (WITH AUDIO)
# -----------------------
@app.get("/video.m3u8")
def video_hls(url: str = Query(...)):
    cmd = [
        "yt-dlp",
        "--cookies", COOKIE_FILE,
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--hls-use-mpegts",
        "-g",
        url
    ]
    out = run(cmd)
    return {"hls_url": out.strip()}


# -----------------------
# HLS AUDIO
# -----------------------
@app.get("/audio.m3u8")
def audio_hls(url: str = Query(...)):
    cmd = [
        "yt-dlp",
        "--cookies", COOKIE_FILE,
        "-f", "ba",
        "-g",
        url
    ]
    out = run(cmd)
    return {"audio_url": out.strip()}


# -----------------------
# DOWNLOAD (MERGED)
# -----------------------
@app.get("/download")
def download(
    url: str = Query(...),
    quality: str = Query("best")
):
    file_id = str(uuid.uuid4())
    out_file = f"{DOWNLOAD_DIR}/{file_id}.mp4"

    format_map = {
        "144p": "bv*[height<=144]+ba/b",
        "240p": "bv*[height<=240]+ba/b",
        "360p": "bv*[height<=360]+ba/b",
        "480p": "bv*[height<=480]+ba/b",
        "720p": "bv*[height<=720]+ba/b",
        "1080p": "bv*[height<=1080]+ba/b",
        "1440p": "bv*[height<=1440]+ba/b",
        "2160p": "bv*[height<=2160]+ba/b",
        "best": "bv*+ba/b"
    }

    fmt = format_map.get(quality, format_map["best"])

    cmd = [
        "yt-dlp",
        "--cookies", COOKIE_FILE,
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", out_file,
        url
    ]

    run(cmd)

    return FileResponse(
        out_file,
        media_type="video/mp4",
        filename=os.path.basename(out_file)
    )
