"""Flask endpoint smoke tests."""

import pytest
from unittest.mock import patch
from src.main import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


class TestHealthEndpoint:
    """Test /api/v1/health endpoint."""

    def test_health_status(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert data["status"] in ["healthy", "ok", "operational", "degraded"]


class TestMetricsEndpoint:
    """Test /api/v1/metrics endpoint."""

    def test_metrics_status(self, client):
        """Test metrics endpoint."""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, dict)


class TestScanStatusEndpoint:
    """Test /api/v1/scan/status endpoint."""

    def test_scan_status_endpoint(self, client):
        """Test scan status endpoint."""
        response = client.get("/api/v1/scan/status")
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data


class TestWebhookEndpoint:
    """Test webhook endpoints."""

    @patch("src.message_handler.MessageHandler.handle_telegram_update")
    def test_telegram_webhook(self, mock_handle, client):
        """Test Telegram webhook endpoint."""
        mock_handle.return_value = True

        payload = {
            "message": {
                "message_id": 1,
                "date": 1700000000,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 456, "username": "tester"},
                "text": "test message",
            }
        }

        response = client.post(
            "/api/v1/webhook/telegram", json=payload, follow_redirects=True
        )
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_endpoint(self, client):
        """Test invalid endpoint returns 404."""
        response = client.get("/invalid/endpoint")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test method not allowed."""
        response = client.post("/api/v1/health")
        assert response.status_code in [405, 400]
