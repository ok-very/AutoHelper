"""Pytest fixtures for AutoHelper tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autohelper.app import build_app
from autohelper.config import Settings, init_settings, reset_settings
from autohelper.db import init_db
from autohelper.db.migrate import run_migrations


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temp paths."""
    return Settings(
        host="127.0.0.1",
        port=8100,
        debug=True,
        db_path=temp_dir / "test.db",
        allowed_roots=[str(temp_dir)],
        block_symlinks=True,
        log_level="DEBUG",
    )


@pytest.fixture
def test_db(test_settings: Settings):
    """Initialize test database with migrations."""
    # Initialize settings so services use test settings
    init_settings(test_settings)
    db = init_db(test_settings.db_path)
    run_migrations(db)
    yield db
    db.close()
    reset_settings()


@pytest.fixture
def client(test_settings: Settings, test_db) -> Generator[TestClient, None, None]:
    """Create test client with initialized database."""
    app = build_app(test_settings)
    with TestClient(app) as c:
        yield c
