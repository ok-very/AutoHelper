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
