import time
import json
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="YouTube All-Quality Stream API")

YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
START_TIME = time.time()

# -------------------------
# UTILS
# -------------------------
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=60):
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )

def base_cmd():
    cmd = [
        YTDLP,
        "--remote-components", "ejs:github",
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0",
        "--dump-json"
    ]
    if COOKIES:
        cmd += ["--cookies", COOKIES]
    return cmd

# -------------------------
# HEALTH
# -------------------------
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": ["/video/qualities", "/audio"]
    }

# -------------------------
# AUDIO (BEST)
# -------------------------
@app.get("/audio")
async def audio(url: str = Query(...)):
    cmd = [
        YTDLP,
        "--remote-components", "ejs:github",
        "-f", "bestaudio",
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "status": "success",
        "audio_url": p.stdout.strip()
    }

# -------------------------
# VIDEO – ALL QUALITIES
# -------------------------
@app.get("/video/qualities")
async def video_qualities(url: str = Query(...)):
    cmd = base_cmd() + [url]
    p = run(cmd, timeout=90)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)

    formats = []
    for f in info.get("formats", []):
        if not f.get("url"):
            continue
        if f.get("vcodec") == "none":
            continue  # skip audio-only

        formats.append({
            "format_id": f.get("format_id"),
            "resolution": f"{f.get('width')}x{f.get('height')}" if f.get("height") else "unknown",
            "fps": f.get("fps"),
            "video_codec": f.get("vcodec"),
            "audio_codec": f.get("acodec"),
            "bitrate_kbps": f.get("tbr"),
            "filesize_mb": round((f.get("filesize") or 0) / 1024 / 1024, 2) if f.get("filesize") else None,
            "protocol": f.get("protocol"),
            "ext": f.get("ext"),
            "url": f.get("url"),
            "is_hls": "m3u8" in (f.get("protocol") or ""),
        })

    # Sort by resolution height (highest first)
    formats.sort(
        key=lambda x: int(x["resolution"].split("x")[1]) if "x" in x["resolution"] else 0,
        reverse=True
    )

    return {
        "status": "success",
        "title": info.get("title"),
        "duration": info.get("duration"),
        "total_formats": len(formats),
        "formats": formats
    }
