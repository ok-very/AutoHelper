"""Address geocoding via Nominatim (OpenStreetMap)."""

import asyncio
from typing import Any

import httpx

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AutoHelper/0.1 (public-art-context-maps)"

# In-memory cache to avoid repeat lookups within a session
_cache: dict[str, tuple[float, float]] = {}

# Rate limit: 1 request per second
_last_request: float = 0.0


async def geocode(address: str) -> tuple[float, float]:
    """Geocode an address to (lat, lon) via Nominatim.

    Raises ValueError if the address cannot be resolved.
    """
    cache_key = address.strip().lower()
    if cache_key in _cache:
        return _cache[cache_key]

    global _last_request
    now = asyncio.get_event_loop().time()
    wait = max(0.0, 1.0 - (now - _last_request))
    if wait > 0:
        await asyncio.sleep(wait)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            NOMINATIM_URL,
            params={
                "q": address,
                "format": "json",
                "limit": 1,
                "addressdetails": 0,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
        )
        _last_request = asyncio.get_event_loop().time()
        resp.raise_for_status()
        results: list[dict[str, Any]] = resp.json()

    if not results:
        raise ValueError(f"Could not geocode address: {address}")

    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    _cache[cache_key] = (lat, lon)
    logger.info("Geocoded '%s' → (%.6f, %.6f)", address, lat, lon)
    return lat, lon
