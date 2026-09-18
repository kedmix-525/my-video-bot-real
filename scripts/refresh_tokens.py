"""
refresh_tokens.py
Instagram tokens last 60 days and TikTok tokens last 365 days - both would
eventually expire and break the whole system. This script asks each platform
for a fresh token every single day (that's safe to do - it doesn't shorten
anything) and, whenever a token actually changes, saves the new value back
into GitHub Secrets automatically using the gh command-line tool.
"""

import os
import subprocess

import requests

REPO = os.environ["GITHUB_REPOSITORY"]


def set_secret(name: str, value: str) -> None:
    subprocess.run(
        ["gh", "secret", "set", name, "--repo", REPO, "--body", value],
        check=True,
    )


def pass_to_later_steps(name: str, value: str) -> None:
    """Make this value available to the *rest of today's run* via $GITHUB_ENV.
    (Saving it to GitHub Secrets only affects *future* runs, not this one.)"""
    with open(os.environ["GITHUB_ENV"], "a") as f:
        f.write(f"{name}={value}\n")


def refresh_instagram() -> None:
    current_token = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": current_token},
        timeout=30,
    )
    resp.raise_for_status()
    new_token = resp.json()["access_token"]

    pass_to_later_steps("IG_ACCESS_TOKEN", new_token)
    if new_token != current_token:
        set_secret("IG_ACCESS_TOKEN", new_token)
        print("Instagram token refreshed.")
    else:
        print("Instagram token unchanged.")


def refresh_tiktok() -> None:
    client_key = os.environ["TIKTOK_CLIENT_KEY"]
    client_secret = os.environ["TIKTOK_CLIENT_SECRET"]
    current_refresh_token = os.environ["TIKTOK_REFRESH_TOKEN"]

    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": current_refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # TikTok hands back a brand new access token AND a brand new refresh token
    # every time - both must be saved or the next run will fail.
    pass_to_later_steps("TIKTOK_ACCESS_TOKEN", data["access_token"])
    set_secret("TIKTOK_ACCESS_TOKEN", data["access_token"])
    if data["refresh_token"] != current_refresh_token:
        set_secret("TIKTOK_REFRESH_TOKEN", data["refresh_token"])
    print("TikTok tokens refreshed.")


def main() -> None:
    refresh_instagram()
    refresh_tiktok()


if __name__ == "__main__":
    main()
