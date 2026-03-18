"""
SSRF-protected HTTP client.

Provides an HTTP client wrapper that validates URLs and redirects for SSRF protection.
"""

import types
from typing import TYPE_CHECKING, cast
from urllib.parse import urljoin

from .validation import is_safe_url

if TYPE_CHECKING:
    import httpx
    from httpx import Response

# Lazy import for optional httpx dependency
_httpx = None


def _get_httpx() -> types.ModuleType:
    """Lazy import httpx."""
    global _httpx
    if _httpx is None:
        try:
            import httpx

            _httpx = httpx
        except ImportError as e:
            raise ImportError(
                "httpx is required for web collection. Install with: pip install httpx"
            ) from e
    return _httpx


class SSRFProtectedClient:
    """HTTP client wrapper that validates URLs for SSRF protection."""

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the SSRF-protected client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def get(self, url: str) -> "httpx.Response":
        """
        Fetch URL with SSRF protection on initial URL and redirects.

        Args:
            url: The URL to fetch

        Returns:
            httpx.Response object

        Raises:
            ValueError: If URL or any redirect is blocked by SSRF protection
        """
        httpx = _get_httpx()

        # Validate initial URL for SSRF protection (defense in depth)
        is_safe, error_msg = await is_safe_url(url)
        if not is_safe:
            raise ValueError(f"Unsafe URL blocked: {error_msg}")

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,  # Handle redirects manually
        ) as client:
            max_redirects = 10
            current_url = url

            for _ in range(max_redirects):
                response = await client.get(current_url)

                # Check if this is a redirect
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect_url = response.headers.get("location")
                    if not redirect_url:
                        raise ValueError("Redirect response missing Location header")

                    # Make absolute URL if relative
                    redirect_url = urljoin(current_url, redirect_url)

                    # Validate redirect URL for SSRF (using async to avoid blocking)
                    is_safe, error_msg = await is_safe_url(redirect_url)
                    if not is_safe:
                        raise ValueError(f"Unsafe redirect blocked: {error_msg}")

                    current_url = redirect_url
                    continue

                # Not a redirect, return response
                return cast("Response", response)

            raise ValueError(f"Too many redirects (max {max_redirects})")
