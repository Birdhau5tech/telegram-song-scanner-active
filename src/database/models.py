"""Database models for WhatsApp Song Scanner."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    inspect,
    text,
)
from sqlalchemy.orm import relationship

from config.database import Base, engine

CASCADE_DELETE_ORPHAN = "all, delete-orphan"


class WhatsAppChat(Base):
    """WhatsApp chat tracking."""

    __tablename__ = "whatsapp_chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(255), unique=True, nullable=False, index=True)
    chat_name = Column(String(255))
    last_message_id = Column(String(255))
    last_scan_time = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # cspell:ignore onupdate
    )

    # RELATIONSHIPS
    messages = relationship("ChatMessage", back_populates="chat", cascade=CASCADE_DELETE_ORPHAN)
    song_requests = relationship(
        "SongRequest", back_populates="chat", cascade=CASCADE_DELETE_ORPHAN
    )


class ChatMessage(Base):
    """Individual WhatsApp messages."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    chat_id = Column(String(255), ForeignKey("whatsapp_chats.chat_id"), nullable=False)
    sender_number = Column(String(50))
    sender_name = Column(String(255))
    raw_text = Column(Text, nullable=False)
    cleaned_text = Column(Text)
    timestamp = Column(DateTime, nullable=False, index=True)
    is_processed = Column(Boolean, default=False)
    processing_attempts = Column(Integer, default=0)
    processing_error = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # RELATIONSHIPS
    chat = relationship("WhatsAppChat", back_populates="messages")
    extracted_songs = relationship(
        "ExtractedSong",
        back_populates="message",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class ExtractedSong(Base):
    """Songs extracted from messages."""

    __tablename__ = "extracted_songs"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    original_phrase = Column(String(500), nullable=False)
    confidence_score = Column(Float)
    extraction_method = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # RELATIONSHIPS
    message = relationship("ChatMessage", back_populates="extracted_songs")
    matched_results = relationship(
        "MatchedSong",
        back_populates="extraction",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class MatchedSong(Base):
    """Verified song matches from APIs."""

    __tablename__ = "matched_songs"

    id = Column(Integer, primary_key=True)
    extraction_id = Column(Integer, ForeignKey("extracted_songs.id"), nullable=False)
    song_title = Column(String(500), nullable=False, index=True)
    artist_name = Column(String(500), index=True)
    album_name = Column(String(500))
    musicbrainz_id = Column(String(255), index=True)
    spotify_id = Column(String(255))
    deezer_id = Column(String(255))
    match_confidence = Column(Float)
    match_source = Column(String(50))
    match_metadata = Column(JSON)
    is_verified = Column(Boolean, default=False)
    verification_method = Column(String(50))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # RELATIONSHIPS
    extraction = relationship("ExtractedSong", back_populates="matched_results")
    requests = relationship(
        "SongRequest",
        back_populates="matched_song",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class SongRequest(Base):
    """Final song requests for RadioDJ."""

    __tablename__ = "song_requests"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(255), ForeignKey("whatsapp_chats.chat_id"), nullable=False)
    matched_song_id = Column(Integer, ForeignKey("matched_songs.id"), nullable=False)
    requested_by = Column(String(255))
    request_priority = Column(Integer, default=1)
    status = Column(
        String(50), default="pending", index=True
    )  # pending, approved, queue_pending, queue_failed_manual, queued, played, rejected
    radiodj_playlist_id = Column(Integer)
    radiodj_track_id = Column(Integer)
    queue_attempt_count = Column(Integer, default=0)
    next_queue_retry_at = Column(DateTime)
    queue_terminal_failure = Column(Boolean, default=False)
    last_queue_method = Column(String(50))
    last_queue_error = Column(Text)
    scheduled_play_time = Column(DateTime)
    actual_play_time = Column(DateTime)
    play_count = Column(Integer, default=0)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # cspell:ignore onupdate
    )

    # RELATIONSHIPS
    chat = relationship("WhatsAppChat", back_populates="song_requests")
    matched_song = relationship("MatchedSong", back_populates="requests")
    queue_events = relationship(
        "QueueProtocolEvent",
        back_populates="request",
        cascade=CASCADE_DELETE_ORPHAN,
    )


class QueueProtocolEvent(Base):
    """Audit trail for queueing attempts and transitions."""

    __tablename__ = "queue_protocol_events"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("song_requests.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    method = Column(String(32))
    attempt_number = Column(Integer, default=0)
    error_message = Column(Text)
    idempotency_token = Column(String(64), index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    request = relationship("SongRequest", back_populates="queue_events")


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
