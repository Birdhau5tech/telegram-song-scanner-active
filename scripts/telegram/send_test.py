"""Send a test message to the configured Telegram chat.

Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from environment or a local `.env` file.
Usage:
  python scripts/telegram/send_test.py "Optional test message"

Exit codes:
  0 on success, 1 on configuration or request error.
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
env_path = ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def main():
    if not TOKEN or not CHAT_ID:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment or .env", file=sys.stderr)
        return 1

    text = "Test message from WhatsApp Song Scanner"
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        print("Failed to send Telegram message:", exc, file=sys.stderr)
        if hasattr(exc, 'response') and exc.response is not None:
            try:
                print(exc.response.text, file=sys.stderr)
            except Exception:
                pass
        return 1

    print("Telegram message sent successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())
