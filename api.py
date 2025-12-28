import os
import json
import shutil
import subprocess
import psutil
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse

app = FastAPI(title="Ytttt API", version="2.0.0")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --------------------------------------------------
# CORE UTILS
# --------------------------------------------------

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
        "--no-cache-dir",
        "--rm-cache-dir",
        "--cookies", "cookies.txt",
        "--user-agent", "Mozilla/5.0"
    ]

# --------------------------------------------------
# HOME / STATS
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "app": "Ytttt",
        "status": "running",
        "endpoints": [
            "/stats",
            "/audio",
            "/audio.m3u8",
            "/video",
            "/video.m3u8",
            "/video/qualities",
            "/playlist",
            "/download"
        ]
    }

@app.get("/stats")
def stats():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent
    }

# --------------------------------------------------
# AUDIO
# --------------------------------------------------

@app.get("/audio")
def audio(url: str):
    cmd = base_cmd() + ["-f", "bestaudio", "-g", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)
    return RedirectResponse(p.stdout.strip())

@app.get("/audio.m3u8")
def audio_m3u8(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    for f in info.get("formats", []):
        if f.get("protocol") == "m3u8_native" and f.get("acodec") != "none":
            return RedirectResponse(f["manifest_url"])

    return JSONResponse({"error": "No audio HLS found"}, 404)

# --------------------------------------------------
# VIDEO (QUALITY + AUTO FALLBACK)
# --------------------------------------------------

@app.get("/video")
def video(
    url: str,
    quality: str = Query("best", description="144p,360p,720p,1080p,2160p")
):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)

    wanted_height = None
    if quality.endswith("p"):
        wanted_height = int(quality.replace("p", ""))

    best_match = None
    fallback = None

    for f in info.get("formats", []):
        if not f.get("url"):
            continue
        if f.get("vcodec") == "none":
            continue

        h = f.get("height")
        if not h:
            continue

        if wanted_height and h == wanted_height:
            best_match = f
            break

        if not wanted_height:
            fallback = f
        elif h < wanted_height:
            fallback = f

    selected = best_match or fallback
    if not selected:
        return JSONResponse({"error": "No suitable format found"}, 404)

    return RedirectResponse(selected["url"])

@app.get("/video.m3u8")
def video_m3u8(
    url: str,
    quality: str = Query("best")
):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    wanted_height = int(quality.replace("p", "")) if quality.endswith("p") else None

    best = None
    fallback = None

    for f in info.get("formats", []):
        if f.get("protocol") != "m3u8_native":
            continue
        if f.get("acodec") == "none":
            continue

        h = f.get("height")
        if not h:
            continue

        if wanted_height and h == wanted_height:
            best = f
            break

        if not wanted_height or h < wanted_height:
            fallback = f

    selected = best or fallback
    if not selected:
        return JSONResponse({"error": "No HLS stream found"}, 404)

    return RedirectResponse(selected["manifest_url"])

# --------------------------------------------------
# VIDEO QUALITIES (ALL)
# --------------------------------------------------

@app.get("/video/qualities")
def video_qualities(url: str):
    cmd = base_cmd() + ["--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    info = json.loads(p.stdout)
    formats = []

    for f in info.get("formats", []):
        stream = f.get("manifest_url") or f.get("url")
        if not stream:
            continue

        formats.append({
            "format_id": f.get("format_id"),
            "quality": f"{f.get('height')}p" if f.get("height") else None,
            "fps": f.get("fps"),
            "ext": f.get("ext"),
            "has_audio": f.get("acodec") != "none",
            "protocol": f.get("protocol"),
            "url": stream
        })

    formats.sort(key=lambda x: int(x["quality"].replace("p", "")) if x["quality"] else 0, reverse=True)

    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "formats": formats
    }

# --------------------------------------------------
# PLAYLIST (FAST, NO DOWNLOAD)
# --------------------------------------------------

@app.get("/playlist")
def playlist(url: str):
    cmd = base_cmd() + ["--flat-playlist", "--dump-json", url]
    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    entries = [json.loads(line) for line in p.stdout.splitlines()]
    return {"count": len(entries), "entries": entries}

# --------------------------------------------------
# DOWNLOAD (AUTO DELETE)
# --------------------------------------------------

@app.get("/download")
def download(
    url: str,
    quality: str = "best"
):
    out = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
    cmd = base_cmd() + ["-f", quality, "-o", out, url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, 500)

    files = sorted(
        os.listdir(DOWNLOAD_DIR),
        key=lambda f: os.path.getmtime(f"{DOWNLOAD_DIR}/{f}"),
        reverse=True
    )

    path = f"{DOWNLOAD_DIR}/{files[0]}"
    response = FileResponse(path, filename=files[0])

    @response.call_on_close
    def cleanup():
        try:
            os.remove(path)
        except:
            pass

    return response
