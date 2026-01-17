
import json
from pathlib import Path
from autohelper.config.store import ConfigStore

def test_config_store_defaults(tmp_path):
    store = ConfigStore(config_path=tmp_path / "config.json")
    defaults = store.load()

    # existing defaults
    assert "allowed_roots" in defaults
    assert isinstance(defaults["allowed_roots"], list)
    assert "excludes" in defaults

    # new mail-related defaults from _get_defaults()
    assert "mail_enabled" in defaults
    assert isinstance(defaults["mail_enabled"], bool)

    assert "mail_poll_interval" in defaults
    assert isinstance(defaults["mail_poll_interval"], int)

def test_config_store_save_load(tmp_path):
    config_path = tmp_path / "config.json"
    store = ConfigStore(config_path=config_path)
    
    new_config = {
        "allowed_roots": ["/tmp/test"],
        "excludes": ["exe"]
    }
    store.save(new_config)
    
    loaded = store.load()
    assert loaded == new_config
    
    # Verify file content
    with open(config_path, "r") as f:
        data = json.load(f)
        assert data == new_config


def test_config_store_corrupt_json_returns_defaults(tmp_path):
    """Ensure ConfigStore handles corrupt JSON gracefully by returning defaults."""
    config_path = tmp_path / "config.json"
    # Write invalid JSON directly to the config file
    config_path.write_text("{ invalid json }", encoding="utf-8")

    store = ConfigStore(config_path=config_path)

    # load() should not raise and should fall back to defaults
    loaded = store.load()

    assert "allowed_roots" in loaded
    assert isinstance(loaded["allowed_roots"], list)
    assert "excludes" in loaded
    assert "mail_enabled" in loaded
    assert "mail_poll_interval" in loaded
