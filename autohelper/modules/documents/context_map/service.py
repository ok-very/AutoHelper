"""Static context map production — data pipeline and rendering."""

import math
from typing import Any

from autohelper.config import get_settings
from autohelper.shared.logging import get_logger
from autohelper.shared.paths import data_dir
from autohelper.shared.geo import geocode, query_overpass_pois

from .renderer import MapData, MarkerItem, render_context_map
from .types import ContextArtwork, ContextLayerType, ContextMapRequest, StaticMapResult

# Max POIs per category — keeps legend from overflowing
MAX_POIS_PER_CATEGORY = 5

logger = get_logger(__name__)

# ── Domus St. Georges context artworks (from PUBLIC ART CONTEXT) ────────────
_DOMUS_CONTEXT = [
    ContextArtwork(number=1, artist="Nathan Lee", title="Mee Creek", year=2020,
                   address="151 East 15th Street, North Vancouver, BC"),
    ContextArtwork(number=2, artist="Ray Natraoro & Victor Harry", title="The Chief", year=2012,
                   address="141 West 14th Street, North Vancouver, BC"),
    ContextArtwork(number=3, artist="Justin Langlois", title="Where Else Would You Rather Be?", year=2021,
                   address="143 East 17th Street, North Vancouver, BC"),
    ContextArtwork(number=4, artist="Robert Cram", title="Hericium Continuum", year=2026,
                   address="1712 Lonsdale Avenue, North Vancouver, BC"),  # at Lennox
    ContextArtwork(number=5, artist="Jacqueline Metz & Nancy Chew", title="Tête-à-Tête", year=2026,
                   address="132 West 15th Street, North Vancouver, BC"),  # Polygon Elle
    ContextArtwork(number=6, artist="Sinàm̓kin Jody Broomfield", title="Strength and Remembrance", year=2019,
                   address="147 East 14th Street, North Vancouver, BC"),  # Stella Jo Dean Plaza
]

# ── Polygon Lennox context artworks (from PUBLIC ART CONTEXT) ───────────────
_LENNOX_CONTEXT = [
    ContextArtwork(number=1, artist="Nathan Lee", title="Mee Creek", year=2020,
                   address="151 East 15th Street, North Vancouver, BC"),
    ContextArtwork(number=2, artist="Marianne Nicolson", title="My People Will Rise Up Like a Thunderbird from the Sea", year=2008,
                   address="141 West 14th Street, North Vancouver, BC"),
    ContextArtwork(number=3, artist="Myfanwy MacLeod", title="The Lady", year=2017,
                   address="100 East 13th Street, North Vancouver, BC"),
    ContextArtwork(number=4, artist="Wade Baker", title="Ancient Sun", year=2007,
                   address="141 West 14th Street, North Vancouver, BC"),
    ContextArtwork(number=5, artist="Maskull Lasserre", title="Sky Harbour", year=2020,
                   address="100 West 13th Street, North Vancouver, BC"),
    ContextArtwork(number=6, artist="Justin Langlois", title="Where Else Would You Rather Be?", year=2021,
                   address="143 East 17th Street, North Vancouver, BC"),
    ContextArtwork(number=7, artist="Katherine Kerr", title="Continuum", year=2007,
                   address="141 West 14th Street, North Vancouver, BC"),
    ContextArtwork(number=8, artist="Jody Broomfield", title="Strength and Remembrance", year=2019,
                   address="100 East 14th Street, North Vancouver, BC"),
    ContextArtwork(number=9, artist="SWON", title="Veil", year=2001,
                    address="2300 Lonsdale Avenue, North Vancouver, BC"),
]

# ── Test sites with their context artworks ──────────────────────────────────
TEST_SITES: list[dict[str, Any]] = [
    {
        "slug": "domus-st-georges",
        "address": "1612 St. Georges Avenue, North Vancouver, BC",
        "municipality": "City of North Vancouver",
        "site_label": "Domus Homes - 1612 St. George's Ave",
        "context_artworks": [a.model_dump() for a in _DOMUS_CONTEXT],
    },
    {
        "slug": "polygon-lennox",
        "address": "1712 Lonsdale Avenue, North Vancouver, BC",
        "municipality": "City of North Vancouver",
        "context_artworks": [a.model_dump() for a in _LENNOX_CONTEXT],
    },
    {
        "slug": "gilmore-place",
        "address": "Gilmore Avenue and Lougheed Highway, Burnaby, BC",
        "municipality": "City of Burnaby",
        "context_artworks": [],
    },
    {
        "slug": "starlight-lougheed-village",
        "address": "9500 Erickson Drive, Burnaby, BC",
        "municipality": "City of Burnaby",
        "context_artworks": [],
    },
]


