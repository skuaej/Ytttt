import time
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="Ytttt – YouTube Progressive + HLS API")

# ==========================
# CONFIG
# ==========================
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
START_TIME = time.time()

# ==========================
# UTILS
# ==========================
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=90):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

def base_cmd():
    return [
        YTDLP,
        "--remote-components", "ejs:github",
        "--cookies", COOKIES,
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0",
    ]

# ==========================
# HEALTH
# ==========================
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": [
            "/video",
            "/video?quality=720p",
            "/video.m3u8",
            "/audio"
        ]
    }

# ==========================
# AUDIO
# ==========================
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

# ==========================
# VIDEO (PROGRESSIVE)
# ==========================
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
        fmt = f"b[ext=mp4][height<={height}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + [
        "-f", fmt,
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "status": "success",
        "type": "progressive",
        "has_audio": True,
        "quality": quality or "best",
        "url": p.stdout.strip()
    }

# ==========================
# VIDEO.M3U8 (GENERATED HLS)
# ==========================
@app.get("/video.m3u8")
async def video_m3u8(
    url: str = Query(...),
    quality: str | None = Query(default=None)
):
    # Get progressive video URL first
    if quality:
        try:
            height = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse({"error": "Invalid quality"}, status_code=400)
        fmt = f"b[ext=mp4][height<={height}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + [
        "-f", fmt,
        "-g",
        url
    ]

    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    media_url = p.stdout.strip()

    # Generate simple HLS playlist
    playlist = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-ALLOW-CACHE:NO
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:0,
{media_url}
#EXT-X-ENDLIST
"""

    return PlainTextResponse(
        playlist,
        media_type="application/vnd.apple.mpegurl"
    )
