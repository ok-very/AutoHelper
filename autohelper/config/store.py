
import json
import os
from pathlib import Path
from typing import Any

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

CONFIG_PATH = Path("./data/config.json")

class ConfigStore:
    """
    Manages persistent configuration validation and storage.
    """
    
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._ensure_dir()
    
    def _ensure_dir(self):
        if not self.config_path.parent.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        """Load configuration from disk."""
        if not self.config_path.exists():
            return self._get_defaults()
            
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_defaults()
    
    def save(self, config: dict[str, Any]) -> None:
        """Save configuration to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
    
    def _get_defaults(self) -> dict[str, Any]:
        """Return default configuration."""
        # Try to infer from environment/existing settings if possible,
        # but otherwise valid empty defaults
        return {
            "allowed_roots": [],
            "excludes": ["pyc", "__pycache__", ".git", ".idea", "node_modules"],
            "mail_enabled": False,
            "mail_poll_interval": 30,
        }
