"""Telegram polling mode - fetch updates without webhook."""

import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

from config.database import SessionLocal
from src.database.operations import ChatOperations, MessageOperations, RequestOperations, SongOperations
from src.music_matching.matching_orchestrator import matching_orchestrator
from src.radiodj_integration.playlist_manager import playlist_manager
from src.text_processing.message_parser import message_parser
from src.text_processing.text_cleaner import text_cleaner
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramPoller:
    """Poll Telegram for updates instead of using webhooks."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.timeout = 30  # long polling timeout

    def is_configured(self) -> bool:
        return bool(self.token)

    def get_updates(self) -> list:
        """Fetch new updates from Telegram."""
        if not self.is_configured():
            logger.warning("Telegram token not configured")
            return []

        try:
            resp = requests.get(
                f"{self.base_url}/getUpdates",
                params={
                    "offset": self.offset,
                    "timeout": self.timeout,
                    "allowed_updates": ["message", "edited_message"],
                },
                timeout=self.timeout + 5,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                logger.error("Telegram API error: %s", data)
                return []

            return data.get("result", [])
        except requests.RequestException as exc:
            logger.error("Failed to get updates: %s", exc)
            return []

    def send_reply(self, chat_id: int, text: str) -> bool:
        """Send a reply message to a specific chat."""
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Replied to chat %s", chat_id)
            return True
        except Exception as exc:
            logger.error("Failed to send reply: %s", exc)
            return False

    def process_update(self, update: dict) -> bool:
        """Process a single update through the full pipeline."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return False

        chat_id = message.get("chat", {}).get("id")
        message_id = str(message.get("message_id", ""))
        text = message.get("text") or message.get("caption") or ""
        sender = message.get("from", {})
        sender_name = sender.get("username") or sender.get("first_name", "unknown")
        sender_id = str(sender.get("id", ""))

        if not text.strip():
            return True

        # Clean and parse the message for song candidates
        cleaned = text_cleaner.clean(text)
        if not cleaned:
            self.send_reply(chat_id, "🎵 I couldn't find a song in that message.\nTry: 'Artist - Song Title'")
            return True

        candidates = message_parser.parse(cleaned)
        if not candidates:
            self.send_reply(chat_id, f"🔍 No song detected in: '{text[:40]}...'\n\nTry formats like:\n• Adele - Hello\n• Shape of You by Ed Sheeran")
            return True

        # Process through full pipeline
        db = SessionLocal()
        try:
            # Store chat and message
            ChatOperations.create_or_update_chat(db, str(chat_id), str(chat_id))
            ts = message.get("date")
            timestamp = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
            
            db_message = MessageOperations.create_message(
                db=db,
                message_id=message_id,
                chat_id=str(chat_id),
                sender_number=sender_id,
                sender_name=sender_name,
                raw_text=text,
                timestamp=timestamp,
            )

            results = []
            for candidate in candidates:
                title = candidate.get("title", "")
                artist = candidate.get("artist", "")
                
                # Create extraction record
                extraction = SongOperations.create_extraction(
                    db=db,
                    message_id=db_message.id,
                    original_phrase=candidate.get("original_phrase", f"{title} - {artist}"),
                    confidence_score=candidate.get("confidence", 80.0),
                    extraction_method=candidate.get("extraction_method", "parser"),
                )

                # Match the song
                match_result = matching_orchestrator.match_song(db, extraction.id, title, artist)
                
                if not match_result:
                    results.append(f"❌ '{title}' by {artist or 'Unknown'} - No match found")
                    continue

                # Create request
                request = RequestOperations.create_request(
                    db=db,
                    chat_id=str(chat_id),
                    matched_song_id=match_result["matched_song_id"],
                    requested_by=sender_name,
                    priority=1,
                )

                matched_title = match_result.get("title", title)
                matched_artist = match_result.get("artist", artist) or "Unknown"
                confidence = match_result.get("confidence", 0)
                is_verified = match_result.get("is_verified", False)

                # Auto-approve high confidence matches
                if is_verified:
                    RequestOperations.approve_request(db, request.id)
                    
                    # Immediately try to add to RadioDJ
                    track_id = playlist_manager.add_song_to_playlist(
                        artist=matched_artist,
                        title=matched_title,
                        use_api=True
                    )
                    
                    if track_id is not None:
                        RequestOperations.mark_queued(db, request.id, track_id if track_id > 0 else None)
                        results.append(f"✅ '{matched_title}' by {matched_artist}\n   📻 Added to RadioDJ queue!")
                    else:
                        results.append(f"✅ '{matched_title}' by {matched_artist}\n   ⚠️ Approved but RadioDJ unavailable")
                else:
                    results.append(f"🔍 '{matched_title}' by {matched_artist}\n   Confidence: {confidence:.0f}% (pending review)")

            # Mark message as processed
            MessageOperations.mark_processed(db, db_message.id, cleaned)

            # Send reply
            reply = "🎵 Song Request Results:\n\n" + "\n\n".join(results)
            self.send_reply(chat_id, reply)

            return True
        except Exception as exc:
            logger.error("Error processing: %s", exc)
            self.send_reply(chat_id, f"❌ Error processing request: {str(exc)[:100]}")
            return False
        finally:
            db.close()

    def run(self, interval: float = 1.0):
        """Run polling loop."""
        if not self.is_configured():
            logger.error("Cannot start polling: TELEGRAM_BOT_TOKEN not set")
            return

        logger.info("Starting Telegram polling mode...")
        logger.info("Bot token: %s...%s", self.token[:10], self.token[-5:])

        # Delete any existing webhook first
        try:
            requests.post(f"{self.base_url}/deleteWebhook", timeout=10)
            logger.info("Webhook deleted (if any)")
        except Exception:
            pass

        while True:
            try:
                updates = self.get_updates()

                for update in updates:
                    update_id = update.get("update_id", 0)
                    self.offset = update_id + 1

                    message = update.get("message") or update.get("edited_message")
                    if message:
                        text = message.get("text", "")[:50]
                        sender = message.get("from", {}).get("username", "unknown")
                        logger.info("Received: '%s...' from @%s", text, sender)

                    success = self.process_update(update)
                    if success:
                        logger.info("Update %s processed successfully", update_id)

                if not updates:
                    time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Polling stopped by user")
                break
            except Exception as exc:
                logger.error("Polling error: %s", exc)
                time.sleep(5)


# Singleton
telegram_poller = TelegramPoller()


def run_polling():
    """Entry point for polling mode."""
    telegram_poller.run()


if __name__ == "__main__":
    run_polling()
