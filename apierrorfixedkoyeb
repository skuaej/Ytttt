
# ==================================
# YouTube Stream API (VC Compatible)
# Audio + Video (360p)
# ==================================

import time
import psutil
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse

app = FastAPI(title="YT Stream API", version="1.0")

START_TIME = time.time()

# =====================
# CONFIG
# =====================
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"     # cookies required
MAX_VIDEO_HEIGHT = 360     # FIXED for VC
CPU_LIMIT = 85             # block above this

# =====================
# UTILS
# =====================
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

def run_yt_dlp(cmd: list, timeout: int = 20):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

# =====================
# ROOT / HEALTH
# =====================
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": [
            "/audio?url=",
            "/video?url=",
            "/status",
            "/ping"
        ]
    }

@app.get("/ping")
async def ping():
    return {"ping": "pong", "uptime": uptime()}

@app.get("/status")
async def status():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()

    return {
        "cpu": {
            "usage_percent": cpu,
            "load": load_level(cpu)
        },
        "ram": {
            "total_mb": int(ram.total / 1024 / 1024),
            "used_mb": int(ram.used / 1024 / 1024),
            "usage_percent": ram.percent
        },
        "policy": {
            "video_allowed": cpu < CPU_LIMIT,
            "max_video": f"{MAX_VIDEO_HEIGHT}p"
        }
    }

# =====================
# AUDIO STREAM
# =====================
@app.get("/audio")
async def audio(url: str = Query(...)):
    try:
        cmd = [
            YTDLP,
            "--cookies", COOKIES,
            "--force-ipv4",
            "--no-playlist",
            "-f", "bestaudio",
            "-g",
            url
        ]

        proc = run_yt_dlp(cmd)

        stream = proc.stdout.strip()
        if not stream:
            return JSONResponse(
                {"status": "error", "reason": proc.stderr},
                status_code=500
            )

        # 🔥 Redirect = fastest for bot
        return RedirectResponse(stream, status_code=302)

    except Exception as e:
        return JSONResponse(
            {"status": "error", "reason": str(e)},
            status_code=500
        )

# =====================
# VIDEO STREAM (360p)
# =====================
@app.get("/video")
async def video(url: str = Query(...)):
    cpu = psutil.cpu_percent(interval=0.3)

    if cpu > CPU_LIMIT:
        return JSONResponse(
            {"status": "blocked", "reason": "high_cpu"},
            status_code=503
        )

    try:
        cmd = [
            YTDLP,
            "--cookies", COOKIES,
            "--force-ipv4",
            "--no-playlist",
            "-f", f"bv*[height<={MAX_VIDEO_HEIGHT}][ext=mp4]+ba/b",
            "-g",
            url
        ]

        proc = run_yt_dlp(cmd)

        stream = proc.stdout.strip()
        if not stream:
            return JSONResponse(
                {"status": "error", "reason": proc.stderr},
                status_code=500
            )

        # 🔥 Redirect is REQUIRED for pytgcalls
        return RedirectResponse(stream, status_code=302)

    except Exception as e:
        return JSONResponse(
            {"status": "error", "reason": str(e)},
            status_code=500
        )
