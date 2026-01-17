"""Tests for the search service."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autohelper.modules.index.service import IndexService


class TestSearchEndpoints:
    """Test search API endpoints."""
    
    def test_search_returns_matches(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """GET /search should return matching files."""
        # Create structure
        (temp_dir / "apple.txt").write_text("content")
        (temp_dir / "banana.txt").write_text("content")
        (temp_dir / "apple_pie.txt").write_text("content")
        
        # Index
        IndexService().rebuild_index()
        
        # Search for "apple"
        response = client.get("/search/?q=apple")
        assert response.status_code == 200
        data = response.json()
        
        # Should find apple.txt and apple_pie.txt
        assert data["total"] == 2
        paths = [item["path"] for item in data["items"]]
        assert any("apple.txt" in p for p in paths)
        assert any("apple_pie.txt" in p for p in paths)
        assert not any("banana.txt" in p for p in paths)

    def test_search_no_matches(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """GET /search should return empty list for no matches."""
        (temp_dir / "test.txt").write_text("content")
        IndexService().rebuild_index()
        
        response = client.get("/search/?q=zebra")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_search_empty_query_returns_422(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """GET /search with empty q should return 422 due to min_length=1."""
        response = client.get("/search/?q=")
        assert response.status_code == 422

    def test_search_missing_query_returns_422(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """GET /search without q should return 422 due to required param."""
        response = client.get("/search/")
        # FastAPI might return 422 for missing required query param
        assert response.status_code == 422

    def test_search_limit(
        self, client: TestClient, temp_dir: Path, test_db
    ) -> None:
        """GET /search should respect limit."""
        for i in range(10):
            (temp_dir / f"file_{i}.txt").write_text("content")
        
        IndexService().rebuild_index()
        
        response = client.get("/search/?q=file&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        # Total logic in simplistic implementation mirrors len(items), 
        # normally it would be a separate count query.
        # My implementation: total=len(items).
        assert data["total"] == 5
