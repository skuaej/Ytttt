# api.py — yt-dlp with Deno + yt-dlp-ejs (NO Node.js)
# Requirements:
#   pipx install yt-dlp yt-dlp-ejs
#   deno installed and on PATH
#   cookies.txt optional (same directory)

import time
import psutil
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="YT Stream API (EJS + Deno)")

START_TIME = time.time()
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"

def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

@app.get("/")
async def root():
    return {"status": "running", "uptime": uptime(), "endpoints": ["/audio", "/video", "/status", "/ping"]}

@app.get("/ping")
async def ping():
    return {"ping": "pong"}

@app.get("/status")
async def status():
    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    return {"cpu": cpu, "ram_mb": int(ram.used/1024/1024), "uptime": uptime()}

def base_args():
    return [
        YTDLP,
        "--remote-components", "ejs:github",   # enable EJS (Deno)
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0",
    ] + (["--cookies", COOKIES] if COOKIES else [])

@app.get("/audio")
async def audio(url: str = Query(...)):
    cmd = base_args() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"status": "error", "stderr": p.stderr}, status_code=500)
    return {"status": "success", "audio": p.stdout.strip()}

@app.get("/video")
async def video(url: str = Query(...)):
    if psutil.cpu_percent(interval=0.2) > 80:
        return JSONResponse({"status": "blocked", "reason": "high_cpu"}, status_code=503)
    cmd = base_args() + ["-f", "bv*+ba/b", "-g", url]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"status": "error", "stderr": p.stderr}, status_code=500)
    return {"status": "success", "video": p.stdout.strip()}
