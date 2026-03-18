"""High-level operations for creating interactive Felt context maps."""

from typing import Any

from autohelper.config import get_settings
from autohelper.shared.logging import get_logger
from autohelper.shared.geo import geocode, query_overpass_pois

from .client import FeltClient
from autohelper.modules.documents.context_map.types import (
    ContextArtwork,
    ContextLayerType,
    ContextMapRequest,
    ContextMapResult,
)

logger = get_logger(__name__)

# FSL v2.3.1 styles — two layers per category:
#   "dot" layer: numbered badge (white number on colored halo)
#   "text" layer: name label floating beside (invisible dot, colored text on white halo)
LAYER_STYLES: dict[str, dict[str, Any]] = {
    # ── Context Artworks ──
    "context_art": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["label"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 14, "fontWeight": 700,
            "color": "#FFFFFF", "haloColor": "#6A0DAD", "haloWidth": 2,
            "placement": "auto", "offset": [0, -14],
        },
        "paint": {"color": "#6A0DAD", "size": 10, "opacity": 1.0, "strokeColor": "#FFFFFF", "strokeWidth": 2},
    },
    "context_art_labels": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["name"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 11, "fontWeight": 500,
            "color": "#4A0080", "haloColor": "#FFFFFF", "haloWidth": 1.5,
            "anchor": "left", "offset": [16, 0],
        },
        "paint": {"color": "#6A0DAD", "size": 1, "opacity": 0, "strokeWidth": 0},
    },
    # ── Parks ──
    "parks": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["label"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 12, "fontWeight": 700,
            "color": "#FFFFFF", "haloColor": "#2D6A4F", "haloWidth": 2,
            "placement": "auto", "offset": [0, -12],
        },
        "paint": {"color": "#2D6A4F", "size": 8, "opacity": 0.9, "strokeColor": "#FFFFFF", "strokeWidth": 1},
    },
    "parks_labels": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["name"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 10, "fontWeight": 500,
            "color": "#1B4332", "haloColor": "#FFFFFF", "haloWidth": 1.5,
            "anchor": "left", "offset": [12, 0],
        },
        "paint": {"color": "#2D6A4F", "size": 1, "opacity": 0, "strokeWidth": 0},
    },
    # ── Schools ──
    "schools": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["label"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 12, "fontWeight": 700,
            "color": "#FFFFFF", "haloColor": "#E9C46A", "haloWidth": 2,
            "placement": "auto", "offset": [0, -12],
        },
        "paint": {"color": "#E9C46A", "size": 8, "opacity": 0.9, "strokeColor": "#FFFFFF", "strokeWidth": 1},
    },
    "schools_labels": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["name"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 10, "fontWeight": 500,
            "color": "#7F5D00", "haloColor": "#FFFFFF", "haloWidth": 1.5,
            "anchor": "left", "offset": [12, 0],
        },
        "paint": {"color": "#E9C46A", "size": 1, "opacity": 0, "strokeWidth": 0},
    },
    # ── Community Centres ──
    "community_centres": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["label"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 12, "fontWeight": 700,
            "color": "#FFFFFF", "haloColor": "#264653", "haloWidth": 2,
            "placement": "auto", "offset": [0, -12],
        },
        "paint": {"color": "#264653", "size": 8, "opacity": 0.9, "strokeColor": "#FFFFFF", "strokeWidth": 1},
    },
    "community_centres_labels": {
        "type": "simple",
        "version": "2.3.1",
        "config": {"labelAttribute": ["name"]},
        "label": {
            "minZoom": 0, "maxZoom": 23,
            "fontSize": 10, "fontWeight": 500,
            "color": "#264653", "haloColor": "#FFFFFF", "haloWidth": 1.5,
            "anchor": "left", "offset": [12, 0],
        },
        "paint": {"color": "#264653", "size": 1, "opacity": 0, "strokeWidth": 0},
    },
}


def _get_client() -> FeltClient:
    settings = get_settings()
    token = settings.felt_api_token
    if not token:
        raise ValueError("FELT_API_TOKEN is not configured")
    return FeltClient(token)


