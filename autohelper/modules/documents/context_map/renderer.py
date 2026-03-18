"""Static context map renderer using Mapbox Static Images API + PIL.

Produces a print-quality PNG with:
- Satellite basemap (Mapbox satellite-streets-v12)
- Numbered pin markers per category (colored by type)
- Dashed walking-radius circle
- Legend panel composited on the right via PIL
"""

import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

# ── Category colors (matching LAYER_STYLES) ──────────────────────────────────
COLORS = {
    "site": "#D32F2F",
    "context_art": "#6A0DAD",
    "parks": "#2D6A4F",
    "schools": "#B8860B",
    "community_centres": "#264653",
}

CATEGORY_ORDER = ["context_art", "parks", "schools", "community_centres"]
CATEGORY_LABELS = {
    "context_art": "CONTEXT ARTWORKS",
    "parks": "PARKS",
    "schools": "SCHOOLS",
    "community_centres": "COMMUNITY CENTRES",
}


@dataclass
class MarkerItem:
    """A numbered marker to place on the map and in the legend."""
    lat: float
    lon: float
    number: int
    name: str
    category: str  # key into COLORS


@dataclass
class MapData:
    """All data needed to render a context map."""
    site_lat: float
    site_lon: float
    site_label: str
    radius_m: float
    markers: list[MarkerItem] = field(default_factory=list)


# ── Mapbox helpers ────────────────────────────────────────────────────────────

MAP_CSS_W = 1200
MAP_CSS_H = 800
# Supersampling factor for anti-aliased legend circles
AA_SCALE = 4


def _color_hex(color: str) -> str:
    """Strip '#' from hex color for Mapbox URL."""
    return color.lstrip("#")


def _pin_label(number: int, category: str) -> str:
    """Single-char pin label. Numbers for art (<10), letters for POIs."""
    if category in ("site", "context_art"):
        return str(min(number, 9))
    return chr(ord("a") + (number - 1) % 26)


def _calc_zoom(lat: float, radius_m: float) -> tuple[float, float]:
    """Calculate zoom so radius fills ~45% of map height (circle visible with padding).

    Returns (zoom, radius_actual_px at @2x).
    """
    # 45% of map height — circle edge well inside frame
    target_css_px = MAP_CSS_H * 0.45
    mpp = radius_m / target_css_px
    zoom = math.log2(156543.03 * math.cos(math.radians(lat)) / mpp)
    zoom = round(zoom, 1)
    # Recalculate at snapped zoom
    actual_mpp = 156543.03 * math.cos(math.radians(lat)) / (2 ** zoom)
    radius_px = (radius_m / actual_mpp) * 2  # @2x
    return zoom, radius_px


def _build_mapbox_url(
    data: MapData,
    access_token: str,
    zoom: float,
    username: str = "mapbox",
    style_id: str = "cmmnvxbv6003701rn60ip2btn",
) -> str:
    """Build Mapbox Static Images API URL with pin overlays and explicit center/zoom."""
    overlays: list[str] = []

    # Site pin
    color = _color_hex(COLORS["site"])
    overlays.append(f"pin-l-1+{color}({data.site_lon},{data.site_lat})")

    # Category markers
    for item in data.markers:
        c = _color_hex(COLORS.get(item.category, "333333"))
        label = _pin_label(item.number, item.category)
        overlays.append(f"pin-l-{label}+{c}({item.lon},{item.lat})")

    overlay_str = ",".join(overlays)
    return (
        f"https://api.mapbox.com/styles/v1/{username}/{style_id}/static"
        f"/{overlay_str}/{data.site_lon},{data.site_lat},{zoom},0"
        f"/{MAP_CSS_W}x{MAP_CSS_H}@2x"
        f"?access_token={access_token}"
    )


