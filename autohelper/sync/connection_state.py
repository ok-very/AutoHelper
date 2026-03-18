"""
Connection State Manager - Thread-safe singleton tracking AutoHelper's connection state.

Three states:
- UNPAIRED: No link key exists
- PAIRED_CONNECTED: Link key valid, backend reachable
- PAIRED_DISCONNECTED: Link key exists but backend unreachable
"""

import enum
import threading
from typing import Callable

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)


class ConnectionState(enum.Enum):
    UNPAIRED = "unpaired"
    PAIRED_CONNECTED = "paired_connected"
    PAIRED_DISCONNECTED = "paired_disconnected"


class ConnectionStateManager:
    """Thread-safe singleton managing the connection state between AutoHelper and the backend."""

    _instance: "ConnectionStateManager | None" = None
    _lock = threading.Lock()

    # Instance attributes (initialized in __new__)
    _state: ConnectionState
    _listeners: list[Callable[[ConnectionState], None]]
    _state_lock: threading.Lock

    def __new__(cls) -> "ConnectionStateManager":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._state = ConnectionState.UNPAIRED
                instance._listeners = []
                instance._state_lock = threading.Lock()
                cls._instance = instance
            return cls._instance

    @property
    def state(self) -> ConnectionState:
        return self._state

    def set_state(self, new_state: ConnectionState) -> None:
        with self._state_lock:
            if self._state != new_state:
                logger.debug("Connection state transition: %s -> %s", self._state.value, new_state.value)
                self._state = new_state
                for listener in self._listeners:
                    try:
                        listener(new_state)
                    except Exception:
                        logger.exception("Connection state listener raised exception")

    def add_listener(self, callback: Callable[[ConnectionState], None]) -> None:
        """Register a callback to be notified of state changes."""
        with self._state_lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[ConnectionState], None]) -> None:
        """Unregister a state change callback."""
        with self._state_lock:
            self._listeners = [listener for listener in self._listeners if listener is not callback]

    @classmethod
    def reset(cls) -> None:
        """Reset singleton for testing."""
        with cls._lock:
            cls._instance = None
