"""
Context Service for AutoHelper

Orchestrates fetching and caching project/developer context from 
multiple providers (AutoArt, Monday.com) for use in mail processing
and other modules.
"""

import logging
import threading
from typing import Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ContextProvider(Enum):
    """Available context data providers."""
    AUTOART = "autoart"
    MONDAY = "monday"


@dataclass
class ContextData:
    """Cached context data from all providers."""
    projects: list[dict[str, Any]] = field(default_factory=list)
    developers: list[str] = field(default_factory=list)
    board_names: list[str] = field(default_factory=list)
    last_updated: float = 0.0


class ContextService:
    """
    Orchestrates fetching and caching context data from multiple providers.
    
    Priority order is configurable - by default checks AutoArt first,
    then falls back to Monday.com if needed.
    
    Usage:
        from autohelper.modules.context.service import ContextService
        
        service = ContextService()
        service.refresh()
        
        developers = service.get_developers()
        projects = service.get_projects()
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern for global context access."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Import here to avoid circular imports
        from autohelper.config.settings import get_settings
        
        self.settings = get_settings()
        self._context = ContextData()
        self._monday_client = None
        self._autoart_client = None
        self._refresh_lock = threading.Lock()
        
        # Initialize clients based on settings
        self._init_clients()
    
    def _init_clients(self) -> None:
        """Initialize API clients based on settings."""
        from autohelper.modules.context.monday import MondayClient, MondayClientError
        from autohelper.modules.context.autoart import AutoArtClient
        from autohelper.config.store import ConfigStore

        # Load config from ConfigStore (where GUI saves settings)
        config_store = ConfigStore()
        config = config_store.load()

        # AutoArt client (local server, may not be running)
        # Use session_id from ConfigStore if available, otherwise fall back to settings
        autoart_url = getattr(self.settings, 'autoart_api_url', 'http://localhost:3000')
        autoart_key = getattr(self.settings, 'autoart_api_key', None)
        autoart_session_id = config.get('autoart_session_id') or getattr(self.settings, 'autoart_session_id', '')
        self._autoart_client = AutoArtClient(
            api_url=autoart_url,
            api_key=autoart_key,
            session_id=autoart_session_id
        )

        # Monday client is now accessed via AutoArt proxy (using session_id)
        # Direct Monday client is only initialized if we have a direct token in settings
        # (for backward compatibility or direct API access scenarios)
        monday_token = getattr(self.settings, 'monday_api_token', None)
        if monday_token:
            try:
                self._monday_client = MondayClient(token=monday_token)
                logger.info("Monday client initialized (direct token)")
            except (ValueError, MondayClientError) as e:
                logger.warning(f"Failed to init Monday client: {e}")
                self._monday_client = None
    
    def reinit_clients(self) -> None:
        """Reinitialize clients (call after settings change)."""
        from autohelper.config.settings import get_settings
        self.settings = get_settings()
        self._init_clients()
    
    def refresh(self, force: bool = False) -> None:
        """
        Refresh context data from all available providers.
        
        Uses priority list from settings to determine fetch order.
        Data from higher-priority providers takes precedence.
        """
        import time
        
        with self._refresh_lock:
            # Get provider priority from settings (default: autoart first, then monday)
            providers = getattr(
                self.settings, 
                'context_providers', 
                [ContextProvider.AUTOART.value, ContextProvider.MONDAY.value]
            )
            
            projects: list[dict[str, Any]] = []
            developers: list[str] = []
            board_names: list[str] = []
            
            for provider in providers:
                if provider == ContextProvider.AUTOART.value and self._autoart_client:
                    try:
                        if self._autoart_client.test_connection():
                            logger.info("Fetching context from AutoArt...")
                            aa_projects = self._autoart_client.fetch_projects(force)
                            aa_developers = self._autoart_client.fetch_developers(force)
                            
                            if aa_projects:
                                projects.extend(aa_projects)
                            if aa_developers:
                                developers.extend(aa_developers)
                            
                            logger.info(f"AutoArt: {len(aa_projects)} projects, {len(aa_developers)} developers")
                    except Exception as e:
                        logger.warning(f"AutoArt fetch failed: {e}")
                
                elif provider == ContextProvider.MONDAY.value and self._monday_client:
                    try:
                        if self._monday_client.test_connection():
                            logger.info("Fetching context from Monday.com...")
                            boards = self._monday_client.fetch_boards_summary()
                            
                            for board in boards:
                                board_names.append(board["name"])
                                # Extract developer and project from board name
                                if board.get("developer") and board["developer"] not in developers:
                                    developers.append(board["developer"])
                                if board.get("project"):
                                    projects.append({
                                        "id": board["id"],
                                        "name": f"{board['developer']} - {board['project']}",
                                        "definition": "Board",
                                        "source": "monday"
                                    })
                            
                            logger.info(f"Monday: {len(boards)} boards")
                    except Exception as e:
                        logger.warning(f"Monday fetch failed: {e}")
            
            # Deduplicate developers
            self._context.developers = list(set(developers))
            self._context.projects = projects
            self._context.board_names = board_names
            self._context.last_updated = time.time()
            
            logger.info(
                f"Context refreshed: {len(self._context.developers)} developers, "
                f"{len(self._context.projects)} projects"
            )
    
    def get_developers(self) -> list[str]:
        """Get list of known developer names."""
        return self._context.developers
    
    def get_projects(self) -> list[dict[str, Any]]:
        """Get list of known projects."""
        return self._context.projects
    
    def get_board_names(self) -> list[str]:
        """Get list of Monday board names."""
        return self._context.board_names
    
    def get_known_entities(self) -> dict[str, Any]:
        """
        Get all known entities for mail processing.
        
        Returns dict with:
            - developers: list of developer names
            - projects: list of project dicts
            - board_names: list of Monday board names
        """
        return {
            "developers": self._context.developers,
            "projects": self._context.projects,
            "board_names": self._context.board_names,
        }
    
    def match_project(self, text: str) -> dict[str, Any] | None:
        """
        Find a project that matches the given text.
        
        Searches through known projects, developers, and board names.
        Returns the best match or None.
        """
        text_lower = text.lower()
        
        # First check board names (most specific)
        for board_name in self._context.board_names:
            if text_lower in board_name.lower():
                return {"match_type": "board", "name": board_name}
        
        # Check projects
        for project in self._context.projects:
            project_name = project.get("name", "").lower()
            if text_lower in project_name:
                return {"match_type": "project", **project}
        
        # Check developers (least specific)
        for developer in self._context.developers:
            if text_lower in developer.lower():
                return {"match_type": "developer", "name": developer}
        
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if any context provider is configured and working."""
        if self._monday_client:
            try:
                if self._monday_client.test_connection():
                    return True
            except:
                pass
        
        if self._autoart_client:
            try:
                if self._autoart_client.test_connection():
                    return True
            except:
                pass
        
        return False


# Module-level convenience functions
_context_service: ContextService | None = None


def get_context_service() -> ContextService:
    """Get or create the global ContextService instance."""
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service


def reset_context_service() -> None:
    """Reset the global context service (for testing)."""
    global _context_service
    if _context_service:
        ContextService._instance = None
        _context_service = None
