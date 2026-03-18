"""
Email template parser and registry.

Parses the 9 batched markdown files from BFA-migration/Email Templates/batched/,
converts markdown → HTML, and provides a merge engine for placeholder substitution.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path to email template markdown files
DEFAULT_TEMPLATES_DIR = Path(r"C:\Users\Neal\dev\BFA-migration\Email Templates\batched")

# HTML wrapper for Calibri/Verdana body
HTML_WRAPPER = """\
<div style="font-family: Calibri, Verdana, sans-serif; font-size: 11pt; line-height: 1.5;">
{body}
</div>"""

# Placeholder normalization: [DEVELOPER] → {{developer}}
PLACEHOLDER_RE = re.compile(r"\[([A-Z][A-Z _/&]+(?:\d+)?)\]")

PLACEHOLDER_MAP: dict[str, str] = {
    "DEVELOPER": "developer",
    "PROJECT NAME": "project_name",
    "NAME": "name",
    "YOUR NAME": "your_name",
    "PROJECT COORDINATOR": "project_coordinator",
    "DATE": "date",
    "TARGET DATE": "target_date",
    "TARGET PAC DATE": "target_pac_date",
    "TARGET SUBMISSION DATE": "target_submission_date",
    "PROPOSED DATE 1": "proposed_date_1",
    "PROPOSED DATE 2": "proposed_date_2",
    "SHAREPOINT LINK": "sharepoint_link",
    "ART OPPORTUNITY ID": "art_opportunity_id",
    "ARTIST NAME": "artist_name",
}


@dataclass
class EmailTemplate:
    """A parsed email template."""

    key: str  # e.g. "01.1", "02.3"
    title: str  # e.g. "Request Project Documents from Developer"
    subject_template: str  # Raw subject with placeholders
    body_markdown: str  # Raw markdown body with placeholders
    body_html: str  # Converted HTML with normalized {{placeholders}}
    source_file: str  # Source markdown filename
    merge_fields: list[str] = field(default_factory=list)  # List of {{field}} names


@dataclass
class MergedEmail:
    """Result of merging a template with context data."""

    subject: str
    html_body: str
    template_key: str


class TemplateRegistry:
    """Registry of email templates loaded from markdown files."""

    _instance: TemplateRegistry | None = None

    def __init__(self) -> None:
        self._templates: dict[str, EmailTemplate] = {}

    @classmethod
    def load(
        cls,
        templates_dir: Path | None = None,
    ) -> TemplateRegistry:
        """Load all templates from the markdown directory (cached singleton)."""
        if cls._instance is not None:
            return cls._instance

        registry = cls()
        source_dir = templates_dir or DEFAULT_TEMPLATES_DIR

        if not source_dir.exists():
            logger.warning("Email templates directory not found: %s", source_dir)
            cls._instance = registry
            return registry

        for md_file in sorted(source_dir.glob("*.md")):
            try:
                templates = _parse_markdown_file(md_file)
                for tmpl in templates:
                    registry._templates[tmpl.key] = tmpl
                logger.debug(
                    "Loaded %d templates from %s", len(templates), md_file.name
                )
            except Exception:
                logger.exception("Failed to parse %s", md_file.name)

        logger.info("Loaded %d email templates total", len(registry._templates))
        cls._instance = registry
        return registry

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def get(self, key: str) -> EmailTemplate | None:
        """Get a template by key (e.g. '01.1', '1.1')."""
        # Try exact match first
        if key in self._templates:
            return self._templates[key]

        # Try zero-padded match (1.1 → 01.1)
        parts = key.split(".")
        if len(parts) == 2:
            padded = f"{int(parts[0]):02d}.{parts[1]}"
            if padded in self._templates:
                return self._templates[padded]

        return None

    def all_keys(self) -> list[str]:
        """Get all template keys."""
        return sorted(self._templates.keys())

    def merge(
        self,
        key: str,
        context: dict[str, str],
    ) -> MergedEmail | None:
        """
        Merge a template with context data.

        Context keys match the normalized placeholder names
        (e.g. 'developer', 'project_name').
        """
        tmpl = self.get(key)
        if tmpl is None:
            return None

        # Merge subject
        subject = tmpl.subject_template
        for field_name, value in context.items():
            subject = subject.replace(f"{{{{{field_name}}}}}", value)

        # Merge HTML body
        html_body = tmpl.body_html
        for field_name, value in context.items():
            html_body = html_body.replace(f"{{{{{field_name}}}}}", value)

        return MergedEmail(
            subject=subject,
            html_body=html_body,
            template_key=key,
        )


# ── Markdown Parsing ──────────────────────────────────────────────────────


def _parse_markdown_file(path: Path) -> list[EmailTemplate]:
    """Parse a batched markdown file into individual templates."""
    content = path.read_text(encoding="utf-8")
    templates: list[EmailTemplate] = []

    # Split by --- separator followed by ## header
    # Each section starts with ## X.Y Title
    sections = re.split(r"\n---\n", content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Look for ## header with template number
        header_match = re.search(
            r"^##\s+(\d+)\.(\d+)\s+(.+?)$", section, re.MULTILINE
        )
        if not header_match:
            continue

        major = int(header_match.group(1))
        minor = header_match.group(2)
        title = header_match.group(3).strip()
        key = f"{major:02d}.{minor}"

        # Extract everything after the header
        body_start = header_match.end()
        body = section[body_start:].strip()

        # Extract subject line if present
        subject = ""
        subject_match = re.search(
            r"\*\*Subject:\*\*\s*(.+?)$", body, re.MULTILINE
        )
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove subject line from body
            body = body[: subject_match.start()] + body[subject_match.end() :]
            body = body.strip()

        # Normalize placeholders in subject and body
        subject = _normalize_placeholders(subject)
        body = _normalize_placeholders(body)

        # Find all merge fields
        merge_fields = sorted(set(re.findall(r"\{\{(\w+)\}\}", subject + body)))

        # Convert body markdown to HTML
        body_html = _md_to_html(body)

        templates.append(
            EmailTemplate(
                key=key,
                title=title,
                subject_template=subject,
                body_markdown=body,
                body_html=body_html,
                source_file=path.name,
                merge_fields=merge_fields,
            )
        )

    return templates


def _normalize_placeholders(text: str) -> str:
    """Convert [DEVELOPER] style placeholders to {{developer}}."""

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1)
        normalized = PLACEHOLDER_MAP.get(raw, raw.lower().replace(" ", "_"))
        return f"{{{{{normalized}}}}}"

    return PLACEHOLDER_RE.sub(replace, text)


def _md_to_html(md: str) -> str:
    """Convert markdown to HTML using the markdown library if available, else basic."""
    try:
        import markdown

        html = markdown.markdown(md, extensions=["nl2br", "sane_lists"])
    except ImportError:
        # Fallback: basic conversion
        html = _basic_md_to_html(md)

    return HTML_WRAPPER.format(body=html)


def _basic_md_to_html(md: str) -> str:
    """Basic markdown to HTML without external dependencies."""
    lines = md.split("\n")
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<br>")
            continue

        if stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{stripped[2:]}</li>")
            continue

        if stripped.startswith("**") and stripped.endswith("**"):
            html_parts.append(f"<p><strong>{stripped[2:-2]}</strong></p>")
            continue

        # Bold inline
        processed = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
        html_parts.append(f"<p>{processed}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)
