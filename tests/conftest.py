"""Shared fixtures for BFA Todo tests."""

import os
import pytest
from docx import Document

# Source 1 (PM's gdocs docx) path — set via env var or default
_DEFAULT_SOURCE_1 = r"C:\Users\Neal\Downloads\2026_01_08_Ballard Fine Art To Do - gdocs.docx"


@pytest.fixture(scope="session")
def pm_doc():
    """Load the PM's canonical docx (source 1) once for all tests."""
    path = os.environ.get("BFA_SOURCE_1", _DEFAULT_SOURCE_1)
    if not os.path.exists(path):
        pytest.skip(f"Source 1 docx not found: {path}")
    return Document(path)