async def _fetch_map_png(url: str) -> bytes:
    """Fetch the static map PNG from Mapbox."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


# ── PIL compositing ───────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _load_fonts(
    size_bold: int = 22,
    size_regular: int = 20,
    size_header: int = 18,
) -> tuple[Any, Any, Any]:
    """Load fonts with fallback chain."""
    for bold, regular in [
        ("arialbd.ttf", "arial.ttf"),
        ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"),
    ]:
        try:
            return (
                ImageFont.truetype(bold, size_bold),
                ImageFont.truetype(regular, size_regular),
                ImageFont.truetype(bold, size_header),
            )
        except OSError:
            continue
    default = ImageFont.load_default()
    return default, default, default


def _draw_dashed_circle(
    draw: ImageDraw.ImageDraw,
    cx: float, cy: float, radius: float,
    dash_len: int = 20, gap_len: int = 12,
    width: int = 4, fill: str = "#333333",
) -> None:
    """Draw a dashed circle using PIL arcs."""
    circumference = 2 * math.pi * radius
    segment = dash_len + gap_len
    n = max(int(circumference / segment), 1)
    for i in range(n):
        start = (i * 360) / n
        end = start + (dash_len / segment) * (360 / n)
        bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
        draw.arc(bbox, start, end, fill=fill, width=width)


def _draw_aa_circle(
    img: Image.Image,
    cx: int, cy: int, r: int,
    fill_color: tuple[int, int, int],
    label: str,
    font: Any,
) -> None:
    """Draw an anti-aliased circle with centered label using supersampling."""
    s = AA_SCALE
    big_size = r * 2 * s
    big = Image.new("RGBA", (big_size, big_size), (0, 0, 0, 0))
    big_draw = ImageDraw.Draw(big)
    big_draw.ellipse([0, 0, big_size - 1, big_size - 1], fill=(*fill_color, 255))

    # Draw label at scaled size
    try:
        big_font = ImageFont.truetype(font.path, font.size * s)
    except (AttributeError, OSError):
        big_font = font
    bbox = big_draw.textbbox((0, 0), label, font=big_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    big_draw.text(
        (big_size // 2 - tw // 2, big_size // 2 - th // 2 - s),
        label, fill="white", font=big_font,
    )

    # Downsample with LANCZOS for smooth edges
    small = big.resize((r * 2, r * 2), Image.LANCZOS)
    img.paste(small, (cx - r, cy - r), small)


def _wrap_text(text: str, font: Any, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _draw_legend(data: MapData, legend_width: int, map_height: int) -> Image.Image:
    """Create a PIL legend panel with anti-aliased circles."""
    img = Image.new("RGBA", (legend_width, map_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_bold, font_regular, font_header = _load_fonts()

    x_margin = 30
    circle_r = 15
    x_circle = x_margin + circle_r
    x_text = x_circle + circle_r + 14
    max_text_w = legend_width - x_text - 24
    y = 50
    line_height = 38
    section_gap = 26

    # ── Site entry ──
    draw.text((x_margin, y), "SUBJECT SITE", fill="#333333", font=font_header)
    y += 30
    y = _draw_legend_row(img, draw, x_circle, y, circle_r, "1",
                         COLORS["site"], data.site_label.upper(),
                         x_text, max_text_w, font_regular, font_bold, line_height)
    y += section_gap

    # ── Category sections ──
    grouped: dict[str, list[MarkerItem]] = {}
    for item in data.markers:
        grouped.setdefault(item.category, []).append(item)

    for cat_key in CATEGORY_ORDER:
        items = grouped.get(cat_key, [])
        if not items:
            continue

        color = COLORS.get(cat_key, "#333333")
        header = CATEGORY_LABELS.get(cat_key, cat_key.upper())

        draw.text((x_margin, y), header, fill="#333333", font=font_header)
        y += 30

        for item in sorted(items, key=lambda m: m.number):
            label = _pin_label(item.number, item.category).upper()
            y = _draw_legend_row(img, draw, x_circle, y, circle_r, label,
                                 color, item.name.upper(),
                                 x_text, max_text_w, font_regular, font_bold, line_height)

        y += section_gap

    # Radius label at bottom
    radius_label = f"{int(data.radius_m)}M WALKING RADIUS"
    draw.text((x_margin, y), radius_label, fill="#666666", font=font_header)
    y += 28
    # Dashed line icon
    for i in range(6):
        x0 = x_margin + i * 16
        draw.line([(x0, y), (x0 + 10, y)], fill="#333333", width=3)

    return img.convert("RGB")


def _draw_legend_row(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    cx: int, y: int, r: int,
    label: str, color: str, text: str,
    tx: int, max_text_w: int, font: Any, font_bold: Any, line_height: int,
) -> int:
    """Draw one legend row with AA circle + wrapped text. Returns new y."""
    rgb = _hex_to_rgb(color)

    lines = _wrap_text(text, font, max_text_w, draw)
    total_text_h = len(lines) * (line_height - 2)
    row_h = max(total_text_h, r * 2 + 4)

    # AA circle centered vertically
    cy = y + row_h // 2
    _draw_aa_circle(img, cx, cy, r, rgb, label, font_bold)

    # Text lines
    ty = y + 2
    for line in lines:
        draw.text((tx, ty), line, fill="#333333", font=font)
        ty += line_height - 2

    return y + row_h + 4


# ── Main render ───────────────────────────────────────────────────────────────

async def render_context_map(
    data: MapData,
    output_path: Path,
    access_token: str,
    username: str = "mapbox",
    style_id: str = "cmmnvxbv6003701rn60ip2btn",
) -> Path:
    """Render a static context map to PNG.

    Fetches basemap from Mapbox Static Images API, overlays a dashed radius
    circle, composites a legend panel on the right, and saves the final image.

    Returns the output path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Calculate zoom to fit radius with padding
    zoom, radius_px = _calc_zoom(data.site_lat, data.radius_m)

    # 2. Build URL and fetch basemap
    url = _build_mapbox_url(data, access_token, zoom, username, style_id)
    png_bytes = await _fetch_map_png(url)

    # 3. Load map image (@2x = 2400x1600)
    map_img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    # 4. Draw dashed radius circle on map
    overlay = Image.new("RGBA", map_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    center_px = map_img.width / 2, map_img.height / 2
    _draw_dashed_circle(overlay_draw, center_px[0], center_px[1], radius_px,
                        dash_len=20, gap_len=12, width=4, fill="#333333")
    map_img = Image.alpha_composite(map_img, overlay).convert("RGB")

    # 5. Create legend panel — scale to fit content
    legend_width = 750
    legend_img = _draw_legend(data, legend_width, map_img.height)

    # 6. Composite side-by-side
    final_width = map_img.width + legend_width
    final = Image.new("RGB", (final_width, map_img.height), "white")
    final.paste(map_img, (0, 0))
    final.paste(legend_img, (map_img.width, 0))

    # 7. Save
    final.save(str(output_path), "PNG")
    return output_path
