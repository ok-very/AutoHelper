"""
Generate placeholder MSIX logo assets using Pillow.

Creates simple branded PNGs for the MSIX package. Replace these with real
artwork before any public release.

Usage:
    python scripts/msix/generate_assets.py [output_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

# Asset specs: (filename, width, height)
ASSETS = [
    ("Square44x44Logo.png", 44, 44),
    ("Square150x150Logo.png", 150, 150),
    ("Wide310x150Logo.png", 310, 150),
    ("StoreLogo.png", 50, 50),
]

BG_COLOR = (63, 92, 110)  # Oxide Blue from DESIGN.md
FG_COLOR = (245, 242, 237)  # Parchment


def generate_asset(path: Path, width: int, height: int) -> None:
    img = Image.new("RGBA", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    label = "AH"
    font_size = min(width, height) // 3

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    draw.text((x, y), label, fill=FG_COLOR, font=font)

    img.save(path)


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Assets")
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, w, h in ASSETS:
        dest = output_dir / filename
        generate_asset(dest, w, h)
        print(f"  {dest} ({w}x{h})")

    print(f"\nGenerated {len(ASSETS)} assets in {output_dir}/")


if __name__ == "__main__":
    main()