async def create_context_map(request: ContextMapRequest) -> ContextMapResult:
    """Create a Felt context map for a project site.

    1. Geocode site address
    2. Geocode and upload numbered context artworks
    3. Query Overpass for nearby POIs (parks, schools, community centres)
    4. Upload POI layers
    5. Add site pin
    6. Return map URL + metadata
    """
    client = _get_client()
    radius_m = request.radius_km * 1000

    # 1. Geocode site
    lat, lon = await geocode(request.site_address)
    logger.info(
        "Creating context map for '%s' at (%.6f, %.6f), radius %.1fkm",
        request.project_slug, lat, lon, request.radius_km,
    )

    # 2. Create Felt map
    map_resp = await client.create_map(
        title=f"Context Map — {request.project_slug}",
        lat=lat,
        lon=lon,
        public_access="private",
    )
    map_id = map_resp["id"]
    map_url = map_resp.get("url", f"https://felt.com/map/{map_id}")

    layer_ids: dict[str, str] = {}

    # 3. Geocode and upload context artworks as a styled data layer.
    if request.context_artworks and ContextLayerType.CONTEXT_ART in request.layers:
        art_features = []
        for artwork in request.context_artworks:
            try:
                a_lat, a_lon = await geocode(artwork.address)
                caption = f"{artwork.artist}, {artwork.title}"
                if artwork.year:
                    caption += f" ({artwork.year})"
                art_features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [a_lon, a_lat]},
                    "properties": {
                        "label": str(artwork.number),
                        "name": caption,
                    },
                })
                logger.info("  #%d %s → (%.4f, %.4f)", artwork.number, artwork.title, a_lat, a_lon)
            except ValueError:
                logger.warning("  #%d Could not geocode: %s", artwork.number, artwork.address)

        if art_features:
            fc = {"type": "FeatureCollection", "features": art_features}
            result = await client.upload_geojson(map_id, fc, "Context Artworks")
            lid = result.get("layer_id", "")
            layer_ids["context_art"] = lid
            if lid:
                try:
                    await client.update_layer_style(map_id, lid, LAYER_STYLES["context_art"])
                except Exception:
                    logger.warning("Could not apply style to context_art layer")
            label_result = await client.upload_geojson(map_id, fc, "Context Artworks Labels")
            label_lid = label_result.get("layer_id", "")
            if label_lid:
                try:
                    await client.update_layer_style(map_id, label_lid, LAYER_STYLES["context_art_labels"])
                except Exception:
                    logger.warning("Could not apply style to context_art_labels layer")

    # 4. Query and upload Overpass POI layers with numbered badges.
    overpass_categories = {
        ContextLayerType.PARKS, ContextLayerType.SCHOOLS, ContextLayerType.COMMUNITY_CENTRES,
    }
    poi_categories = [c for c in request.layers if c in overpass_categories]
    if poi_categories:
        poi_data = await query_overpass_pois(lat, lon, radius_m, poi_categories)
        for cat, fc in poi_data.items():
            fc["features"] = [f for f in fc["features"] if f["properties"].get("name")]
            fc["features"].sort(key=lambda f: f["properties"].get("distance_m", 0))
            fc["features"] = fc["features"][:15]
            if not fc["features"]:
                continue
            for i, feature in enumerate(fc["features"], 1):
                feature["properties"]["label"] = str(i)
            layer_name = cat.value.replace("_", " ").title()
            result = await client.upload_geojson(map_id, fc, layer_name)
            lid = result.get("layer_id", "")
            layer_ids[cat.value] = lid
            if lid and cat.value in LAYER_STYLES:
                try:
                    await client.update_layer_style(map_id, lid, LAYER_STYLES[cat.value])
                except Exception:
                    logger.warning("Could not apply style to %s layer", cat.value)
            labels_key = f"{cat.value}_labels"
            if labels_key in LAYER_STYLES:
                label_result = await client.upload_geojson(map_id, fc, f"{layer_name} Labels")
                label_lid = label_result.get("layer_id", "")
                if label_lid:
                    try:
                        await client.update_layer_style(map_id, label_lid, LAYER_STYLES[labels_key])
                    except Exception:
                        logger.warning("Could not apply style to %s layer", labels_key)

    # 5. Add site pin as an element
    site_pin_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": request.project_slug.replace("-", " ").title(),
                    "description": request.site_address,
                },
            }
        ],
    }
    try:
        await client.upsert_elements(map_id, site_pin_fc)
        logger.info("Added site pin for '%s'", request.project_slug)
    except Exception:
        logger.warning("Could not add site pin element")

    # 6. Get final map info
    try:
        map_info = await client.get_map(map_id)
        thumbnail_url = map_info.get("thumbnail_url")
        map_url = map_info.get("url", map_url)
    except Exception:
        thumbnail_url = None

    return ContextMapResult(
        map_id=map_id,
        map_url=map_url,
        thumbnail_url=thumbnail_url,
        layers=layer_ids,
        project_slug=request.project_slug,
    )


async def validate_connection() -> dict[str, Any]:
    """Validate the Felt API token."""
    client = _get_client()
    return await client.validate_token()
