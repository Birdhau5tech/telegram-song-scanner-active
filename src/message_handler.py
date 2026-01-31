"""Handle incoming chat messages (Telegram-focused)."""

from datetime import datetime, timezone
from typing import Dict, cast

from sqlalchemy.orm import Session

from src.database.operations import ChatOperations, MessageOperations, SongOperations
from src.music_matching.matching_orchestrator import matching_orchestrator
from src.playlist_parser import playlist_parser
from src.text_processing.message_parser import message_parser
from src.text_processing.text_cleaner import text_cleaner
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """Process inbound messages through parsing and matching pipeline."""

    def __init__(self):
        self.cleaner = text_cleaner
        self.parser = message_parser
        self.orchestrator = matching_orchestrator

    def process_message(
        self,
        db: Session,
        message_id: str,
        chat_id: str,
        sender_number: str,
        sender_name: str,
        raw_text: str,
        timestamp: datetime,
    ) -> bool:
        """Process a message through storage, parsing, and matching."""
        try:
            logger.info("Processing message: %s from %s", message_id, sender_name)

            ChatOperations.create_or_update_chat(db, chat_id, chat_id)

            message = MessageOperations.create_message(
                db=db,
                message_id=message_id,
                chat_id=chat_id,
                sender_number=sender_number,
                sender_name=sender_name,
                raw_text=raw_text,
                timestamp=timestamp,
            )
            message_id_int = int(message.id)

            cleaned_text = self.cleaner.clean(raw_text)
            if not cleaned_text:
                logger.debug("Message %s has no useful content", message_id)
                MessageOperations.mark_processed(db, message_id_int, cleaned_text)
                return True

            candidates = self.parser.parse(cleaned_text)

            try:
                playlist_info = playlist_parser.detect_playlist_url(cleaned_text)
                if playlist_info:
                    platform = playlist_info.get("platform")
                    playlist_id = playlist_info.get("playlist_id")
                    tracks = playlist_parser.get_playlist_tracks(platform, playlist_id)
                    max_tracks = 25
                    for track in tracks[:max_tracks]:
                        title = track.get("title")
                        artist = track.get("artist")
                        if not title:
                            continue
                        candidates.append(
                            {
                                "title": title,
                                "artist": artist,
                                "original_phrase": f"{title} - {artist}" if artist else title,
                                "extraction_method": f"playlist_{platform}",
                                "confidence": 98.0,
                            }
                        )
                    if tracks:
                        logger.info(
                            "Expanded playlist into %s tracks (platform=%s)",
                            min(len(tracks), max_tracks),
                            platform,
                        )
            except Exception as exc:
                logger.warning("Playlist parsing failed: %s", exc)

            if not candidates:
                logger.debug("No song candidates found in message %s", message_id)
                MessageOperations.mark_processed(db, message_id_int, cleaned_text)
                return True

            logger.info("Found %s song candidates in message", len(candidates))

            for candidate in candidates:
                try:
                    extraction = SongOperations.create_extraction(
                        db=db,
                        message_id=message_id_int,
                        original_phrase=cast(str, candidate["original_phrase"]),
                        confidence_score=candidate["confidence"],
                        extraction_method=candidate["extraction_method"],
                    )

                    self.orchestrator.process_extraction(
                        db=db,
                        extraction_id=extraction.id,
                        title=candidate["title"],
                        artist=candidate.get("artist"),
                        chat_id=chat_id,
                        requested_by=sender_name,
                    )
                except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
                    logger.error("Error processing candidate: %s", exc)
                    continue

            MessageOperations.mark_processed(db, message_id_int, cleaned_text)

            logger.info("Successfully processed message %s", message_id)
            return True

        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.error("Error processing message: %s", exc)
            try:
                MessageOperations.record_processing_error(db, message_id_int, str(exc))
            except (RuntimeError, ValueError, KeyError):
                pass
            return False

    def handle_telegram_update(self, db: Session, update: Dict) -> bool:
        """Handle incoming Telegram webhook update."""
        try:
            message = update.get("message") or update.get("edited_message")
            if not message:
                logger.debug("Telegram update has no message")
                return False

            message_id = message.get("message_id")
            chat = message.get("chat", {})
            chat_id = str(chat.get("id"))

            sender = message.get("from", {})
            sender_id = sender.get("id")
            sender_name = sender.get("username") or "{} {}".format(
                sender.get("first_name", ""), sender.get("last_name", "")
            ).strip()

            raw_text = message.get("text") or message.get("caption") or ""

            ts = message.get("date")
            timestamp = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)

            return self.process_message(
                db=db,
                message_id=str(message_id),
                chat_id=chat_id,
                sender_number=str(sender_id),
                sender_name=sender_name or str(sender_id),
                raw_text=raw_text,
                timestamp=timestamp,
            )
        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.error("Error handling Telegram update: %s", exc)
            return False


# SINGLETON INSTANCE
message_handler = MessageHandler()