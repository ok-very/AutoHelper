
import json
from pathlib import Path
from autohelper.config.store import ConfigStore

def test_config_store_defaults(tmp_path):
    store = ConfigStore(config_path=tmp_path / "config.json")
    defaults = store.load()
    assert "allowed_roots" in defaults
    assert isinstance(defaults["allowed_roots"], list)
    assert "excludes" in defaults

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
