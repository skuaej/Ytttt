import json
import subprocess
import shutil
import os
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse

app = FastAPI(title="Ytttt API", version="1.0.0")

COOKIES_FILE = "cookies.txt"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# -------------------------
# Helpers
# -------------------------

def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

def base_cmd():
    return [
        "yt-dlp",
        "--no-warnings",
        "--cookies", COOKIES_FILE,
        "--user-agent", "Mozilla/5.0",
        "--remote-components", "ejs:github"
    ]

# -------------------------
# ROOT
# -------------------------

@app.get("/")
def home():
    return {
        "app": "Ytttt",
        "status": "running",
        "endpoints": [
            "/audio",
            "/audio.m3u8",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/video.quality",
            "/playlist",
            "/download"
        ]
    }

# -------------------------
# AUDIO
# -------------------------

@app.get("/audio")
def audio(url: str):
    cmd = base_cmd() + ["-f", "bestaudio", "--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    return RedirectResponse(info["url"])


@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native" and f.get("vcodec") == "none":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No audio m3u8 found"}, status_code=404)

# -------------------------
# VIDEO (BEST AUTO)
# -------------------------

@app.get("/video")
def video(url: str):
    cmd = base_cmd() + ["-f", "best", "--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    return RedirectResponse(info["url"])


@app.get("/video.m3u8")
def video_m3u8(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No video m3u8 found"}, status_code=404)

# -------------------------
# VIDEO QUALITIES LIST
# -------------------------

@app.get("/video/qualities")
def video_qualities(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        stream_url = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")
        if not stream_url or not f.get("height"):
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "height": f.get("height"),
            "quality": f"{f.get('height')}p",
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": stream_url
        })

    formats.sort(key=lambda x: x["height"], reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "max_quality": f"{formats[0]['height']}p" if formats else None,
        "formats": formats
    }

# -------------------------
# VIDEO BY MANUAL QUALITY (UP TO 8K)
# -------------------------

@app.get("/video.quality")
def video_quality(
    url: str,
    height: int = Query(720, description="Max height e.g. 720, 1080, 2160, 4320")
):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    candidates = []

    for f in info.get("formats", []):
        if f.get("height") and f["height"] <= height:
            candidates.append(f)

    if not candidates:
        return JSONResponse({"error": "Quality not available"}, status_code=404)

    # Prefer HLS with audio
    candidates.sort(
        key=lambda x: (
            x.get("protocol") != "m3u8_native",
            abs(x["height"] - height)
        )
    )

    f = candidates[0]
    stream_url = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")
    return RedirectResponse(stream_url)

# -------------------------
# PLAYLIST
# -------------------------

@app.get("/playlist")
def playlist(url: str):
    cmd = base_cmd() + ["--flat-playlist", "--dump-json", url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    entries = [json.loads(line) for line in p.stdout.splitlines()]
    return {"entries": entries}

# -------------------------
# DOWNLOAD (VPS MODE ONLY)
# -------------------------

@app.get("/download")
def download(
    url: str,
    format_id: str = Query("best", description="Use format_id from /video/qualities")
):
    out = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    cmd = base_cmd() + ["-f", format_id, "-o", out, url]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    files = sorted(
        os.scandir(DOWNLOAD_DIR),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    return FileResponse(files[0].path, filename=files[0].name)
