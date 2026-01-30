"""Handle incoming WhatsApp messages."""

from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.orm import Session

from src.database.operations import ChatOperations, MessageOperations, SongOperations
from src.music_matching.matching_orchestrator import matching_orchestrator
from src.text_processing.message_parser import message_parser
from src.text_processing.text_cleaner import text_cleaner
from src.utils.logger import get_logger
from src.whatsapp.client import whatsapp_client
from src.playlist_parser import playlist_parser

logger = get_logger(__name__)


class MessageHandler:
    """Handle incoming WhatsApp messages."""

    def __init__(self):
        """Initialize message handler."""
        self.client = whatsapp_client
        self.cleaner = text_cleaner
        self.parser = message_parser
        self.orchestrator = matching_orchestrator

    def handle_twilio_webhook(self, db: Session, webhook_data: Dict) -> bool:
        """Handle incoming Twilio webhook.

        Args:
            db: Database session
            webhook_data: Webhook payload from Twilio

        Returns:
            True if handled successfully
        """
        try:
            # Extract message data
            message_sid = webhook_data.get("MessageSid")
            if not message_sid:
                logger.warning("Twilio webhook missing MessageSid")
                return False
            from_number = webhook_data.get("From", "").replace("whatsapp:", "")
            body = webhook_data.get("Body", "")
            timestamp_str = webhook_data.get("timestamp")

            # Parse timestamp
            timestamp = datetime.now(timezone.utc)
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.debug("Invalid timestamp format: %s", timestamp_str)

            # Use from_number as chat_id for Twilio
            chat_id = from_number

            # Process the message
            return self.process_message(
                db=db,
                message_id=message_sid,
                chat_id=chat_id,
                sender_number=from_number,
                sender_name=from_number,
                raw_text=body,
                timestamp=timestamp,
            )
        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.error("Error handling Twilio webhook: %s", exc)
            return False

    def handle_evolution_message(self, db: Session, message_data: Dict) -> bool:
        """Handle message from Evolution API.

        Args:
            db: Database session
            message_data: Message data from Evolution API

        Returns:
            True if handled successfully
        """
        try:
            # Extract message data from Evolution API format
            key = message_data.get("key", {})
            message = message_data.get("message", {})

            message_id = key.get("id")
            chat_id = key.get("remoteJid")
            sender_number = key.get("participant") or key.get("fromMe")

            # Extract text from various message types
            raw_text = ""
            if "conversation" in message:
                raw_text = message["conversation"]
            elif "extendedTextMessage" in message:
                raw_text = message["extendedTextMessage"].get("text", "")

            # Get timestamp
            timestamp = datetime.fromtimestamp(
                message_data.get("messageTimestamp", 0), tz=timezone.utc
            )

            # Get sender name (if available)
            push_name = message_data.get("pushName", sender_number)

            # Process the message
            return self.process_message(
                db=db,
                message_id=message_id,
                chat_id=chat_id,
                sender_number=sender_number,
                sender_name=push_name,
                raw_text=raw_text,
                timestamp=timestamp,
            )
        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.error("Error handling Evolution message: %s", exc)
            return False

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
        """Process a message through the complete pipeline.

        Args:
            db: Database session
            message_id: Unique message identifier
            chat_id: Chat identifier
            sender_number: Sender phone number
            sender_name: Sender display name
            raw_text: Raw message text
            timestamp: Message timestamp

        Returns:
            True if processed successfully
        """
        try:
            logger.info("Processing message: %s from %s", message_id, sender_name)

            # STEP 1: Ensure chat exists
            ChatOperations.create_or_update_chat(db, chat_id, chat_id)

            # STEP 2: Store message
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

            # STEP 3: Clean text
            cleaned_text = self.cleaner.clean(raw_text)
            if not cleaned_text:
                logger.debug("Message %s has no useful content", message_id)
                MessageOperations.mark_processed(db, message_id_int, cleaned_text)
                return True

            # STEP 4: Parse for song requests
            candidates = self.parser.parse(cleaned_text)

            # STEP 4a: Detect and expand playlists (e.g., Spotify links)
            try:
                playlist_info = playlist_parser.detect_playlist_url(cleaned_text)
                if playlist_info:
                    platform = playlist_info.get("platform")
                    playlist_id = playlist_info.get("playlist_id")
                    tracks = playlist_parser.get_playlist_tracks(platform, playlist_id)
                    max_tracks = 25  # avoid flooding
                    for t in tracks[:max_tracks]:
                        title = t.get("title")
                        artist = t.get("artist")
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

            # STEP 5: Process each candidate
            for candidate in candidates:
                try:
                    # Create extraction record
                    extraction = SongOperations.create_extraction(
                        db=db,
                        message_id=message_id_int,
                        original_phrase=candidate["original_phrase"],
                        confidence_score=candidate["confidence"],
                        extraction_method=candidate["extraction_method"],
                    )

                    # Attempt to match and create request
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

            # STEP 6: Mark message as processed
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
        """Handle incoming Telegram webhook update.

        Args:
            db: Database session
            update: Telegram update payload

        Returns:
            True if handled successfully
        """
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

            # Extract text from the message
            raw_text = message.get("text") or message.get("caption") or ""

            # Timestamp (Telegram uses 'date' as int seconds)
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
