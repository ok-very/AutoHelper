import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
import json

# Mock win32com before importing service
with patch.dict('sys.modules', {'win32com': MagicMock(), 'win32com.client': MagicMock(), 'pythoncom': MagicMock()}):
    from autohelper.modules.mail.service import MailService, extract_project_info, clean_subject

def test_extract_project_info():
    # Test cases
    cases = [
        ("Qualex - Artesia - Update", ("Qualex", "Artesia", "Qualex - Artesia")),
        ("RE: Anthem - Citizen - Invoice", ("Anthem", "Citizen", "Anthem - Citizen")),
        ("Unknown - Project - Topic", ("", "", "_Uncategorized")),
        ("Just a subject", ("", "", "_Uncategorized")),
        ("[EXT] Bosa - Parkway - Meeting", ("Bosa", "Parkway", "Bosa - Parkway")),
    ]

    for subject, expected in cases:
        assert extract_project_info(subject) == expected

def test_clean_subject():
    assert clean_subject("RE: Hello") == "Hello"
    assert clean_subject("[EXT] FW: Update") == "Update"


def test_ingest_pst(tmp_path):
    """Test PST ingestion with mocked Outlook and settings."""
    from autohelper.config import Settings, init_settings, reset_settings
    from autohelper.db import init_db

    # Reset any cached settings from other tests
    reset_settings()

    # Setup settings with tmp_path as the ingest path
    settings = Settings(mail_enabled=True, mail_ingest_path=tmp_path)
    init_settings(settings)

    # Init temp DB
    db_file = tmp_path / "test.db"
    db = init_db(db_file)
    # Create tables manually for test
    db.execute("CREATE TABLE mail_ingestion_log (id INTEGER PRIMARY KEY AUTOINCREMENT, source_path TEXT NOT NULL, ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP, email_count INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', error_message TEXT)")
    db.execute("CREATE TABLE transient_emails (id TEXT PRIMARY KEY, subject TEXT, sender TEXT, received_at DATETIME, project_id TEXT, body_preview TEXT, metadata JSON, ingestion_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

    # Mock Outlook
    with patch('autohelper.modules.mail.service.MailService._get_outlook') as mock_get_outlook:
        mock_outlook = MagicMock()
        mock_namespace = MagicMock()
        mock_folder = MagicMock()

        # Setup Folder Structure
        mock_mail_item = MagicMock()
        mock_mail_item.Class = 43 # olMail
        mock_mail_item.Subject = "Qualex - Artesia - Test"
        mock_mail_item.EntryID = "TEST_ID_123"
        mock_mail_item.SenderEmailAddress = "test@example.com"
        mock_mail_item.Body = "Test Body"
        mock_mail_item.ReceivedTime = datetime.now()

        mock_folder.Name = "TestPST"
        mock_folder.Items = [mock_mail_item]
        mock_folder.Folders = []

        mock_namespace.Folders = [mock_folder]
        mock_outlook.GetNamespace.return_value = mock_namespace
        mock_get_outlook.return_value = mock_outlook

        # Test Ingestion - use a path under the configured mail_ingest_path (tmp_path)
        pst_file = tmp_path / "TestPST.pst"
        pst_path = str(pst_file)

        # Create fresh service instance with current settings
        service = MailService()
        # Force reload settings to get the test settings
        service.settings = settings

        # We need to mock os.path.exists for the PST file
        with patch('pathlib.Path.exists', return_value=True):
             result = service.ingest_pst(pst_path)

        assert result['success'] is True, f"Ingestion failed: {result.get('error')}"
        assert result['count'] == 1

        # Verify DB content
        log = db.execute("SELECT * FROM mail_ingestion_log").fetchone()
        assert log is not None
        assert log[1] == pst_path # source_path
        assert log[4] == "completed" # status

        email = db.execute("SELECT * FROM transient_emails").fetchone()
        assert email is not None
        assert email[0] == "TEST_ID_123"
        assert email[4] == "Qualex - Artesia" # project_id

    # Cleanup
    reset_settings()


def test_ingest_pst_invalid_extension(tmp_path):
    """Ensure ingest_pst rejects non-PST/OST files."""
    from autohelper.config import Settings, init_settings, reset_settings
    from autohelper.db import init_db

    reset_settings()
    settings = Settings(mail_enabled=True, mail_ingest_path=tmp_path)
    init_settings(settings)

    db_file = tmp_path / "test.db"
    db = init_db(db_file)
    db.execute(
        "CREATE TABLE mail_ingestion_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "source_path TEXT NOT NULL, "
        "ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "email_count INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'pending', "
        "error_message TEXT)"
    )
    db.execute(
        "CREATE TABLE transient_emails ("
        "id TEXT PRIMARY KEY, "
        "subject TEXT, "
        "sender TEXT, "
        "received_at DATETIME, "
        "project_id TEXT, "
        "body_preview TEXT, "
        "metadata JSON, "
        "ingestion_id INTEGER, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )

    # Create a non-PST file inside the ingest directory
    invalid_file = tmp_path / "not_a_pst.txt"
    invalid_file.write_text("dummy content")

    service = MailService()
    service.settings = settings
    result = service.ingest_pst(str(invalid_file))

    assert result["success"] is False
    # Error message should indicate invalid extension / file type
    assert "pst" in result["error"].lower() or "ost" in result["error"].lower()

    reset_settings()


def test_ingest_pst_outside_ingest_path(tmp_path):
    """Ensure ingest_pst rejects files outside configured mail_ingest_path."""
    from autohelper.config import Settings, init_settings, reset_settings
    from autohelper.db import init_db

    reset_settings()
    ingest_dir = tmp_path / "ingest"
    ingest_dir.mkdir()
    settings = Settings(mail_enabled=True, mail_ingest_path=ingest_dir)
    init_settings(settings)

    db_file = tmp_path / "test.db"
    db = init_db(db_file)
    db.execute(
        "CREATE TABLE mail_ingestion_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "source_path TEXT NOT NULL, "
        "ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "email_count INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'pending', "
        "error_message TEXT)"
    )
    db.execute(
        "CREATE TABLE transient_emails ("
        "id TEXT PRIMARY KEY, "
        "subject TEXT, "
        "sender TEXT, "
        "received_at DATETIME, "
        "project_id TEXT, "
        "body_preview TEXT, "
        "metadata JSON, "
        "ingestion_id INTEGER, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )

    # Create a PST file outside the ingest directory
    outside_file = tmp_path / "outside.pst"
    outside_file.write_bytes(b"dummy pst content")

    service = MailService()
    service.settings = settings
    result = service.ingest_pst(str(outside_file))

    assert result["success"] is False
    # Error should indicate path restriction / outside ingest directory
    assert "ingest" in result["error"].lower() or str(ingest_dir).lower() in result["error"].lower()

    reset_settings()


def test_ingest_pst_missing_file(tmp_path):
    """Ensure ingest_pst handles missing/nonexistent files safely."""
    from autohelper.config import Settings, init_settings, reset_settings
    from autohelper.db import init_db

    reset_settings()
    settings = Settings(mail_enabled=True, mail_ingest_path=tmp_path)
    init_settings(settings)

    db_file = tmp_path / "test.db"
    db = init_db(db_file)
    db.execute(
        "CREATE TABLE mail_ingestion_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "source_path TEXT NOT NULL, "
        "ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "email_count INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'pending', "
        "error_message TEXT)"
    )
    db.execute(
        "CREATE TABLE transient_emails ("
        "id TEXT PRIMARY KEY, "
        "subject TEXT, "
        "sender TEXT, "
        "received_at DATETIME, "
        "project_id TEXT, "
        "body_preview TEXT, "
        "metadata JSON, "
        "ingestion_id INTEGER, "
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )

    missing_file = tmp_path / "missing.pst"
    # Do not create the file

    service = MailService()
    service.settings = settings
    result = service.ingest_pst(str(missing_file))

    assert result["success"] is False
    assert "not found" in result["error"].lower()

    reset_settings()
