"""Fetch nearby points of interest for context maps."""

import json
import math
from pathlib import Path
from typing import Any

import httpx

from autohelper.shared.logging import get_logger

from autohelper.modules.documents.context_map.types import ContextLayerType

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# In-memory cache for Overpass results — keyed by (lat, lon, radius, categories)
_overpass_cache: dict[str, dict] = {}

# Resolve data directory relative to project root
_DATA_DIR = Path(__file__).resolve().parents[5] / "data"

# Overpass query tags per category
_OVERPASS_TAGS: dict[ContextLayerType, list[dict[str, str]]] = {
    ContextLayerType.PARKS: [
        {"leisure": "park"},
        {"leisure": "playground"},
    ],
    ContextLayerType.SCHOOLS: [
        {"amenity": "school"},
    ],
    ContextLayerType.COMMUNITY_CENTRES: [
        {"amenity": "community_centre"},
    ],
}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two (lat, lon) points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_public_art_nearby(
    lat: float,
    lon: float,
    radius_m: float,
    geojson_path: Path | None = None,
) -> dict[str, Any]:
    """Load public art features from the NVRC GeoJSON, filtered by distance."""
    path = geojson_path or (_DATA_DIR / "north-vancouver-public-art.geojson")
    if not path.exists():
        logger.warning("Public art GeoJSON not found: %s", path)
        return {"type": "FeatureCollection", "features": []}

    with open(path) as f:
        fc = json.load(f)

    nearby = []
    for feature in fc.get("features", []):
        coords = feature.get("geometry", {}).get("coordinates")
        if not coords or len(coords) < 2:
            continue
        flon, flat = coords[0], coords[1]
        if _haversine_m(lat, lon, flat, flon) <= radius_m:
            nearby.append(feature)

    logger.info("Found %d public art features within %.0fm", len(nearby), radius_m)
    return {"type": "FeatureCollection", "features": nearby}


async def query_overpass_pois(
    lat: float,
    lon: float,
    radius_m: float,
    categories: list[ContextLayerType],
) -> dict[ContextLayerType, dict[str, Any]]:
    """Query Overpass API for nearby POIs in a single request, return GeoJSON per category."""
    # Cache key — round coords to avoid near-miss duplicates
    cache_key = f"{round(lat,4)},{round(lon,4)},{int(radius_m)},{sorted(c.value for c in categories)}"
    if cache_key in _overpass_cache:
        logger.info("Overpass cache hit for %s", cache_key)
        return _overpass_cache[cache_key]

    results: dict[ContextLayerType, dict[str, Any]] = {
        cat: {"type": "FeatureCollection", "features": []} for cat in categories
    }

    # Build a single combined Overpass query for all categories
    # Tag each element type so we can split results afterward
    all_filters = []
    for cat in categories:
        tags = _OVERPASS_TAGS.get(cat)
        if not tags:
            continue
        for tag_set in tags:
            for k, v in tag_set.items():
                all_filters.append(f'node["{k}"="{v}"](around:{radius_m},{lat},{lon});')
                all_filters.append(f'way["{k}"="{v}"](around:{radius_m},{lat},{lon});')
                all_filters.append(f'relation["{k}"="{v}"](around:{radius_m},{lat},{lon});')

    if not all_filters:
        return results

    query = f"[out:json][timeout:25];\n(\n  {'  '.join(all_filters)}\n);\nout center;"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Overpass query failed")
        return results  # don't cache failures

    # Classify each element into its category based on tags
    for el in data.get("elements", []):
        if el["type"] == "node":
            coord_lat, coord_lon = el["lat"], el["lon"]
        elif "center" in el:
            coord_lat, coord_lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue

        tags = el.get("tags", {})
        cat = _classify_element(tags, categories)
        if cat is None:
            continue

        name = tags.get("name", "")
        dist = _haversine_m(lat, lon, coord_lat, coord_lon)
        results[cat]["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [coord_lon, coord_lat]},
            "properties": {
                "name": name,
                "osm_id": el.get("id"),
                "category": cat.value,
                "distance_m": round(dist),
            },
        })

    for cat in categories:
        count = len(results[cat]["features"])
        if count:
            logger.info("Overpass: %d %s features within %.0fm", count, cat.value, radius_m)

    _overpass_cache[cache_key] = results
    return results


def _classify_element(
    tags: dict[str, str],
    categories: list[ContextLayerType],
) -> ContextLayerType | None:
    """Match OSM tags to a category, with name validation to filter mistagged data."""
    name = tags.get("name", "").lower()

    if ContextLayerType.PARKS in categories:
        if tags.get("leisure") in ("park", "playground"):
            return ContextLayerType.PARKS

    if ContextLayerType.SCHOOLS in categories:
        if tags.get("amenity") == "school":
            # OSM has rampant mistagging — apartments, restaurants tagged as schools
            if _name_plausible_for_school(name):
                return ContextLayerType.SCHOOLS
            else:
                logger.debug("Rejected mistagged school: %s", name)

    if ContextLayerType.COMMUNITY_CENTRES in categories:
        if tags.get("amenity") == "community_centre":
            if _name_plausible_for_community_centre(name):
                return ContextLayerType.COMMUNITY_CENTRES
            else:
                logger.debug("Rejected mistagged community centre: %s", name)

    return None


# Keywords that indicate a legitimate school
_SCHOOL_KEYWORDS = {
    "school", "academy", "elementary", "secondary", "high school",
    "college", "university", "learning", "montessori", "preschool",
    "kindergarten", "education", "institute", "lycée", "école",
}

# Keywords that indicate a legitimate community centre
_COMMUNITY_KEYWORDS = {
    "community", "centre", "center", "recreation", "civic",
    "neighbourhood", "neighborhood", "legion", "hall", "library",
    "seniors", "youth", "cultural", "arts centre", "arts center",
}


def _name_plausible_for_school(name: str) -> bool:
    """Check if a name plausibly refers to a school."""
    if not name:
        return False
    return any(kw in name for kw in _SCHOOL_KEYWORDS)


def _name_plausible_for_community_centre(name: str) -> bool:
    """Check if a name plausibly refers to a community centre."""
    if not name:
        return False
    return any(kw in name for kw in _COMMUNITY_KEYWORDS)
