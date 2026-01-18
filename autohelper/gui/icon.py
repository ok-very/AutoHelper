import threading
import sys
import os
from typing import Callable, Optional
from PIL import Image, ImageDraw

import pystray
from pystray import MenuItem as item

# Placeholder for Kivy app launch
from autohelper.gui.popup import launch_config_popup

class AutoHelperIcon:
    """
    System tray icon for AutoHelper.
    """
    def __init__(
        self,
        stop_callback: Callable[[], None],
        config_callback: Optional[Callable[[], None]] = None
    ):
        self.stop_callback = stop_callback
        self.config_callback = config_callback
        self.icon: Optional[pystray.Icon] = None
        self._setup_icon()

    def _create_image(self):
        """Create a smiley face icon."""
        width = 64
        height = 64
        bg_color = (43, 85, 128)  # AutoHelper Blue
        face_color = (255, 204, 0) # Smiley Yellow
        black = (0, 0, 0)

        image = Image.new('RGB', (width, height), bg_color)
        dc = ImageDraw.Draw(image)
        
        # Draw face circle
        padding = 8
        dc.ellipse([padding, padding, width-padding, height-padding], fill=face_color)
        
        # Draw eyes
        eye_radius = 4
        eye_y = 24
        eye_x_offset = 16
        
        # Left eye
        dc.ellipse(
            [32-eye_x_offset-eye_radius, eye_y-eye_radius, 
             32-eye_x_offset+eye_radius, eye_y+eye_radius], 
            fill=black
        )
        # Right eye
        dc.ellipse(
            [32+eye_x_offset-eye_radius, eye_y-eye_radius, 
             32+eye_x_offset+eye_radius, eye_y+eye_radius], 
            fill=black
        )
        
        # Draw smile (arc)
        # Bounding box for the arc
        smile_bbox = [20, 24, 44, 48]
        dc.arc(smile_bbox, start=0, end=180, fill=black, width=3)
        
        return image

    def _setup_icon(self):
        """Configure the pystray icon."""
        image = self._create_image()
        menu = (
            item('AutoHelper Service', lambda: None, enabled=False),
            item('Status: Running', lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item('Configure...', self.on_configure),
            pystray.Menu.SEPARATOR,
            item('Exit', self.on_exit)
        )
        
        self.icon = pystray.Icon(
            "AutoHelper", 
            image, 
            "AutoHelper Service", 
            menu
        )

    def on_configure(self, icon, item):
        """Launch the configuration popup.

        Prefer using an injected non-blocking callback over directly
        starting a Qt event loop from the pystray callback.
        """
        # If the icon has been configured with a dedicated configuration
        # callback, use that instead of directly invoking the Qt popup.
        if self.config_callback:
            self.config_callback()
            return

        # Fallback for backward compatibility. This may start a Qt event loop
        # and should be avoided when an external event loop (e.g. Qt) is
        # already running; callers are encouraged to provide `config_callback`.
        try:
            launch_config_popup()
        except RuntimeError as exc:
            # Avoid crashing the tray callback if launching the popup
            # from this context is unsafe.
            print(f"Configuration popup could not be launched from tray callback: {exc}")

    def on_exit(self, icon, item):
        """Stop the application."""
        print("Stopping AutoHelper...")
        icon.stop()
        if self.stop_callback:
            self.stop_callback()

    def run(self):
        """Run the icon (blocking)."""
        if self.icon:
            self.icon.run()

    def run_detached(self):
        """Run the icon in a separate thread (if needed, but usually pystray runs in main)."""
        if self.icon:
            self.icon.run_detached()
