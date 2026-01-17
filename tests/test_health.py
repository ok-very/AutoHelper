"""Tests for health endpoints."""

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_returns_ok(self, client: TestClient) -> None:
        """GET /health should return ok status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "version" in data
    
    def test_status_returns_details(self, client: TestClient) -> None:
        """GET /status should return detailed status."""
        response = client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["db_reachable"] is True
        assert "migrations" in data
        assert "index" in data
        assert "roots" in data
    
    def test_root_endpoint(self, client: TestClient) -> None:
        """GET / should return service info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "AutoHelper"
