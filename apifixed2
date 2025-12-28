import time
import json
import subprocess
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from pathlib import Path

app = FastAPI(title="Ytttt – Audio/Video Streaming + Download API")

# ==========================
# CONFIG
# ==========================
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
START_TIME = time.time()

# ==========================
# UTILS
# ==========================
def uptime():
    s = int(time.time() - START_TIME)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h {m}m {s}s"

def run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def base_cmd():
    return [
        YTDLP,
        "--remote-components", "ejs:github",
        "--cookies", COOKIES,
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0",
    ]

# ==========================
# ROOT
# ==========================
@app.get("/")
async def root():
    return {
        "status": "running",
        "uptime": uptime(),
        "endpoints": [
            "/audio",
            "/audio.m3u8",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/download"
        ]
    }

# ==========================
# AUDIO (BEST)
# ==========================
@app.get("/audio")
async def audio(url: str = Query(...)):
    cmd = base_cmd() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)
    return {"status": "success", "url": p.stdout.strip()}

# ==========================
# AUDIO.M3U8 (GENERATED)
# ==========================
@app.get("/audio.m3u8")
async def audio_m3u8(url: str = Query(...)):
    cmd = base_cmd() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    audio_url = p.stdout.strip()
    playlist = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXTINF:0,
{audio_url}
#EXT-X-ENDLIST
"""
    return PlainTextResponse(playlist, media_type="application/vnd.apple.mpegurl")

# ==========================
# VIDEO (PROGRESSIVE WITH SOUND)
# ==========================
@app.get("/video")
async def video(url: str = Query(...), quality: str | None = None):
    if quality:
        try:
            h = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse({"error": "Use quality like 720p"}, status_code=400)
        fmt = f"b[ext=mp4][height<={h}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + ["-f", fmt, "-g", url]
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
async def video_m3u8(url: str = Query(...), quality: str | None = None):
    if quality:
        try:
            h = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse({"error": "Use quality like 720p"}, status_code=400)
        fmt = f"b[ext=mp4][height<={h}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + ["-f", fmt, "-g", url]
    p = run(cmd)
    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    media_url = p.stdout.strip()
    playlist = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXTINF:0,
{media_url}
#EXT-X-ENDLIST
"""
    return PlainTextResponse(playlist, media_type="application/vnd.apple.mpegurl")

# ==========================
# VIDEO QUALITIES (UP TO 8K)
# ==========================
@app.get("/video/qualities")
async def video_qualities(url: str = Query(...)):
    cmd = base_cmd() + ["--dump-json", url]
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
            "ext": f.get("ext"),
            "protocol": f.get("protocol"),
            "has_audio": f.get("acodec") != "none",
            "url_available": bool(f.get("url"))
        })

    formats.sort(key=lambda x: x["height"] or 0, reverse=True)

    return {
        "status": "success",
        "title": info.get("title"),
        "max_quality": f"{formats[0]['height']}p" if formats else None,
        "formats": formats
    }

# ==========================
# DOWNLOAD (ANY QUALITY, UP TO 8K)
# ==========================
@app.get("/download")
async def download(url: str = Query(...), quality: str | None = None):
    if quality:
        try:
            h = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse({"error": "Use quality like 2160p, 4320p"}, status_code=400)
        fmt = f"bv*[height={h}]+ba/best"
    else:
        fmt = "bestvideo+bestaudio/best"

    out = DOWNLOAD_DIR / "%(title)s_%(height)sp.%(ext)s"
    cmd = base_cmd() + [
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", str(out),
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    # return latest file
    latest = max(DOWNLOAD_DIR.glob("*"), key=lambda x: x.stat().st_mtime)
    return FileResponse(latest, filename=latest.name)
