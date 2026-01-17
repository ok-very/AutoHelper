"""
AutoHelper entrypoint - runs uvicorn server.
"""

import uvicorn

from autohelper.app import build_app
from autohelper.config import get_settings


def main() -> None:
    """Run the AutoHelper server."""
    settings = get_settings()
    app = build_app(settings)
    
    print(f"Starting AutoHelper on http://{settings.host}:{settings.port}")
    print(f"Docs: http://{settings.host}:{settings.port}/docs")
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
