import osimport time
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


# ---------------import subprocess
import json
import time
import psutil
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="YT Stream API (Stable)")

YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
START_TIME = time.time()


# --------------------
# Utils
# --------------------
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"


def run(cmd, timeout=60):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )


def base_cmd():
    cmd = [
        YTDLP,
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0",
        "--remote-components", "ejs:github",
        "--dump-json"
    ]
    if COOKIES:
        cmd += ["--cookies", COOKIES]
    return cmd


# --------------------
# Health
# --------------------
@app.get("/")
def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": [
            "/ping",
            "/status",
            "/audio",
            "/video",
            "/video/qualities"
        ]
    }


@app.get("/ping")
def ping():
    return {"ping": "pong", "uptime": uptime()}


@app.get("/status")
def status():
    cpu = psutil.cpu_percent(interval=0.4)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "disk_percent": disk.percent
    }


# --------------------
# AUDIO (SAFE)
# --------------------
@app.get("/audio")
def audio(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", "bestaudio",
        "-g",
        url
    ]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "type": "audio",
        "url": p.stdout.strip()
    }


# --------------------
# VIDEO (SAFE STREAM)
# m3u8 ONLY — WITH AUDIO
# --------------------
@app.get("/video")
def video(
    url: str = Query(...),
    quality: str = Query("best")
):
    # Map quality → m3u8 itags
    quality_map = {
        "144p": "91",
        "240p": "92",
        "360p": "93",
        "480p": "94",
        "720p": "95",
        "1080p": "96"
    }

    itag = quality_map.get(quality, "best")

    fmt = f"{itag}/best[protocol^=m3u8]/best"

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", fmt,
        "-g",
        url
    ]

    p = run(cmd)

    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "type": "video",
        "quality": quality,
        "stream": p.stdout.strip()
    }


# --------------------
# VIDEO QUALITIES LIST
# (INCLUDES m3u8 + DASH)
# --------------------
@app.get("/video/qualities")
def video_qualities(url: str = Query(...)):
    p = run(base_cmd() + [url], timeout=90)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        if not f.get("url"):
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "resolution": f.get("resolution"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "is_m3u8": "m3u8" in (f.get("protocol") or ""),
            "url": f.get("url")
        })

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "total_formats": len(formats),
        "formats": formats
    }----------
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
