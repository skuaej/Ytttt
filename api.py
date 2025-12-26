import os
import time
import psutil
import asyncio
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse

app = FastAPI(title="YT Stream API")

START_TIME = time.time()

# ==========================
# CONFIG
# ==========================
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
MAX_VIDEO_QUALITY = "360p"

# ==========================
# UTILS
# ==========================
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"


def load_level(cpu):
    if cpu < 40:
        return "LOW"
    elif cpu < 70:
        return "MEDIUM"
    return "HIGH"


# ==========================
# HEALTH / PING
# ==========================
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": ["/audio", "/video", "/status", "/ping"]
    }


@app.get("/ping")
async def ping():
    return {"ping": "pong", "uptime": uptime()}


# ==========================
# SERVER STATUS
# ==========================
@app.get("/status")
async def status():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()

    return {
        "cpu": {
            "usage_percent": cpu,
            "load_level": load_level(cpu)
        },
        "ram": {
            "total_mb": int(ram.total / 1024 / 1024),
            "used_mb": int(ram.used / 1024 / 1024),
            "usage_percent": ram.percent
        },
        "policy": {
            "video_allowed": cpu < 80,
            "max_video_quality": MAX_VIDEO_QUALITY
        }
    }


# ==========================
# AUDIO STREAM
# ==========================
@app.get("/audio")
async def audio(url: str = Query(...)):
    try:
        cmd = [
            YTDLP,
            "--cookies", COOKIES,
            "--remote-components", "ejs:github",
            "--force-ipv4",
            "-f", "bestaudio",
            "-g",
            url,
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20
        )

        stream = proc.stdout.strip()
        if not stream:
            return JSONResponse(
                {"status": "error", "reason": "audio_not_found"},
                status_code=500
            )

        return {
            "status": "success",
            "audio": stream
        }

    except Exception as e:
        return JSONResponse(
            {"status": "error", "reason": str(e)},
            status_code=500
        )


# ==========================
# VIDEO STREAM (360p)
# ==========================
@app.get("/video")
async def video(url: str = Query(...)):
    cpu = psutil.cpu_percent(interval=0.3)

    if cpu > 80:
        return JSONResponse(
            {"status": "blocked", "reason": "high_cpu"},
            status_code=503
        )

    try:
        cmd = [
            YTDLP,
            "--cookies", COOKIES,
            "--remote-components", "ejs:github",
            "--force-ipv4",
            "-f", "bv*[height<=360]+ba/b",
            "-g",
            url,
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=25
        )

        stream = proc.stdout.strip()
        if not stream:
            return JSONResponse(
                {"status": "error", "reason": "video_not_found"},
                status_code=500
            )

        return {
            "status": "success",
            "quality": "360p",
            "video": stream
        }

    except Exception as e:
        return JSONResponse(
            {"status": "error", "reason": str(e)},
            status_code=500
        )
