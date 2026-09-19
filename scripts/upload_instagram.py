"""
upload_instagram.py
Publishes output/final_video.mp4 as an Instagram Reel.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import requests

WORK_DIR = Path("output")
IG_USER_ID = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]  # "your-username/your-repo", set automatically by Actions
GRAPH_VERSION = "v21.0"


def host_video_publicly(video_path: Path) -> tuple[str, str]:
    """Attach the video to a new GitHub release and return (public_url, tag_name)."""
    tag = f"reel-{int(time.time())}"
    subprocess.run(
        ["gh", "release", "create", tag, str(video_path),
         "--title", tag, "--notes", "Temporary file for Instagram upload"],
        check=True,
    )
    url = f"https://github.com/{REPO}/releases/download/{tag}/{video_path.name}"
    return url, tag


def delete_release(tag: str) -> None:
    subprocess.run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"], check=False)


def create_media_container(video_url: str, caption: str) -> str:
    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=60,
    )
    print(f"Instagram error response: {resp.text}")
    resp.raise_for_status()
    return resp.json()["id"]


def wait_until_ready(container_id: str, timeout_seconds: int = 300) -> None:
    """Instagram needs to download and process the video before it can publish it."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{container_id}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Instagram failed to process container {container_id}")
        time.sleep(10)
    raise TimeoutError(f"Container {container_id} was not ready after {timeout_seconds}s")


def publish_container(container_id: str) -> str:
    resp = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def main() -> None:
    with open(WORK_DIR / "post_text.json") as f:
        post_text = json.load(f)
    caption = post_text["description"]

    video_path = WORK_DIR / "final_video.mp4"
    video_url, tag = host_video_publicly(video_path)
    print(f"Video temporarily hosted at: {video_url}")

    try:
        container_id = create_media_container(video_url, caption)
        wait_until_ready(container_id)
        media_id = publish_container(container_id)
        print(f"Instagram Reel published, media id: {media_id}")
    finally:
        delete_release(tag)


if __name__ == "__main__":
    main()
