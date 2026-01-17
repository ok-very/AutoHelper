"""
Configuration settings using pydantic-settings.
Supports env vars and optional .env file.
"""

from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with env var support."""
    
    model_config = SettingsConfigDict(
        env_prefix="AUTOHELPER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8100
    debug: bool = False
    
    # Database
    db_path: Path = Field(default=Path("./data/autohelper.db"))
    
    # Filesystem roots (comma-separated paths)
    allowed_roots: Annotated[list[str], Field(default_factory=list)]
    
    # Security
    block_symlinks: bool = True
    
    # OneDrive Files On-Demand detection (Windows only)
    onedrive_detection: bool = True
    
    # Logging
    log_level: str = "INFO"
    
    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])
    
    # Mail Polling
    mail_enabled: bool = False
    mail_poll_interval: int = 30  # seconds
    mail_output_path: Path = Field(default_factory=lambda: Path(Path.home() / "OneDrive" / "Emails"))
    mail_ingest_path: Path = Field(default_factory=lambda: Path(Path.home() / "Documents" / "AutoHelper" / "Ingest"))
    
    # Context Layer / External Data Sources
    autoart_api_url: str = "http://localhost:3000"
    autoart_api_key: str = ""  # Optional API key for AutoArt
    autoart_session_id: str = ""  # Session ID from AutoArt pairing (Monday token proxied via this)
    context_providers: list[str] = Field(default=["autoart", "monday"])  # Priority order
    
    def get_allowed_roots(self) -> list[Path]:
        """Parse and validate allowed root paths."""
        return [Path(r).resolve() for r in self.allowed_roots if r]


# Global settings instance for caching
_settings: Settings | None = None


def init_settings(settings: Settings) -> None:
    """Initialize global settings (call during app startup or test setup)."""
    global _settings
    _settings = settings


def get_settings() -> Settings:
    """Get cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None
