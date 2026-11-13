"""Database models for WhatsApp Song Scanner."""

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config.database import Base, engine

CASCADE_DELETE_ORPHAN = "all, delete-orphan"


class WhatsAppChat(Base):
    """WhatsApp chat tracking."""

    __tablename__ = "whatsapp_chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    chat_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_scan_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # cspell:ignore onupdate
    )

    # RELATIONSHIPS
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="chat",
        cascade=CASCADE_DELETE_ORPHAN,
    )
    song_requests: Mapped[List["SongRequest"]] = relationship(
        "SongRequest", back_populates="chat", cascade=CASCADE_DELETE_ORPHAN
    )


class ChatMessage(Base):
    """Individual WhatsApp messages."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    chat_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("whatsapp_chats.chat_id"),
        nullable=False,
    )
    sender_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_processed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    processing_attempts: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # RELATIONSHIPS
    chat: Mapped["WhatsAppChat"] = relationship("WhatsAppChat", back_populates="messages")
    extracted_songs: Mapped[List["ExtractedSong"]] = relationship(
        "ExtractedSong",
        back_populates="message",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class ExtractedSong(Base):
    """Songs extracted from messages."""

    __tablename__ = "extracted_songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    original_phrase: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # RELATIONSHIPS
    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="extracted_songs")
    matched_results: Mapped[List["MatchedSong"]] = relationship(
        "MatchedSong",
        back_populates="extraction",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class MatchedSong(Base):
    """Verified song matches from APIs."""

    __tablename__ = "matched_songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    extraction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("extracted_songs.id"),
        nullable=False,
    )
    song_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    artist_name: Mapped[Optional[str]] = mapped_column(String(500), index=True, nullable=True)
    album_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    spotify_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deezer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    match_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    match_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    match_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    is_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    verification_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    # RELATIONSHIPS
    extraction: Mapped["ExtractedSong"] = relationship(
        "ExtractedSong",
        back_populates="matched_results",
    )
    requests: Mapped[List["SongRequest"]] = relationship(
        "SongRequest",
        back_populates="matched_song",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class SongRequest(Base):
    """Final song requests for RadioDJ."""

    __tablename__ = "song_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("whatsapp_chats.chat_id"),
        nullable=False,
    )
    matched_song_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matched_songs.id"),
        nullable=False,
    )
    requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_priority: Mapped[Optional[int]] = mapped_column(Integer, default=1, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(
        String(50), default="pending", index=True
    )  # pending, approved, queue_pending, queue_failed_manual, queued, played, rejected
    radiodj_playlist_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    radiodj_track_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    queue_attempt_count: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    next_queue_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    queue_terminal_failure: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        default=False,
        nullable=True,
    )
    last_queue_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_queue_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_play_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_play_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    play_count: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=True,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # cspell:ignore onupdate
    )

    # RELATIONSHIPS
    chat: Mapped["WhatsAppChat"] = relationship("WhatsAppChat", back_populates="song_requests")
    matched_song: Mapped["MatchedSong"] = relationship("MatchedSong", back_populates="requests")
    queue_events: Mapped[List["QueueProtocolEvent"]] = relationship(
        "QueueProtocolEvent",
        back_populates="request",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class QueueProtocolEvent(Base):
    """Audit trail for queueing attempts and transitions."""

    __tablename__ = "queue_protocol_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("song_requests.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    attempt_number: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_token: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=True,
    )

    request: Mapped["SongRequest"] = relationship("SongRequest", back_populates="queue_events")


def init_database():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_queue_protocol_schema()
    print("Database tables created successfully")


def drop_all_tables():
    """Drop all database tables (use with caution)."""
    Base.metadata.drop_all(bind=engine)
    print("All database tables dropped")


def _ensure_queue_protocol_schema():
    """Apply lightweight schema upgrades for queue protocol columns/tables."""
    inspector = inspect(engine)

    if "song_requests" in inspector.get_table_names():
        existing_columns = {col["name"] for col in inspector.get_columns("song_requests")}
        column_specs = {
            "queue_attempt_count": "INTEGER DEFAULT 0",
            "next_queue_retry_at": "DATETIME",
            "queue_terminal_failure": "BOOLEAN DEFAULT 0",
            "last_queue_method": "VARCHAR(50)",
            "last_queue_error": "TEXT",
        }

        with engine.begin() as conn:
            for col_name, col_type in column_specs.items():
                if col_name not in existing_columns:
                    conn.execute(
                        text(f"ALTER TABLE song_requests ADD COLUMN {col_name} {col_type}")
                    )

    # Ensure new audit table exists.
    Base.metadata.tables["queue_protocol_events"].create(bind=engine, checkfirst=True)
