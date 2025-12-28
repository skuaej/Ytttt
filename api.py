import time
import json
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="YouTube Stream API (SABR-safe)")

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

def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def base_cmd(dump_json=False):
    cmd = [
        YTDLP,
        "--remote-components", "ejs:github",
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0",
        "--cookies", COOKIES,
    ]
    if dump_json:
        cmd.append("--dump-json")
    return cmd

# -------------------------
# HEALTH
# -------------------------
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": [
            "/audio",
            "/video",
            "/video?quality=720p",
            "/video/qualities"
        ]
    }

# -------------------------
# AUDIO (BEST)
# -------------------------
@app.get("/audio")
async def audio(url: str = Query(...)):
    cmd = base_cmd() + [
        "-f", "bestaudio",
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "status": "success",
        "type": "audio",
        "url": p.stdout.strip()
    }

# -------------------------
# VIDEO (BEST or QUALITY)
# -------------------------
@app.get("/video")
async def video(
    url: str = Query(...),
    quality: str | None = Query(default=None)
):
    if quality:
        try:
            height = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse(
                {"error": "Invalid quality. Use 720p, 480p, etc."},
                status_code=400
            )

        format_selector = f"bv*[height={height}]/bv*[height<={height}]/best"
    else:
        format_selector = "bv*+ba/b"

    cmd = base_cmd() + [
        "-f", format_selector,
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "status": "success",
        "quality": quality or "best",
        "delivery": "direct-or-sabr",
        "url": p.stdout.strip()
    }

# -------------------------
# VIDEO – ALL QUALITIES
# -------------------------
@app.get("/video/qualities")
async def video_qualities(url: str = Query(...)):
    cmd = base_cmd(dump_json=True) + [url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        if f.get("vcodec") == "none":
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "resolution": f"{f.get('width')}x{f.get('height')}" if f.get("height") else None,
            "height": f.get("height"),
            "fps": f.get("fps"),
            "protocol": f.get("protocol"),
            "ext": f.get("ext"),
            "has_url": bool(f.get("url")),
            "delivery": "sabr" if not f.get("url") else "direct",
            "url": f.get("url")
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "status": "success",
        "title": info.get("title"),
        "duration": info.get("duration"),
        "total_formats": len(formats),
        "formats": formats
    }
