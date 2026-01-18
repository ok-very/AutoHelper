"""
Tests for generate module.
"""

import json
from pathlib import Path

# Fixtures from conftest.py are automatically available
# client, temp_dir


def test_generate_intake_manifest(client, temp_dir):
    """Test generating an intake manifest."""
    # Setup - use temp_dir which is an allowed root
    folder = temp_dir / "intake"
    folder.mkdir()
    (folder / "file1.txt").write_text("content1")
    (folder / "file2.pdf").write_text("content2")
    (folder / "subdir").mkdir()
    (folder / "subdir" / "file3.jpg").write_text("content3")
    
    # Act
    resp = client.post("/generate/intake-manifest", json={
        "context_id": "ctx-123",
        "intake_folder": str(folder),
        "options": {"overwrite": True}
    })
    
    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_type"] == "intake_manifest"
    assert data["ref_id"] is not None
    
    artifact_path = Path(data["path"])
    assert artifact_path.exists()
    assert artifact_path.name == "_intake_manifest.json"
    
    # Check content
    manifest = json.loads(artifact_path.read_text())
    assert manifest["context_id"] == "ctx-123"
    assert manifest["file_count"] == 3
    assert len(manifest["files"]) == 3
    
    paths = [f["path"] for f in manifest["files"]]
    # Normalize paths for windows/unix check
    paths = [p.replace("\\", "/") for p in paths]
    assert "file1.txt" in paths
    assert "subdir/file3.jpg" in paths


def test_generate_report(client, temp_dir):
    """Test generating a report."""
    # Setup
    output_dir = temp_dir / "reports"
    output_dir.mkdir()
    
    template = "# Report for {{project}}\nStatus: {{status}}"
    payload = {"project": "Alpha", "status": "Green"}
    
    # Act
    resp = client.post("/generate/report", json={
        "context_id": "ctx-456",
        "template": template,
        "payload": payload,
        "options": {"output_folder": str(output_dir), "overwrite": True}
    })
    
    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_type"] == "report"
    assert Path(data["path"]).exists()
    
    content = Path(data["path"]).read_text()
    assert "# Report for Alpha" in content
    assert "Status: Green" in content


def test_generate_error_invalid_folder(client):
    """Test error when folder does not exist."""
    resp = client.post("/generate/intake-manifest", json={
        "context_id": "ctx-err",
        "intake_folder": "/non/existent/path/123987"
    })
    assert resp.status_code == 400


def test_generate_overwrite_protection(client, temp_dir):
    """Test overwrite protection."""
    folder = temp_dir / "intake_overwrite"
    folder.mkdir()
    (folder / "_intake_manifest.json").write_text("{}")
    
    # Attempt without overwrite=True
    resp = client.post("/generate/intake-manifest", json={
        "context_id": "ctx-ovr",
        "intake_folder": str(folder)
    })
    assert resp.status_code == 409
