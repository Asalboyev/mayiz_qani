import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def telegram_is_configured() -> bool:
    return bool(BOT_TOKEN and CHAT_ID)


def send_message(text: str) -> dict:
    if not telegram_is_configured():
        return {
            "ok": False,
            "skipped": True,
            "reason": "Telegram token yoki chat_id .env ichida yo'q",
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=15,
    )
    return response.json()


def send_photo(photo_path: str, caption: str = "") -> dict:
    if not telegram_is_configured():
        return {
            "ok": False,
            "skipped": True,
            "reason": "Telegram token yoki chat_id .env ichida yo'q",
        }

    path = Path(photo_path)
    if not path.exists():
        return {
            "ok": False,
            "error": f"Photo not found: {photo_path}",
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    with open(path, "rb") as photo:
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML",
            },
            files={"photo": photo},
            timeout=30,
        )

    return response.json()


def send_location(latitude: float, longitude: float) -> dict:
    if not telegram_is_configured():
        return {
            "ok": False,
            "skipped": True,
            "reason": "Telegram token yoki chat_id .env ichida yo'q",
        }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendLocation"
    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "latitude": latitude,
            "longitude": longitude,
        },
        timeout=15,
    )
    return response.json()