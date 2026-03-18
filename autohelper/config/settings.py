"""
Configuration settings using pydantic-settings.
Supports env vars and optional .env file.

Config values can also be persisted to config.json via ConfigStore.
For values that need to persist across restarts (like autoart_link_key),
we read from config.json during Settings initialization.
"""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from autohelper.config.manifest import CONFIG_KEYS
from autohelper.shared.paths import data_dir

# =============================================================================
# Metadata Backend Types
# =============================================================================

MetadataBackendType = Literal["manifest", "sharepoint"]


class Settings(BaseSettings):
    """Application settings with env var support."""

    model_config = SettingsConfigDict(
        env_prefix="AUTOHELPER_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8100
    debug: bool = False

    # Database
    db_path: Path = Field(default_factory=lambda: data_dir() / "autohelper.db")

    # Filesystem roots (comma-separated paths)
    allowed_roots: list[str] = Field(default_factory=list)

    # Image serving — allowed base directories for the /api/image proxy
    image_allowed_roots: list[str] = Field(default_factory=list)

    # Report thumbnails
    report_thumbnail_max_area: int = Field(default=15000, ge=1000, le=500000)
    report_thumbnail_quality: int = Field(default=80, ge=10, le=100)

    # Exclusion patterns
    excludes: list[str] = Field(
        default_factory=lambda: ["pyc", "__pycache__", ".git", ".idea", "node_modules"]
    )

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
    mail_output_path: Path = Field(
        default_factory=lambda: Path(Path.home() / "OneDrive" / "Emails")
    )
    mail_ingest_path: Path = Field(
        default_factory=lambda: data_dir() / "ingest"
    )

    # Context Layer / External Data Sources
    autoart_frontend_url: str = "http://localhost:5173"
    autoart_api_url: str = "http://localhost:3001"
    autoart_link_key: str = ""  # Persistent link key from AutoArt pairing
    context_providers: list[str] = Field(default=["autoart", "monday"])  # Priority order

    # Artifact Storage Settings
    # Backend selection: "manifest" (default, local JSON) or "sharepoint" (requires credentials)
    metadata_backend: MetadataBackendType = "manifest"

    # SharePoint settings (only used if metadata_backend == "sharepoint")
    sharepoint_site_url: str | None = None
    sharepoint_client_id: str | None = None
    sharepoint_client_secret: str | None = None

    # Garbage Collection Settings
    gc_enabled: bool = True  # Enable/disable GC scheduler
    gc_schedule_hours: int = Field(default=24, ge=1)  # Run every N hours (min: 1)
    gc_retention_days: int = Field(default=7, ge=1)  # Retain files/sessions N days (min: 1)
    gc_rtf_temp_path: str | None = None  # Custom RTF temp path (default: system temp)
    gc_cleanup_orphaned_manifests: bool = False  # Disabled by default (risky)
    gc_cleanup_mail_ingest: bool = True  # Clean up processed mail files

    # Contact Sync Settings
    contact_sync_enabled: bool = False
    contact_sync_csv_path: str = ""
    contact_sync_interval_minutes: int = Field(default=30, ge=5)
    contact_sync_work_hours_start: int = Field(default=8, ge=0, le=23)
    contact_sync_work_hours_end: int = Field(default=18, ge=0, le=23)
    contact_sync_timezone: str = "America/Los_Angeles"
    contact_sync_dry_run: bool = False
    contact_sync_batch_size: int = Field(default=50, ge=1, le=500)
    contact_sync_managed_prefix: str = "BFA-"  # Prefix to identify managed contacts

    # Exchange Connection
    exchange_email: str = ""
    exchange_password: str = ""

    # ClickUp Integration — env vars read without AUTOHELPER_ prefix
    clickup_token: str = Field(default="", validation_alias=AliasChoices("CLICKUP_TOKEN", "AUTOHELPER_CLICKUP_TOKEN", "clickup_token"))
    clickup_client_id: str = Field(default="", validation_alias=AliasChoices("CLICKUP_CLIENT_ID", "AUTOHELPER_CLICKUP_CLIENT_ID", "clickup_client_id"))
    clickup_client_secret: str = Field(default="", validation_alias=AliasChoices("CLICKUP_CLIENT_SECRET", "AUTOHELPER_CLICKUP_CLIENT_SECRET", "clickup_client_secret"))
    clickup_redirect_uri: str = Field(default="http://localhost:8100/api/clickup/callback", validation_alias=AliasChoices("CLICKUP_REDIRECT_URI", "AUTOHELPER_CLICKUP_REDIRECT_URI", "clickup_redirect_uri"))
    clickup_workspace_id: str = Field(default="", validation_alias=AliasChoices("CLICKUP_WORKSPACE_ID", "AUTOHELPER_CLICKUP_WORKSPACE_ID", "clickup_workspace_id"))
    clickup_space_id: str = Field(default="", validation_alias=AliasChoices("CLICKUP_SPACE_ID", "AUTOHELPER_CLICKUP_SPACE_ID", "clickup_space_id"))
    clickup_list_id: str = Field(default="", validation_alias=AliasChoices("CLICKUP_LIST_ID", "AUTOHELPER_CLICKUP_LIST_ID", "clickup_list_id"))
    clickup_folder_id: str = Field(default="", validation_alias=AliasChoices("CLICKUP_FOLDER_ID", "AUTOHELPER_CLICKUP_FOLDER_ID", "clickup_folder_id"))
    clickup_artist_list_id: str = Field(default="", validation_alias=AliasChoices("CLICKUP_ARTIST_LIST_ID", "AUTOHELPER_CLICKUP_ARTIST_LIST_ID", "clickup_artist_list_id"))
    clickup_sync_enabled: bool = False
    clickup_sync_interval_hours: int = Field(default=6, ge=1, le=168)

    # Google OAuth
    google_client_id: str = Field(default="", validation_alias=AliasChoices("GOOGLE_CLIENT_ID", "AUTOHELPER_GOOGLE_CLIENT_ID", "google_client_id"))
    google_client_secret: str = Field(default="", validation_alias=AliasChoices("GOOGLE_CLIENT_SECRET", "AUTOHELPER_GOOGLE_CLIENT_SECRET", "google_client_secret"))
    google_redirect_uri: str = Field(default="http://localhost:8100/api/google/callback", validation_alias=AliasChoices("GOOGLE_REDIRECT_URI", "AUTOHELPER_GOOGLE_REDIRECT_URI", "google_redirect_uri"))

    # Monday OAuth
    monday_client_id: str = Field(default="", validation_alias=AliasChoices("MONDAY_CLIENT_ID", "AUTOHELPER_MONDAY_CLIENT_ID", "monday_client_id"))
    monday_client_secret: str = Field(default="", validation_alias=AliasChoices("MONDAY_CLIENT_SECRET", "AUTOHELPER_MONDAY_CLIENT_SECRET", "monday_client_secret"))
    monday_redirect_uri: str = Field(default="http://localhost:8100/api/monday/callback", validation_alias=AliasChoices("MONDAY_REDIRECT_URI", "AUTOHELPER_MONDAY_REDIRECT_URI", "monday_redirect_uri"))

    # Felt Integration
    felt_api_token: str = Field(default="", validation_alias=AliasChoices("FELT_API_TOKEN", "AUTOHELPER_FELT_API_TOKEN", "felt_api_token"))
    felt_default_basemap: str = "light"
    felt_default_radius_km: float = Field(default=2.0, ge=0.1, le=50.0)

    # Mapbox Static Maps
    mapbox_access_token: str = Field(default="", validation_alias=AliasChoices("MAPBOX_ACCESS_TOKEN", "AUTOHELPER_MAPBOX_ACCESS_TOKEN", "mapbox_access_token"))
    mapbox_username: str = "nmoignard"
    mapbox_style_id: str = "cmmnvxbv6003701rn60ip2btn"

    # Export
    export_output_dir: str = ""

    # Artist Records
    artist_storage_root: str = ""
    artist_ground_truth_csv: str = ""
    artist_scan_enabled: bool = False
    artist_scan_on_change: bool = True

    @model_validator(mode="after")
    def load_from_config_store(self) -> "Settings":
        """
        Load persisted values from config.json.

        ConfigStore is the source of truth for values that persist across restarts,
        like autoart_link_key and user-editable settings. Only applies to fields
        that were NOT explicitly provided (e.g. via constructor kwargs in tests).
        """
        try:
            from autohelper.config.store import ConfigStore

            cfg = ConfigStore().load()
            explicitly_set = self.model_fields_set

            # Link key and clickup token are only stored in config.json (not env vars)
            if "autoart_link_key" not in explicitly_set:
                if "autoart_link_key" in cfg and cfg["autoart_link_key"]:
                    object.__setattr__(self, "autoart_link_key", cfg["autoart_link_key"])
            if "clickup_token" not in explicitly_set:
                if "clickup_token" in cfg and cfg["clickup_token"]:
                    object.__setattr__(self, "clickup_token", cfg["clickup_token"])

            # User-editable settings — manifest is the single source of truth
            for key in CONFIG_KEYS:
                if key in cfg and key not in explicitly_set:
                    object.__setattr__(self, key, cfg[key])
        except Exception:
            # Don't fail startup if config.json is missing or malformed
            pass

        return self

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
