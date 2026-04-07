"""Database CRUD operations."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.database.models import (
    ChatMessage,
    ExtractedSong,
    MatchedSong,
    QueueProtocolEvent,
    SongRequest,
    WhatsAppChat,
)


class ChatOperations:
    """Operations for WhatsApp chats."""

    @staticmethod
    def create_or_update_chat(
        db: Session, chat_id: str, chat_name: Optional[str] = None
    ) -> WhatsAppChat:
        """Create or update a WhatsApp chat."""
        chat = db.query(WhatsAppChat).filter(WhatsAppChat.chat_id == chat_id).first()
        if chat:
            if chat_name:
                chat.chat_name = chat_name  # type: ignore[assignment]
            chat.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        else:
            chat = WhatsAppChat(chat_id=chat_id, chat_name=chat_name)
            db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat

    @staticmethod
    def get_active_chats(db: Session) -> List[WhatsAppChat]:
        """Get all active chats."""
        return db.query(WhatsAppChat).filter(WhatsAppChat.is_active.is_(True)).all()

    @staticmethod
    def update_last_scan(db: Session, chat_id: str, message_id: Optional[str] = None):
        """Update last scan timestamp for a chat."""
        chat = db.query(WhatsAppChat).filter(WhatsAppChat.chat_id == chat_id).first()
        if chat:
            chat.last_scan_time = datetime.now(timezone.utc)  # type: ignore[assignment]
            if message_id:
                chat.last_message_id = message_id  # type: ignore[assignment]
            db.commit()


class MessageOperations:
    """Operations for chat messages."""

    @staticmethod
    def create_message(
        db: Session,
        message_id: str,
        chat_id: str,
        sender_number: str,
        sender_name: str,
        raw_text: str,
        timestamp: datetime,
    ) -> ChatMessage:
        """Create a new message."""
        message = ChatMessage(
            message_id=message_id,
            chat_id=chat_id,
            sender_number=sender_number,
            sender_name=sender_name,
            raw_text=raw_text,
            timestamp=timestamp,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def get_unprocessed_messages(db: Session, limit: int = 100) -> List[ChatMessage]:
        """Get unprocessed messages."""
        return (
            db.query(ChatMessage)
            .filter(ChatMessage.is_processed.is_(False))
            .order_by(ChatMessage.timestamp.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def mark_processed(db: Session, message_id: int, cleaned_text: Optional[str] = None):
        """Mark message as processed."""
        message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if message:
            message.is_processed = True  # type: ignore[assignment]
            if cleaned_text:
                message.cleaned_text = cleaned_text  # type: ignore[assignment]
            db.commit()

    @staticmethod
    def record_processing_error(db: Session, message_id: int, error: str):
        """Record processing error."""
        message = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if message:
            message.processing_attempts += 1  # type: ignore[assignment]
            message.processing_error = error  # type: ignore[assignment]
            db.commit()


class SongOperations:
    """Operations for extracted and matched songs."""

    @staticmethod
    def create_extraction(
        db: Session,
        message_id: int,
        original_phrase: str,
        confidence_score: float,
        extraction_method: str,
    ) -> ExtractedSong:
        """Create an extracted song entry."""
        extraction = ExtractedSong(
            message_id=message_id,
            original_phrase=original_phrase,
            confidence_score=confidence_score,
            extraction_method=extraction_method,
        )
        db.add(extraction)
        db.commit()
        db.refresh(extraction)
        return extraction

    @staticmethod
    def create_match(
        db: Session,
        extraction_id: int,
        song_title: str,
        artist_name: Optional[str] = None,
        album_name: Optional[str] = None,
        musicbrainz_id: Optional[str] = None,
        match_confidence: Optional[float] = None,
        match_source: Optional[str] = None,
        match_metadata: Optional[dict] = None,
    ) -> MatchedSong:
        """Create a matched song entry."""
        match = MatchedSong(
            extraction_id=extraction_id,
            song_title=song_title,
            artist_name=artist_name,
            album_name=album_name,
            musicbrainz_id=musicbrainz_id,
            match_confidence=match_confidence,
            match_source=match_source,
            match_metadata=match_metadata,
        )
        db.add(match)
        db.commit()
        db.refresh(match)
        return match

    @staticmethod
    def verify_match(db: Session, match_id: int, method: str):
        """Mark match as verified."""
        match = db.query(MatchedSong).filter(MatchedSong.id == match_id).first()
        if match:
            match.is_verified = True  # type: ignore[assignment]
            match.verification_method = method  # type: ignore[assignment]
            db.commit()


class RequestOperations:
    """Operations for song requests."""

    @staticmethod
    def create_request(
        db: Session, chat_id: str, matched_song_id: int, requested_by: str, priority: int = 1
    ) -> SongRequest:
        """Create a song request."""
        request = SongRequest(
            chat_id=chat_id,
            matched_song_id=matched_song_id,
            requested_by=requested_by,
            request_priority=priority,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def get_pending_requests(db: Session, limit: int = 50) -> List[SongRequest]:
        """Get pending requests."""
        return (
            db.query(SongRequest)
            .filter(SongRequest.status == "pending")
            .order_by(desc(SongRequest.request_priority), SongRequest.created_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_recent_requests(
        db: Session,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[SongRequest]:
        """Get latest requests across all statuses, optionally filtered by status."""
        query = db.query(SongRequest)
        if status:
            query = query.filter(SongRequest.status == status)
        return query.order_by(desc(SongRequest.id)).limit(limit).all()

    @staticmethod
    def get_request_events(
        db: Session,
        request_id: int,
        limit: int = 20,
    ) -> List[QueueProtocolEvent]:
        """Get latest queue protocol events for a request."""
        return (
            db.query(QueueProtocolEvent)
            .filter(QueueProtocolEvent.request_id == request_id)
            .order_by(desc(QueueProtocolEvent.id))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_queue_candidates(db: Session, limit: int = 50) -> List[SongRequest]:
        """Get approved requests ready for queue attempts."""
        now = datetime.now(timezone.utc)
        return (
            db.query(SongRequest)
            .filter(SongRequest.status == "approved")
            .filter(SongRequest.queue_terminal_failure.is_(False))
            .filter(SongRequest.radiodj_track_id.is_(None))
            .filter(
                (SongRequest.next_queue_retry_at.is_(None)) | (SongRequest.next_queue_retry_at <= now)
            )
            .order_by(desc(SongRequest.request_priority), SongRequest.created_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def approve_request(db: Session, request_id: int):
        """Approve a request."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if request:
            request.status = "approved"  # type: ignore[assignment]
            request.next_queue_retry_at = None  # type: ignore[assignment]
            request.queue_terminal_failure = False  # type: ignore[assignment]
            request.last_queue_error = None  # type: ignore[assignment]
            request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()

    @staticmethod
    def reject_request(db: Session, request_id: int, notes: Optional[str] = None):
        """Reject a request."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if request:
            request.status = "rejected"  # type: ignore[assignment]
            if notes:
                request.notes = notes  # type: ignore[assignment]
            request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()

    @staticmethod
    def mark_queued(db: Session, request_id: int, radiodj_track_id: Optional[int] = None):
        """Mark request as queued in RadioDJ."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if request:
            request.status = "queued"  # type: ignore[assignment]
            if radiodj_track_id:
                request.radiodj_track_id = radiodj_track_id  # type: ignore[assignment]
            request.next_queue_retry_at = None  # type: ignore[assignment]
            request.queue_terminal_failure = False  # type: ignore[assignment]
            request.last_queue_error = None  # type: ignore[assignment]
            request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()

    @staticmethod
    def start_queue_attempt(
        db: Session,
        request_id: int,
        method: str = "api_db",
    ) -> Optional[SongRequest]:
        """Transition request to queue_pending and append attempt_started event."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if not request:
            return None

        request.status = "queue_pending"  # type: ignore[assignment]
        request.queue_attempt_count = (request.queue_attempt_count or 0) + 1  # type: ignore[assignment]
        request.last_queue_method = method  # type: ignore[assignment]
        request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        token = uuid4().hex
        RequestOperations._append_queue_event(
            db,
            request=request,
            event_type="attempt_started",
            method=method,
            attempt_number=request.queue_attempt_count or 0,
            idempotency_token=token,
        )
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def mark_queue_success(
        db: Session,
        request_id: int,
        method: str,
        radiodj_track_id: Optional[int] = None,
    ) -> Optional[SongRequest]:
        """Mark queue success and append event."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if not request:
            return None

        request.status = "queued"  # type: ignore[assignment]
        if radiodj_track_id:
            request.radiodj_track_id = radiodj_track_id  # type: ignore[assignment]
        request.next_queue_retry_at = None  # type: ignore[assignment]
        request.queue_terminal_failure = False  # type: ignore[assignment]
        request.last_queue_method = method  # type: ignore[assignment]
        request.last_queue_error = None  # type: ignore[assignment]
        request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        RequestOperations._append_queue_event(
            db,
            request=request,
            event_type="attempt_succeeded",
            method=method,
            attempt_number=request.queue_attempt_count or 0,
            idempotency_token=uuid4().hex,
        )
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def record_queue_failure(
        db: Session,
        request_id: int,
        error_message: str,
        method: str = "api_db",
        retry_delays_seconds: Optional[List[int]] = None,
    ) -> Optional[SongRequest]:
        """Record queue failure and schedule retry or terminal failure."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if not request:
            return None

        retry_delays_seconds = retry_delays_seconds or [60, 120, 240]
        attempt_number = request.queue_attempt_count or 0
        request.last_queue_method = method  # type: ignore[assignment]
        request.last_queue_error = error_message  # type: ignore[assignment]
        request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]

        RequestOperations._append_queue_event(
            db,
            request=request,
            event_type="attempt_failed",
            method=method,
            attempt_number=attempt_number,
            error_message=error_message,
            idempotency_token=uuid4().hex,
        )

        retry_index = max(attempt_number - 1, 0)
        if retry_index < len(retry_delays_seconds):
            retry_delay = retry_delays_seconds[retry_index]
            request.status = "approved"  # type: ignore[assignment]
            request.next_queue_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)  # type: ignore[assignment]
            RequestOperations._append_queue_event(
                db,
                request=request,
                event_type="retry_scheduled",
                method=method,
                attempt_number=attempt_number,
                error_message=f"retry_in_seconds={retry_delay}",
                idempotency_token=uuid4().hex,
            )
        else:
            request.status = "queue_failed_manual"  # type: ignore[assignment]
            request.queue_terminal_failure = True  # type: ignore[assignment]
            request.next_queue_retry_at = None  # type: ignore[assignment]
            RequestOperations._append_queue_event(
                db,
                request=request,
                event_type="terminal_failed",
                method=method,
                attempt_number=attempt_number,
                error_message=error_message,
                idempotency_token=uuid4().hex,
            )

        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def manual_requeue(db: Session, request_id: int, note: Optional[str] = None) -> Optional[SongRequest]:
        """Reset terminal queue failure and allow a fresh queue cycle."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if not request:
            return None

        request.status = "approved"  # type: ignore[assignment]
        request.queue_attempt_count = 0  # type: ignore[assignment]
        request.next_queue_retry_at = None  # type: ignore[assignment]
        request.queue_terminal_failure = False  # type: ignore[assignment]
        request.last_queue_error = None  # type: ignore[assignment]
        request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        if note:
            request.notes = note  # type: ignore[assignment]

        RequestOperations._append_queue_event(
            db,
            request=request,
            event_type="manual_requeue_requested",
            method="manual",
            attempt_number=0,
            error_message=note,
            idempotency_token=uuid4().hex,
        )

        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def _append_queue_event(
        db: Session,
        request: SongRequest,
        event_type: str,
        method: Optional[str],
        attempt_number: int,
        error_message: Optional[str] = None,
        idempotency_token: Optional[str] = None,
    ):
        """Append queue protocol event for diagnostics and auditing."""
        event = QueueProtocolEvent(
            request_id=request.id,
            event_type=event_type,
            method=method,
            attempt_number=attempt_number,
            error_message=error_message,
            idempotency_token=idempotency_token,
        )
        db.add(event)

    @staticmethod
    def mark_played(db: Session, request_id: int):
        """Mark request as played."""
        request = db.query(SongRequest).filter(SongRequest.id == request_id).first()
        if request:
            request.status = "played"  # type: ignore[assignment]
            request.actual_play_time = datetime.now(timezone.utc)  # type: ignore[assignment]
            request.play_count += 1  # type: ignore[assignment]
            request.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
