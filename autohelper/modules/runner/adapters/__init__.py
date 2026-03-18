"""
Site adapter registry and exports.

Provides automatic detection and selection of site-specific scrapers.
"""

import threading

from .base import SiteAdapter, SiteMatch


class AdapterRegistry:
    """
    Registry for site adapters with auto-detection.

    Maintains a list of adapters and selects the best match
    based on confidence scoring. Thread-safe for concurrent access.

    Adapters are registered lazily on first detect() call to avoid
    deadlocking Python's import lock with our threading.Lock.
    """

    _adapters: list[SiteAdapter] = []
    _default: SiteAdapter | None = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Lazy-init: import and register adapters on first use."""
        if cls._initialized:
            return

        # Import OUTSIDE the lock — these trigger further imports and
        # must not compete with Python's import machinery.
        from .cargo import CargoAdapter
        from .default import DefaultAdapter
        from .squarespace import SquarespaceAdapter
        from .wordpress import WordPressAdapter

        with cls._lock:
            if cls._initialized:
                return  # double-check after acquiring lock

            default = DefaultAdapter()
            cls._adapters.append(default)
            cls._default = default

            cls._adapters.append(CargoAdapter())
            cls._adapters.append(SquarespaceAdapter())
            cls._adapters.append(WordPressAdapter())

            cls._initialized = True

    @classmethod
    def register(cls, adapter: SiteAdapter, *, is_default: bool = False) -> None:
        """
        Register an adapter.

        Args:
            adapter: The adapter instance to register
            is_default: If True, use as fallback when no match found

        Note:
            Duplicate adapters (by name) are silently ignored.
        """
        with cls._lock:
            existing_names = {a.name for a in cls._adapters}
            if adapter.name in existing_names:
                return

            cls._adapters.append(adapter)
            if is_default:
                cls._default = adapter

    @classmethod
    def detect(cls, url: str, html: str) -> tuple[SiteAdapter, SiteMatch]:
        """
        Find the best matching adapter for URL/HTML.

        Args:
            url: The page URL
            html: Raw HTML content

        Returns:
            Tuple of (adapter, match) with highest confidence
        """
        cls._ensure_initialized()

        matches: list[tuple[SiteAdapter, SiteMatch]] = []

        with cls._lock:
            adapters = list(cls._adapters)
            default = cls._default

        for adapter in adapters:
            match = adapter.detect(url, html)
            if match:
                matches.append((adapter, match))

        if matches:
            return max(matches, key=lambda x: x[1].confidence)

        if default:
            return (default, SiteMatch("default", 0.0, {}))

        raise RuntimeError("No adapters registered and no default adapter set")

    @classmethod
    def clear(cls) -> None:
        """Clear all registered adapters (for testing)."""
        with cls._lock:
            cls._adapters = []
            cls._default = None
            cls._initialized = False


__all__ = ["AdapterRegistry", "SiteAdapter", "SiteMatch"]
