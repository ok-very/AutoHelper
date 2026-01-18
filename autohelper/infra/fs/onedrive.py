"""
OneDrive Files On-Demand utilities.

Provides functionality to:
- Detect offline (cloud-only) files
- Free up space by marking files as cloud-only (dehydrating)
- Check OneDrive availability
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

# Windows file attribute for offline/cloud-only files
FILE_ATTRIBUTE_OFFLINE = 0x1000
# OneDrive-specific: Pinned (always keep on device)
FILE_ATTRIBUTE_PINNED = 0x80000
# OneDrive-specific: Unpinned (free up space when needed)
FILE_ATTRIBUTE_UNPINNED = 0x100000


class OneDriveManager:
    """Manager for OneDrive Files On-Demand operations."""
    
    def __init__(self) -> None:
        """Initialize OneDrive manager."""
        self._is_windows = sys.platform == "win32"
        self._kernel32 = None
        
        if self._is_windows:
            try:
                import ctypes
                self._kernel32 = ctypes.windll.kernel32  # type: ignore
            except Exception as e:
                logger.warning(f"Failed to load kernel32: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if OneDrive operations are available (Windows only)."""
        return self._is_windows and self._kernel32 is not None
    
    def is_offline_file(self, path: Path) -> bool:
        """
        Check if a file is offline (cloud-only).
        
        Args:
            path: Path to the file to check
            
        Returns:
            True if the file is offline (content not locally available)
        """
        if not self.is_available:
            return False
            
        try:
            st = path.stat()
            if hasattr(st, 'st_file_attributes'):
                return bool(st.st_file_attributes & FILE_ATTRIBUTE_OFFLINE)
        except Exception as e:
            logger.debug(f"Failed to check offline status for {path}: {e}")
        
        return False
    
    def free_up_space(self, path: Path) -> bool:
        """
        Mark a file as cloud-only (dehydrate) to free up local disk space.
        
        This uses the Windows API to set the unpinned attribute, which tells
        OneDrive it can remove the local copy when needed.
        
        Args:
            path: Path to the file to dehydrate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available or self._kernel32 is None:
            logger.warning("OneDrive operations not available on this platform")
            return False
        
        try:
            import ctypes
            
            # Get current attributes
            path_str = str(path)
            current_attrs = self._kernel32.GetFileAttributesW(path_str)
            
            if current_attrs == 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
                error_code = ctypes.get_last_error()
                logger.error(f"Failed to get file attributes for {path}: error {error_code}")
                return False
            
            # Set unpinned attribute (tells OneDrive to free up space)
            # Remove pinned, add unpinned
            new_attrs = (current_attrs & ~FILE_ATTRIBUTE_PINNED) | FILE_ATTRIBUTE_UNPINNED
            
            if self._kernel32.SetFileAttributesW(path_str, new_attrs):
                logger.info(f"Marked file for space reclamation: {path}")
                return True
            else:
                error_code = ctypes.get_last_error()
                logger.error(f"Failed to set file attributes for {path}: error {error_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to free up space for {path}: {e}")
            return False
    
    def pin_file(self, path: Path) -> bool:
        """
        Mark a file to always keep on device (hydrated).
        
        Args:
            path: Path to the file to pin
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available or self._kernel32 is None:
            logger.warning("OneDrive operations not available on this platform")
            return False
        
        try:
            import ctypes
            
            path_str = str(path)
            current_attrs = self._kernel32.GetFileAttributesW(path_str)
            
            if current_attrs == 0xFFFFFFFF:
                error_code = ctypes.get_last_error()
                logger.error(f"Failed to get file attributes for {path}: error {error_code}")
                return False
            
            # Set pinned attribute, remove unpinned
            new_attrs = (current_attrs & ~FILE_ATTRIBUTE_UNPINNED) | FILE_ATTRIBUTE_PINNED
            
            if self._kernel32.SetFileAttributesW(path_str, new_attrs):
                logger.info(f"Pinned file to device: {path}")
                return True
            else:
                error_code = ctypes.get_last_error()
                logger.error(f"Failed to pin file {path}: error {error_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to pin file {path}: {e}")
            return False


# Singleton instance
onedrive_manager = OneDriveManager()
