import time
import json
import subprocess
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import (
    JSONResponse,
    PlainTextResponse,
    FileResponse
)

# ==========================
# APP
# ==========================
app = FastAPI(title="Ytttt – YouTube Streaming & Download API (VPS)")

# ==========================
# CONFIG
# ==========================
YTDLP = "yt-dlp"
COOKIES = "cookies.txt"          # must exist
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

def run(cmd, timeout=None):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout
    )

def base_cmd():
    return [
        YTDLP,
        "--cookies", COOKIES,
        "--remote-components", "ejs:github",
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0"
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
            "/playlist",
            "/download"
        ]
    }

# ==========================
# AUDIO
# ==========================
@app.get("/audio")
async def audio(url: str = Query(...)):
    cmd = base_cmd() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)

    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {"type": "audio", "url": p.stdout.strip()}

# ==========================
# AUDIO.M3U8
# ==========================
@app.get("/audio.m3u8")
async def audio_m3u8(url: str = Query(...)):
    cmd = base_cmd() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)

    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    playlist = f"""#EXTM3U
#EXT-X-VERSION:3
#EXTINF:0,
{p.stdout.strip()}
#EXT-X-ENDLIST
"""
    return PlainTextResponse(
        playlist,
        media_type="application/vnd.apple.mpegurl"
    )

# ==========================
# VIDEO (PROGRESSIVE)
# ==========================
@app.get("/video")
async def video(
    url: str = Query(...),
    quality: str | None = None
):
    if quality:
        try:
            h = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse(
                {"error": "Use quality like 720p"},
                status_code=400
            )
        fmt = f"b[ext=mp4][height<={h}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + ["-f", fmt, "-g", url]
    p = run(cmd)

    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    return {
        "type": "video",
        "has_audio": True,
        "quality": quality or "best",
        "url": p.stdout.strip()
    }

# ==========================
# VIDEO.M3U8
# ==========================
@app.get("/video.m3u8")
async def video_m3u8(
    url: str = Query(...),
    quality: str | None = None
):
    if quality:
        try:
            h = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse(
                {"error": "Use quality like 720p"},
                status_code=400
            )
        fmt = f"b[ext=mp4][height<={h}]/b"
    else:
        fmt = "b[ext=mp4]/b"

    cmd = base_cmd() + ["-f", fmt, "-g", url]
    p = run(cmd)

    if p.returncode != 0 or not p.stdout.strip():
        return JSONResponse({"error": p.stderr}, status_code=500)

    playlist = f"""#EXTM3U
#EXT-X-VERSION:3
#EXTINF:0,
{p.stdout.strip()}
#EXT-X-ENDLIST
"""
    return PlainTextResponse(
        playlist,
        media_type="application/vnd.apple.mpegurl"
    )

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
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "height": f.get("height"),
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": f.get("url")
        })

    formats.sort(
        key=lambda x: x["height"] or 0,
        reverse=True
    )

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{formats[0]['height']}p" if formats else None,
        "formats": formats
    }

# ==========================
# PLAYLIST
# ==========================
@app.get("/playlist")
async def playlist(url: str = Query(...)):
    cmd = base_cmd() + ["--flat-playlist", "--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    videos = []
    for line in p.stdout.splitlines():
        data = json.loads(line)
        videos.append({
            "title": data.get("title"),
            "url": f"https://youtu.be/{data.get('id')}"
        })

    return {
        "total_videos": len(videos),
        "videos": videos
    }

# ==========================
# DOWNLOAD (ANY QUALITY, VPS)
# ==========================
@app.get("/download")
async def download(
    url: str = Query(...),
    quality: str | None = None
):
    if quality:
        try:
            h = int(quality.replace("p", ""))
        except ValueError:
            return JSONResponse(
                {"error": "Use quality like 1080p, 2160p, 4320p"},
                status_code=400
            )
        fmt = f"bv*[height<={h}]+ba/best"
    else:
        fmt = "bestvideo+bestaudio/best"

    output = DOWNLOAD_DIR / "%(title)s_%(height)sp.%(ext)s"

    cmd = base_cmd() + [
        "-f", fmt,
        "--merge-output-format", "mp4",
        "-o", str(output),
        url
    ]

    p = run(cmd, timeout=None)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    file = max(
        DOWNLOAD_DIR.glob("*.mp4"),
        key=lambda x: x.stat().st_mtime
    )

    return FileResponse(
        file,
        filename=file.name,
        media_type="video/mp4"
    )
