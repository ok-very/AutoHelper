"""Font service - locate and serve font files."""

from pathlib import Path

from autohelper.shared.logging import get_logger

logger = get_logger(__name__)


# Path to bundled fonts (relative to this file)
FONTS_DIR = Path(__file__).parent.parent.parent / "resources" / "fonts"


class FontService:
    """Service for locating and serving font files."""
    
    def get_font_path(self, family: str, style: str = "regular") -> Path | None:
        """
        Get path to a font file.
        
        Args:
            family: Font family name (e.g., 'Carlito')
            style: Font style (regular, bold, italic, bolditalic)
            
        Returns:
            Path to font file or None if not found
        """
        # Normalize inputs
        family = family.lower()
        style = style.lower().replace("-", "").replace("_", "")
        
        # Map style to filename patterns
        style_map = {
            "regular": ["Regular", ""],
            "bold": ["Bold"],
            "italic": ["Italic"],
            "bolditalic": ["BoldItalic", "Bold-Italic"],
        }
        
        patterns = style_map.get(style, [style.title()])
        
        # Look for the font file
        font_dir = FONTS_DIR / family.title()
        
        if not font_dir.exists():
            logger.warning(f"Font family directory not found: {font_dir}")
            return None
        
        for pattern in patterns:
            # Try different naming conventions
            candidates = [
                font_dir / f"{family.title()}-{pattern}.ttf",
                font_dir / f"{family.title()}{pattern}.ttf",
                font_dir / f"{family.title()}-{pattern}.otf",
            ]
            
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        
        logger.warning(f"Font not found: {family}/{style}")
        return None
    
    def list_fonts(self) -> list[dict]:
        """List all available font families and styles."""
        fonts = []
        
        if not FONTS_DIR.exists():
            return fonts
        
        for family_dir in FONTS_DIR.iterdir():
            if family_dir.is_dir():
                styles = []
                for font_file in family_dir.glob("*.ttf"):
                    # Extract style from filename
                    name = font_file.stem
                    if "-" in name:
                        style = name.split("-")[-1].lower()
                    else:
                        style = "regular"
                    styles.append(style)
                
                if styles:
                    fonts.append({
                        "family": family_dir.name,
                        "styles": sorted(set(styles))
                    })
        
        return fonts
