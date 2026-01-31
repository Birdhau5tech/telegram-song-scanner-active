"""Main application entry point."""

from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy.exc import SQLAlchemyError

from config.database import SessionLocal
from config.settings import APP_CONFIG
from src.core.health_check import health_check
from src.core.scheduler import scheduler
from src.core.state_manager import state_manager
from src.database.models import init_database
from src.database.operations import RequestOperations
from src.utils.logger import get_logger
from src.message_handler import message_handler

logger = get_logger(__name__)


app = Flask(__name__)
CORS(app)


@app.route("/api/v1/health", methods=["GET"])
def get_health():
    """Health check endpoint."""
    try:
        health_status = health_check.get_health()
        status_code = 200 if health_status["status"] in ["healthy", "degraded"] else 503
        return jsonify(health_status), status_code
    except (KeyError, ValueError, TypeError) as exc:
        logger.exception("Health check error")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/v1/metrics", methods=["GET"])
def get_metrics():
    """Metrics endpoint."""
    try:
        metrics = health_check.get_metrics()
        return jsonify(metrics), 200
    except (KeyError, ValueError, TypeError) as exc:
        logger.exception("Metrics error")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/webhook/telegram", methods=["POST"])
def telegram_webhook():
    """Handle incoming Telegram webhook (POST JSON from Telegram)."""
    try:
        update = request.get_json()
        logger.info("Received Telegram update")

        db = SessionLocal()
        try:
            success = message_handler.handle_telegram_update(db, update)
            if success:
                return jsonify({"status": "success"}), 200
            return jsonify({"status": "ignored"}), 200
        finally:
            db.close()
    except (SQLAlchemyError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Telegram webhook error")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/requests/pending", methods=["GET"])
def get_pending_requests():
    """Get pending song requests."""
    try:
        limit = int(request.args.get("limit", 50))

        db = SessionLocal()
        try:
            requests_list = RequestOperations.get_pending_requests(db, limit)

            results = []
            for req in requests_list:
                results.append(
                    {
                        "id": req.id,
                        "chat_id": req.chat_id,
                        "requested_by": req.requested_by,
                        "song_title": req.matched_song.song_title,
                        "artist_name": req.matched_song.artist_name,
                        "status": req.status,
                        "priority": req.request_priority,
                        "created_at": req.created_at.isoformat(),
                    }
                )

            return jsonify({"requests": results, "count": len(results)}), 200
        finally:
            db.close()
    except (SQLAlchemyError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Error getting pending requests")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/requests/approve", methods=["POST"])
def approve_request():
    """Approve a song request."""
    try:
        data = request.get_json()
        request_id = data.get("request_id")

        if not request_id:
            return jsonify({"error": "request_id required"}), 400

        db = SessionLocal()
        try:
            RequestOperations.approve_request(db, request_id)
            return jsonify({"status": "approved"}), 200
        finally:
            db.close()
    except (SQLAlchemyError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Error approving request")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/requests/reject", methods=["POST"])
def reject_request():
    """Reject a song request."""
    try:
        data = request.get_json()
        request_id = data.get("request_id")
        notes = data.get("notes")

        if not request_id:
            return jsonify({"error": "request_id required"}), 400

        db = SessionLocal()
        try:
            RequestOperations.reject_request(db, request_id, notes)
            return jsonify({"status": "rejected"}), 200
        finally:
            db.close()
    except (SQLAlchemyError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Error rejecting request")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/scan/status", methods=["GET"])
def scan_status():
    """Get scan status."""
    try:
        state = state_manager.get_state()
        return (
            jsonify(
                {
                    "status": state["status"],
                    "last_scan": (state["last_scan"].isoformat() if state["last_scan"] else None),
                    "stats": state["stats"],
                }
            ),
            200,
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.exception("Error getting scan status")
        return jsonify({"error": str(exc)}), 500


def initialize_app():
    """Initialize application."""
    logger.info("Initializing Song Scanner...")

    try:
        init_database()
        logger.info("Database initialized")
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.exception(
            "Database may already be initialized: %s",
            exc,
        )

    scheduler.start()
    logger.info("Application initialized successfully")


@app.route("/", methods=["GET"])
def dashboard():
    """Serve the dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return f.read()
    return jsonify({"error": "Dashboard not found"}), 404


def main():
    """Run the application."""
    initialize_app()

    logger.info(
        "Starting Flask server on %s:%s",
        APP_CONFIG["host"],
        APP_CONFIG["port"],
    )
    app.run(host=APP_CONFIG["host"], port=APP_CONFIG["port"], debug=APP_CONFIG["debug"])


if __name__ == "__main__":
    main()
