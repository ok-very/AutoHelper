import json
from pathlib import Path
from typing import Any, cast

from autohelper.config.manifest import DEFAULTS
from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir

logger = get_logger(__name__)

CONFIG_PATH = data_dir() / "config.json"


class ConfigStore:
    """
    Manages persistent configuration validation and storage.
    """

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        if not self.config_path.parent.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        """Load configuration from disk."""
        if not self.config_path.exists():
            return self._get_defaults()

        try:
            with open(self.config_path, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_defaults()

    def save(self, config: dict[str, Any]) -> None:
        """Save configuration to disk."""
        """Save configuration to disk atomically."""
        import os
        import tempfile

        try:
            # Write to a temp file in the same directory, flush and fsync, then atomically replace.
            dirpath = self.config_path.parent
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(dirpath), delete=False) as tf:
                json.dump(config, tf, indent=2)
                tf.flush()
                os.fsync(tf.fileno())
                temp_path = Path(tf.name)
            # Atomic replace
            os.replace(str(temp_path), str(self.config_path))
        except Exception as e:
            # Attempt to clean up temp file if it exists
            try:
                if 'temp_path' in locals() and temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            logger.error(f"Failed to save config: {e}")
            raise

    def _get_defaults(self) -> dict[str, Any]:
        """Return default configuration derived from the manifest."""
        return dict(DEFAULTS)
