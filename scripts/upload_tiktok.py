"""
upload_tiktok.py
Publishes output/final_video.mp4 to TikTok using the Content Posting API's
Direct Post / FILE_UPLOAD flow.

IMPORTANT: until your TikTok developer app has passed TikTok's audit, every
video this uploads will be PRIVATE (visible only to you), no matter what
privacy_level you ask for below - see the guide for how audit approval works.
"""

import json
import os
from pathlib import Path

import requests

WORK_DIR = Path("output")
ACCESS_TOKEN = os.environ["TIKTOK_ACCESS_TOKEN"]
API_BASE = "https://open.tiktokapis.com/v2/post/publish"


def init_upload(video_size: int, title: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/video/init/",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title": title,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,   # send the whole file as one chunk
                "total_chunk_count": 1,
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def upload_bytes(upload_url: str, video_path: Path, video_size: int) -> None:
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    resp = requests.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        },
        data=video_bytes,
        timeout=120,
    )
    resp.raise_for_status()


def main() -> None:
    with open(WORK_DIR / "post_text.json") as f:
        post_text = json.load(f)

    video_path = WORK_DIR / "final_video.mp4"
    video_size = video_path.stat().st_size

    data = init_upload(video_size, title=post_text["title"])
    upload_bytes(data["upload_url"], video_path, video_size)

    print(f"TikTok upload started, publish id: {data['publish_id']}")
    print("Check the TikTok Studio inbox on your phone to confirm it posted.")


if __name__ == "__main__":
    main()
