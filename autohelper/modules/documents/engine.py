"""DocumentEngine — Jinja2 environment setup and render pipeline."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi.responses import HTMLResponse

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _rats_filter(rank: int) -> str:
    """Convert a 0-4 rank to rat emojis."""
    if not rank or rank <= 0:
        return ""
    return "\U0001f400" * min(rank, 4)


def _format_bytes(b: int | None) -> str:
    """Human-friendly file size."""
    if b is None:
        return "\u2014"
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.0f} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def _format_inches(val: float | None) -> str:
    if val is None:
        return "\u2014"
    return f'{val:.1f}"'


class DocumentEngine:
    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["rats"] = _rats_filter
        self.env.filters["format_bytes"] = _format_bytes
        self.env.filters["format_inches"] = _format_inches

    def render(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_to_response(self, template_name: str, context: dict) -> HTMLResponse:
        html = self.render(template_name, context)
        return HTMLResponse(content=html)


# Module-level singleton
_engine: DocumentEngine | None = None


def get_engine() -> DocumentEngine:
    global _engine
    if _engine is None:
        _engine = DocumentEngine()
    return _engine
