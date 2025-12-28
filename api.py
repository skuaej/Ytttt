import json
import time
import subprocess
import os
import psutil
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse

app = FastAPI(title="Ytttt API", version="1.1.0")

YTDLP = "yt-dlp"
COOKIES = "cookies.txt"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# -------------------------
# HELPERS
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
        YTDLP,
        "--cookies", COOKIES,
        "--user-agent", "Mozilla/5.0",
        "--dump-json",
        "--no-warnings"
    ]

# -------------------------
# STATS
# -------------------------
@app.get("/stats")
def stats():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }

# -------------------------
# MANUAL QUALITY STREAM
# -------------------------
@app.get("/video/quality")
def video_quality(
    url: str = Query(...),
    res: int = Query(720, description="144–2160 (8K if available)")
):
    cmd = base_cmd() + [url]
    p = run(cmd)

    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    info = json.loads(p.stdout)
    candidates = []

    for f in info.get("formats", []):
        if not f.get("height"):
            continue
        if f["height"] <= res:
            candidates.append(f)

    # prefer HLS with audio
    candidates.sort(
        key=lambda x: (
            x.get("protocol") != "m3u8_native",
            abs(x.get("height", 0) - res)
        )
    )

    if not candidates:
        return JSONResponse({"error": "Requested quality not available"}, status_code=404)

    f = candidates[0]
    stream_url = f.get("manifest_url") if f.get("protocol") == "m3u8_native" else f.get("url")

    return RedirectResponse(stream_url)

# -------------------------
# DOWNLOAD ENDPOINT
# -------------------------
@app.get("/download")
def download(
    url: str = Query(...),
    res: int | None = Query(None, description="Optional quality like 720,1080")
):
    fmt = (
        f"bestvideo[height<={res}]+bestaudio/best"
        if res else
        "bestvideo+bestaudio/best"
    )

    out = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    cmd = [
        YTDLP,
        "--cookies", COOKIES,
        "-f", fmt,
        "-o", out,
        "--merge-output-format", "mp4",
        url
    ]

    p = run(cmd)
    if p.returncode != 0:
        return JSONResponse({"error": p.stderr}, status_code=500)

    files = sorted(
        os.scandir(DOWNLOAD_DIR),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    return FileResponse(
        files[0].path,
        filename=files[0].name,
        media_type="application/octet-stream"
    )
