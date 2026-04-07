"""End-to-end-ish test: Jamendo fallback to RadioDJ sync."""

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import models
from src.database.operations import (
    ChatOperations,
    MessageOperations,
    RequestOperations,
    SongOperations,
)
from src.music_matching.matching_orchestrator import matching_orchestrator
from src.radiodj_integration.sync_service import sync_service


def _db_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    return session, engine


def test_jamendo_match_flows_to_radiodj(monkeypatch):
    db, engine = _db_session()
    try:
        # Prepare chat/message/extraction
        ChatOperations.create_or_update_chat(db, "test_chat")
        message = MessageOperations.create_message(
            db,
            message_id="msg1",
            chat_id="test_chat",
            sender_number="123",
            sender_name="tester",
            raw_text="play hello",
            timestamp=datetime.now(timezone.utc),
        )
        extraction = SongOperations.create_extraction(
            db,
            message_id=message.id,
            original_phrase="hello",
            confidence_score=0.9,
            extraction_method="test",
        )

        candidate = {"title": "Hello", "artist": "World"}

        # Force MusicBrainz miss and Jamendo hit
        monkeypatch.setattr(matching_orchestrator.musicbrainz, "search_song", lambda t, a: [])
        monkeypatch.setattr(matching_orchestrator.jamendo, "search_song", lambda t, a: [candidate])
        monkeypatch.setattr(
            matching_orchestrator.fuzzy,
            "get_best_match",
            lambda t, a, c: (candidate, 0.95),
        )
        monkeypatch.setattr(
            matching_orchestrator.validator,
            "validate",
            lambda m, c: (True, ""),
        )
        monkeypatch.setattr(
            matching_orchestrator.validator,
            "should_auto_approve",
            lambda m, c: True,
        )

        request_id = matching_orchestrator.process_extraction(
            db=db,
            extraction_id=extraction.id,
            title="Hello",
            artist="World",
            chat_id="test_chat",
            requested_by="tester",
        )

        assert request_id is not None

        # Ensure request is approved
        req = db.query(models.SongRequest).get(request_id)
        assert req.status == "approved"

        # Make sync_service see our approved request and succeed adding to RadioDJ
        monkeypatch.setattr(
            RequestOperations,
            "get_queue_candidates",
            lambda _db, _limit=50: [req],
        )
        monkeypatch.setattr(
            sync_service.playlist_manager,
            "add_song_to_playlist",
            lambda artist, title, playlist_id=None, use_api=True: 321,
        )

        stats = sync_service.sync_approved_requests(db, limit=10)
        db.refresh(req)

        assert stats == {"synced": 1, "failed": 0}
        assert req.status == "queued"
        assert req.radiodj_track_id == 321
    finally:
        db.close()
        engine.dispose()


def test_queue_protocol_retries_then_terminal_failure(monkeypatch):
    db, engine = _db_session()
    try:
        ChatOperations.create_or_update_chat(db, "test_chat")
        message = MessageOperations.create_message(
            db,
            message_id="msg2",
            chat_id="test_chat",
            sender_number="123",
            sender_name="tester",
            raw_text="play love",
            timestamp=datetime.now(timezone.utc),
        )
        extraction = SongOperations.create_extraction(
            db,
            message_id=message.id,
            original_phrase="love",
            confidence_score=0.9,
            extraction_method="test",
        )
        match = SongOperations.create_match(
            db,
            extraction_id=extraction.id,
            song_title="Love",
            artist_name="070 Shake",
            match_confidence=0.95,
            match_source="test",
        )
        req = RequestOperations.create_request(
            db,
            chat_id="test_chat",
            matched_song_id=match.id,
            requested_by="tester",
        )
        RequestOperations.approve_request(db, req.id)

        monkeypatch.setattr(
            RequestOperations,
            "get_queue_candidates",
            lambda _db, _limit=50: [req] if req.status == "approved" else [],
        )
        monkeypatch.setattr(
            sync_service.playlist_manager,
            "add_song_to_playlist",
            lambda artist, title, playlist_id=None, use_api=True: None,
        )

        for _ in range(4):
            sync_service.sync_approved_requests(db, limit=10)
            db.refresh(req)

        assert req.queue_attempt_count == 4
        assert req.queue_terminal_failure is True
        assert req.status == "queue_failed_manual"
        assert req.next_queue_retry_at is None
    finally:
        db.close()
        engine.dispose()


def test_process_request_records_protocol_success(monkeypatch):
    db, engine = _db_session()
    try:
        ChatOperations.create_or_update_chat(db, "test_chat")
        message = MessageOperations.create_message(
            db,
            message_id="msg3",
            chat_id="test_chat",
            sender_number="123",
            sender_name="tester",
            raw_text="play tonight",
            timestamp=datetime.now(timezone.utc),
        )
        extraction = SongOperations.create_extraction(
            db,
            message_id=message.id,
            original_phrase="tonight",
            confidence_score=0.9,
            extraction_method="test",
        )
        match = SongOperations.create_match(
            db,
            extraction_id=extraction.id,
            song_title="Tonight",
            artist_name="Miguel Migs",
            match_confidence=0.95,
            match_source="test",
        )
        req = RequestOperations.create_request(
            db,
            chat_id="test_chat",
            matched_song_id=match.id,
            requested_by="tester",
        )
        RequestOperations.approve_request(db, req.id)

        monkeypatch.setattr(
            sync_service.playlist_manager,
            "add_song_to_playlist",
            lambda artist, title, playlist_id=None, use_api=True: 38,
        )

        request = db.query(models.SongRequest).filter(models.SongRequest.id == req.id).first()
        assert request is not None

        result = sync_service.process_request(db, request)
        db.refresh(req)

        assert result is True
        assert req.status == "queued"
        assert req.radiodj_track_id == 38
        assert req.queue_attempt_count == 1
        assert req.last_queue_method == "api_db"

        events = (
            db.query(models.QueueProtocolEvent)
            .filter(models.QueueProtocolEvent.request_id == req.id)
            .order_by(models.QueueProtocolEvent.id.asc())
            .all()
        )
        assert [event.event_type for event in events] == ["attempt_started", "attempt_succeeded"]
    finally:
        db.close()
        engine.dispose()
