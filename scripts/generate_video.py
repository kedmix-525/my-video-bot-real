"""
generate_video.py
Creates ONE short vertical video: picks a topic, writes a script with Gemini,
records an AI voiceover, grabs matching stock clips from Pexels, and stitches
everything together with ffmpeg (with burned-in captions).
Run it twice a day (once per video) from the GitHub Actions workflow.
"""

import os
import json
import random
import subprocess
import textwrap
from pathlib import Path

import requests

# ---------- Settings you can tweak ----------
NICHE = os.environ.get("VIDEO_NICHE", "surprising science facts")
VOICE = "en-US-AndrewNeural"          # any edge-tts voice name
WORK_DIR = Path("output")
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]


def ask_gemini(prompt: str) -> str:
    """Send one prompt to Gemini's free API and return the plain text reply."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def write_script() -> dict:
    """Ask Gemini for a short-video script plus a handful of stock-footage keywords."""
    prompt = textwrap.dedent(f"""
        Write one short video script about {NICHE}.
        Rules:
        - 45 to 60 seconds when read aloud at a normal pace (about 120-150 words).
        - Hook the viewer in the first sentence.
        - Plain spoken English, no stage directions, no emojis, no markdown.
        - End with a one-line call to action (e.g. "follow for more").
        Then, on a new line that starts with KEYWORDS:, give 4 short search terms
        (2-3 words each, comma separated) for stock video clips that would visually
        match the script.
    """).strip()

    reply = ask_gemini(prompt)
    if "KEYWORDS:" not in reply:
        raise ValueError(f"Model reply didn't include KEYWORDS line: {reply!r}")

    script_part, keyword_part = reply.split("KEYWORDS:", 1)
    keywords = [k.strip() for k in keyword_part.strip().split(",") if k.strip()]
    return {"script": script_part.strip(), "keywords": keywords[:4]}


def make_voiceover(script_text: str, out_audio: Path, out_srt: Path) -> None:
    """Use the free edge-tts command-line tool to create the narration + captions."""
    subprocess.run(
        [
            "edge-tts",
            "--voice", VOICE,
            "--text", script_text,
            "--write-media", str(out_audio),
            "--write-subtitles", str(out_srt),
        ],
        check=True,
    )


def download_stock_clips(keywords: list[str], dest_dir: Path) -> list[Path]:
    """Pull one short vertical clip per keyword from the free Pexels API."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []
    headers = {"Authorization": PEXELS_API_KEY}

    for i, keyword in enumerate(keywords):
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": keyword, "orientation": "portrait", "per_page": 5},
            timeout=30,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            continue

        video = random.choice(videos)
        # pick the smallest file that is still at least 720px tall (keeps downloads quick)
        files = sorted(video["video_files"], key=lambda f: f.get("height") or 0)
        best = next((f for f in files if (f.get("height") or 0) >= 720), files[-1])

        clip_path = dest_dir / f"clip_{i}.mp4"
        with requests.get(best["link"], stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(clip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        clip_paths.append(clip_path)

    if not clip_paths:
        raise RuntimeError("No stock clips were found for any keyword.")
    return clip_paths


def assemble_video(clips: list[Path], audio: Path, srt: Path, out_path: Path) -> None:
    """Join the clips, loop them if needed, and lay the voiceover + captions on top."""
    list_file = out_path.parent / "concat_list.txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")

    joined = out_path.parent / "joined_raw.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(joined)],
        check=True,
    )

    # if the joined clips are shorter than the voiceover, loop the whole thing
    style = (
        "FontName=Arial,FontSize=26,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=90"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", str(joined),
            "-i", str(audio),
            "-filter_complex", f"[0:v]subtitles={srt}:force_style='{style}'[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            "-pix_fmt", "yuv420p", str(out_path),
        ],
        check=True,
    )


def main() -> None:
    WORK_DIR.mkdir(exist_ok=True)
    result = write_script()
    print("Script:", result["script"])
    print("Keywords:", result["keywords"])

    audio_path = WORK_DIR / "voice.mp3"
    srt_path = WORK_DIR / "captions.srt"
    make_voiceover(result["script"], audio_path, srt_path)

    clips = download_stock_clips(result["keywords"], WORK_DIR / "clips")

    final_path = WORK_DIR / "final_video.mp4"
    assemble_video(clips, audio_path, srt_path, final_path)

    # save the title/description text next to the video for the upload scripts to reuse
    caption_text = result["script"].split(".")[0].strip() + "..."
    with open(WORK_DIR / "post_text.json", "w") as f:
        json.dump({"title": caption_text[:95], "description": result["script"]}, f)

    print(f"Done: {final_path}")


if __name__ == "__main__":
    main()
