"""Simple Telegram bot client using HTTP API."""
from typing import Optional
import os

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramClient:
    """Minimal Telegram API client for sending messages to a chat."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, parse_mode: Optional[str] = None) -> bool:
        """Send a text message to the configured chat.

        Returns True on success, False otherwise.
        """
        if not self.is_configured():
            logger.debug("Telegram not configured (token/chat_id missing)")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram message sent")
            return True
        except Exception as exc:
            logger.error("Failed to send Telegram message: %s", exc)
            return False


# Singleton client using env vars by default
telegram_client = TelegramClient()
