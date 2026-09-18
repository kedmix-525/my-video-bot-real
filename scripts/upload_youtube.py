"""
upload_youtube.py
Uploads output/final_video.mp4 to YouTube as a Short, using a refresh token
that was generated once during setup (see the guide for how to get it).
"""

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

WORK_DIR = Path("output")

CLIENT_ID = os.environ["YT_CLIENT_ID"]
CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]


def get_youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_short(video_path: Path, title: str, description: str) -> str:
    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            # the word "#Shorts" in the description/title is what tells YouTube
            # to treat a vertical video under 3 minutes as a Short
            "description": f"{description}\n\n#Shorts",
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            # Honest disclosure that the voice is AI-generated. YouTube added this
            # switch in Oct 2024 specifically for videos like these - leaving it off
            # is the kind of thing their July 2025 "inauthentic content" policy
            # penalizes, so it's worth the one extra line.
            "containsSyntheticMedia": True,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"YouTube upload complete: https://youtube.com/shorts/{video_id}")
    return video_id


def main() -> None:
    with open(WORK_DIR / "post_text.json") as f:
        post_text = json.load(f)

    upload_short(
        WORK_DIR / "final_video.mp4",
        title=post_text["title"],
        description=post_text["description"],
    )


if __name__ == "__main__":
    main()