async def create_static_context_map(request: ContextMapRequest) -> StaticMapResult:
    """Render a static context map image (PNG) with numbered markers and legend.

    Pipeline: geocode → Overpass POIs → Mapbox Static + PIL render.
    """
    radius_m = request.radius_km * 1000

    # 1. Geocode site
    lat, lon = await geocode(request.site_address)
    logger.info(
        "Rendering static map for '%s' at (%.6f, %.6f), radius %.1fkm",
        request.project_slug, lat, lon, request.radius_km,
    )

    markers: list[MarkerItem] = []

    # 2. Geocode context artworks
    if request.context_artworks and ContextLayerType.CONTEXT_ART in request.layers:
        for artwork in request.context_artworks:
            try:
                a_lat, a_lon = await geocode(artwork.address)
                caption = f"{artwork.artist}, {artwork.title}"
                if artwork.year:
                    caption += f" ({artwork.year})"
                markers.append(MarkerItem(
                    lat=a_lat, lon=a_lon, number=artwork.number,
                    name=caption, category="context_art",
                ))
                logger.info("  #%d %s -> (%.4f, %.4f)", artwork.number, artwork.title, a_lat, a_lon)
            except ValueError:
                logger.warning("  #%d Could not geocode: %s", artwork.number, artwork.address)

    # 3. Expand radius to encompass all context artworks
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    max_art_dist = max(
        (_haversine_m(lat, lon, m.lat, m.lon) for m in markers),
        default=0,
    )
    effective_radius = max(radius_m, max_art_dist * 1.15)
    logger.info("Effective radius: %.0fm (base %.0fm, farthest artwork %.0fm)",
                effective_radius, radius_m, max_art_dist)

    # 4. Query Overpass POIs at expanded radius — sequential numbering across all categories
    overpass_categories = {
        ContextLayerType.PARKS, ContextLayerType.SCHOOLS, ContextLayerType.COMMUNITY_CENTRES,
    }
    poi_categories = [c for c in request.layers if c in overpass_categories]
    poi_counter = 1  # global counter so labels don't repeat (A, B, C... across all POI types)
    if poi_categories:
        poi_data = await query_overpass_pois(lat, lon, effective_radius, poi_categories)
        for cat, fc in poi_data.items():
            features = [f for f in fc["features"] if f["properties"].get("name")]
            features.sort(key=lambda f: f["properties"].get("distance_m", 0))
            features = features[:MAX_POIS_PER_CATEGORY]
            for feature in features:
                coords = feature["geometry"]["coordinates"]
                markers.append(MarkerItem(
                    lat=coords[1], lon=coords[0], number=poi_counter,
                    name=feature["properties"]["name"], category=cat.value,
                ))
                poi_counter += 1

    # 5. Render
    output_dir = data_dir() / "maps"
    output_path = output_dir / f"{request.project_slug}-context.png"

    site_label = request.site_label or request.project_slug.replace("-", " ").title()
    map_data = MapData(
        site_lat=lat, site_lon=lon,
        site_label=site_label,
        radius_m=effective_radius,
        markers=markers,
    )

    settings = get_settings()
    if not settings.mapbox_access_token:
        raise ValueError("MAPBOX_ACCESS_TOKEN is not configured")

    await render_context_map(
        map_data, output_path,
        access_token=settings.mapbox_access_token,
        username=settings.mapbox_username,
        style_id=settings.mapbox_style_id,
    )
    logger.info("Static map saved to %s", output_path)

    # Build legend data for the response
    legend: dict[str, list[dict[str, str]]] = {}
    legend["site"] = [{"number": "1", "name": site_label}]
    for item in markers:
        legend.setdefault(item.category, []).append({
            "number": str(item.number), "name": item.name,
        })

    return StaticMapResult(
        output_path=str(output_path),
        project_slug=request.project_slug,
        legend=legend,
    )
