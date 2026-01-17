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

@pytest.fixture
def mock_settings():
    from autohelper.config import Settings, init_settings
    s = Settings(mail_enabled=True)
    init_settings(s)
    return s

@pytest.fixture
def db_session(tmp_path):
    from autohelper.db import init_db, get_db
    # Init temp file DB
    db_file = tmp_path / "test.db"
    db = init_db(db_file)
    # Create Tables manually for test
    db.execute("CREATE TABLE mail_ingestion_log (id INTEGER PRIMARY KEY AUTOINCREMENT, source_path TEXT NOT NULL, ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP, email_count INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', error_message TEXT)")
    db.execute("CREATE TABLE transient_emails (id TEXT PRIMARY KEY, subject TEXT, sender TEXT, received_at DATETIME, project_id TEXT, body_preview TEXT, metadata JSON, ingestion_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    return db

def test_ingest_pst(mock_settings, db_session):
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
        
        # Test Ingestion
        service = MailService()
        
        # We need to mock os.path.exists for the PST file
        with patch('pathlib.Path.exists', return_value=True):
             result = service.ingest_pst("C:\\TestPST.pst")
             
        assert result['success'] is True
        assert result['count'] == 1
        
        # Verify DB content
        log = db_session.execute("SELECT * FROM mail_ingestion_log").fetchone()
        assert log is not None
        assert log[1] == "C:\\TestPST.pst" # source_path
        assert log[4] == "completed" # status
        
        email = db_session.execute("SELECT * FROM transient_emails").fetchone()
        assert email is not None
        assert email[0] == "TEST_ID_123"
        assert email[4] == "Qualex - Artesia" # project_id
