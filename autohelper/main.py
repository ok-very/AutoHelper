"""
AutoHelper entrypoint - runs uvicorn server.
"""

import uvicorn

from autohelper.app import build_app
from autohelper.config import get_settings


import sys
import threading
import os
from autohelper.app import build_app
from autohelper.config import get_settings

def main() -> None:
    """Run the AutoHelper server."""
    settings = get_settings()
    
    print(f"Starting AutoHelper on http://{settings.host}:{settings.port}")
    print(f"Docs: http://{settings.host}:{settings.port}/docs")
    
    config = uvicorn.Config(
        build_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        loop="asyncio"
    )
    server = uvicorn.Server(config)

    if "--popup" in sys.argv:
        print("Starting Config Popup...")
        from autohelper.gui.popup import launch_config_popup
        launch_config_popup()
        sys.exit(0)

    if "--tray" in sys.argv:
        print("Starting in System Tray mode...")
        try:
            from autohelper.gui.icon import AutoHelperIcon
            
            # Run server in background thread
            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()
            
            # Run icon in main thread (blocking)
            def on_quit():
                print("Stopping server...")
                server.should_exit = True
                server_thread.join(timeout=5)
                print("Server stopped. Exiting.")
                sys.exit(0)
                
            icon = AutoHelperIcon(stop_callback=on_quit)
            icon.run()
            
        except Exception as e:
            print(f"Failed to start GUI mode: {e}")
            print("Falling back to console mode.")
            server.run()
    else:
        # Standard console mode
        server.run()

if __name__ == "__main__":
    main()
