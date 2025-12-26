# yt_api.py
# YouTube Audio API with COOKIE + PROXY
# For Telegram Music Bots

import os
import yt_dlp
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="YT Audio API (Cookie + Proxy)")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")

YT_PROXY = os.getenv("YT_PROXY")  # optional


def extract_audio(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "skip_download": True,
        "noplaylist": True,
    }

    # 🍪 COOKIE SUPPORT
    if os.path.exists(COOKIE_FILE):
        ydl_opts["cookiefile"] = COOKIE_FILE

    # 🌍 PROXY SUPPORT
    if YT_PROXY:
        ydl_opts["proxy"] = YT_PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            audio_url = info.get("url")
            if not audio_url:
                raise Exception("Audio URL not found")

            return {
                "title": info.get("title"),
                "duration": info.get("duration"),
                "audio_url": audio_url,
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/audio")
def audio(
    vidid: str = Query(..., description="YouTube video ID")
):
    return extract_audio(vidid)
