# Context Map Styling Rules

## Layer Hierarchy (bottom to top)

| Layer | Type | Color | Label | Notes |
|-------|------|-------|-------|-------|
| Parks | Data layer | `#2D6A4F` green | Numbered badge | Overpass `leisure=park,playground` |
| Schools | Data layer | `#E9C46A` amber | Numbered badge | Overpass `amenity=school` |
| Community Centres | Data layer | `#264653` teal | Numbered badge | Overpass `amenity=community_centre` |
| Context Artworks | Data layer | `#6A0DAD` purple | Numbered badge | Artworks from PUBLIC ART CONTEXT section |
| Project Site | Element (pin) | Red pin (default) | Project name | The development site |

## Context Artworks (Data Layer + FSL)

- Added as a **data layer** only — NO elements (elements create red pin overlap)
- **Marker**: Purple (`#6A0DAD`) filled circle, 10px, white 2px stroke
- **Label**: Number only via `labelAttribute: ["label"]` — renders as numbered badge
- Full caption in `name` property (visible on hover in Felt)
- Printed legend maps numbers to full names: `1. Nathan Lee, Mee Creek (2020)`
- Only artworks from the project's PUBLIC ART CONTEXT section

### Marker Style

The `label` property stores the number (`"1"`, `"2"`, etc.). FSL renders these as white-on-purple numbered badges. The `name` property stores the full caption for hover display. A separate printed legend maps numbers to names for the art plan document.

## POI Layers (FSL v2.3)

All POI layers use Felt Style Language v2.3.1 with numbered badges, same as artworks.

### Common Label Properties

```json
{
  "config": {"labelAttribute": ["label"]},
  "label": {
    "minZoom": 0, "maxZoom": 23,
    "fontSize": 12, "fontWeight": 700,
    "color": "#FFFFFF", "haloWidth": 2,
    "placement": "auto", "offset": [0, -12]
  }
}
```

Halo color matches the category paint color. Full name in `name` property (hover).

### Paint Properties

All POI dots: 8px, white 1px stroke, high opacity.

### POI Filtering

- Sorted by haversine distance from site, nearest first
- Capped at **15 per category** to prevent clutter
- Unnamed OSM features are dropped

## Content Rules

### What Goes on the Map

- **Context artworks**: Only works named in the project's PUBLIC ART CONTEXT section. These are existing public artworks physically located near the site.
- **Parks, schools, community centres**: Nearest 15 per category within radius (default 1km) via Overpass API.
- **Project site**: The development location, labeled with project name.

### What Does NOT Go on the Map

- **Precedent artworks**: Reference works from other cities (Markham, Toronto, etc.) listed in the PRECEDENT IMAGES section. These are inspirational, not geographic.
- **Bulk public art data**: The NVRC scrape of 160+ artworks is NOT plotted. Only curated, plan-specific context artworks appear.

## Map Settings

- **Basemap**: `light`
- **Access**: `private`
- **Default radius**: 1.0 km
- **Title format**: `Context Map — {project-slug}`

## Static Map Renderer (Mapbox + PIL)

Print-quality PNG generation via `renderer.py`. Used by `POST /felt/static-context-map`.

### Basemap

- **Provider**: Mapbox Static Images API (`@2x` retina)
- **Style**: `satellite-streets-v12` (satellite + street labels)
- **Dimensions**: 1200×800 CSS px → 2400×1600 actual px
- **Framing**: Explicit center/zoom calculated from walking radius

### Pin Markers

Mapbox `pin-l-{label}+{color}(lon,lat)` overlays:

| Category | Color | Label scheme |
|----------|-------|--------------|
| Site | `#D32F2F` red | `1` (always) |
| Context Artworks | `#6A0DAD` purple | `1`–`9` (numbers) |
| Parks | `#2D6A4F` green | `A`–`Z` (letters) |
| Schools | `#B8860B` amber | `A`–`Z` (letters) |
| Community Centres | `#264653` teal | `A`–`Z` (letters) |

### Walking Radius Circle

Dashed circle drawn with PIL on top of fetched basemap. Centered on site,
radius calculated from `radius_km` setting. Zoom level chosen so circle
fills ~45% of map height (all markers within radius visible).

### Legend Panel

Composited on the right via PIL (750px wide at @2x).

- **Circles**: Anti-aliased via 4× supersampling + LANCZOS downscale
- **Text**: ALL CAPS throughout (labels, names, headers)
- **Wrapping**: Long names word-wrap within available width
- **Sections**: SUBJECT SITE, then CONTEXT ARTWORKS, PARKS, SCHOOLS, COMMUNITY CENTRES
- **Footer**: Walking radius label + dashed line icon

### Fonts

Fallback chain: Arial → DejaVu Sans → PIL default.

## Interactive Export (Felt)

Felt has no API for image export. Current workflow:
1. Open the map URL in Felt
2. File > Export view > PNG or PDF
3. Save to project's OneDrive folder for inclusion in art plan document
