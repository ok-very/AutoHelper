"""Unit tests for _prepare_html_for_word — verifies HTML pre-processing for Word COM.

Uses minimal synthetic HTML to test anchor detection, date update, and CSS stripping
without depending on a full render pipeline run.
"""

import re
import pytest
from unittest.mock import patch


# Minimal HTML mimicking the structure that render_site produces with the new
# docx-ingested preamble format (inline styles on <p>, <b> tags, no <span>
# wrappers for the title).
_PREAMBLE_HTML = '''
<p style="margin:0;font-size:11pt;font-family:Calibri,sans-serif;line-height:1.15;color:#000;font-weight:700"><b>Ballard Fine Art - To Do List January 9, 2026</b></p>
<p style="margin:0;font-size:11pt;font-family:Calibri,sans-serif;line-height:1.15;color:#000">PUBLIC ART COMMITTEE MEETINGS</p>
<p style="margin:0;font-size:8pt;font-family:Calibri,sans-serif;line-height:1.15;color:#000"><b>Vancouver</b>: (Checklist + PPAP + DPAP)</p>
<p style="margin:0;font-size:8pt;font-family:Calibri,sans-serif;line-height:1.15;color:#000"><span style="background-color:#ffff00">Contact: Tamara Tosoff</span></p>
'''

_PREAMBLE_LISTS_HTML = '''
<p style="margin:0;font-size:11pt;font-family:Calibri,sans-serif;line-height:1.15;color:#000;font-weight:700"><b>Proposals (New Projects)</b></p>
<p style="margin:0;font-size:11pt;font-family:Calibri,sans-serif;line-height:1.15;color:#000">Create Properties - 7000 Lougheed HWY</p>
'''

_PROJECT_HTML = '''
<h3 style="font-size:11pt;font-weight:700;font-family:Calibri,sans-serif;margin-top:0;margin-bottom:2pt">(EK) Anthem - Seymour (Baden Park) - Install June 2026</h3>
<p><b>Contact:</b> Someone</p>
<p><b>Project Status:</b> Active</p>
'''

_PROJECT2_HTML = '''
<h3 style="font-size:11pt;font-weight:700;font-family:Calibri,sans-serif;margin-top:0;margin-bottom:2pt">(JB/EK) Anthem: East 2nd, North Vancouver (Artwork:$96,500.00) (Total:120,000.00) Install: Spring 2027</h3>
<p><b>Contact:</b> Duncan Wade</p>
'''


def _build_test_html():
    """Build a minimal full HTML document with preamble + projects."""
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Test</title></head>
<body class="doc-content">
<section class="bfa-preamble" data-preamble-uid="uid-preamble" id="p-preamble">
<div data-section="content">
{_PREAMBLE_HTML}
</div>
</section>
<section class="bfa-preamble-lists" data-preamble-uid="uid-lists" id="p-lists">
<div data-section="content">
{_PREAMBLE_LISTS_HTML}
</div>
</section>
<section class="bfa-project" data-project-uid="uid-001" id="p-proj1">
{_PROJECT_HTML}
</section>
<section class="bfa-project" data-project-uid="uid-002" id="p-proj2">
{_PROJECT2_HTML}
</section>
</body></html>'''


@pytest.fixture
def prepared():
    """Run _prepare_html_for_word on test HTML."""
    # Mock _get_on_hold_uids to avoid DB dependency
    with patch(
        "autohelper.modules.bfa_todo.docx_renderer._get_on_hold_uids",
        return_value=set(),
    ):
        from autohelper.modules.bfa_todo.docx_renderer import _prepare_html_for_word
        html, uid_map = _prepare_html_for_word(_build_test_html())
    return html, uid_map


class TestDateUpdate:
    def test_date_passes_through_unchanged(self, prepared):
        """_prepare_html_for_word must NOT touch the date.

        The DB is the date authority (set by refresh_dynamic_preamble_dates).
        The HTML already has the correct date before _prepare_html_for_word runs.
        """
        html, _ = prepared
        # The test HTML has "January 9, 2026" — it should survive unchanged
        assert "To Do List January 9, 2026" in html, (
            f"Date should pass through unchanged, "
            f"but found: {[m.group() for m in re.finditer(r'To Do List[^<]{5,30}', html)]}"
        )


class TestAnchors:
    """_postprocess_docx looks for these text anchors in the Word-converted doc.
    They must survive _prepare_html_for_word."""

    def test_vancouver_checklist_anchor(self, prepared):
        """'Vancouver: (Checklist' must be findable as text."""
        from bs4 import BeautifulSoup
        html, _ = prepared
        soup = BeautifulSoup(html, "lxml")
        found = False
        for el in soup.find_all(True):
            text = el.get_text()
            if "Vancouver" in text and "Checklist" in text:
                found = True
                break
        assert found, "Vancouver/Checklist anchor not found in prepared HTML"

    def test_proposals_anchor(self, prepared):
        """'Proposals (New Projects)' must be findable as text."""
        from bs4 import BeautifulSoup
        html, _ = prepared
        soup = BeautifulSoup(html, "lxml")
        found = False
        for p in soup.find_all("p"):
            if p.get_text(strip=True).startswith("Proposals") and "New" in p.get_text():
                found = True
                break
        assert found, "Proposals anchor not found in prepared HTML"

    def test_first_project_header_anchor(self, prepared):
        """First project header starting with '(' and containing 'Install' must exist."""
        from bs4 import BeautifulSoup
        html, _ = prepared
        soup = BeautifulSoup(html, "lxml")
        found = False
        for el in soup.find_all(["h3", "p"]):
            t = el.get_text(strip=True)
            if t.startswith("(") and ":" in t and "Install" in t:
                found = True
                break
        assert found, "First project header anchor not found in prepared HTML"


class TestUidMap:
    def test_uid_count(self, prepared):
        """uid_map should have one entry per project section."""
        _, uid_map = prepared
        assert len(uid_map) == 2

    def test_uid_values(self, prepared):
        _, uid_map = prepared
        uids = [e["uid"] for e in uid_map]
        assert "uid-001" in uids
        assert "uid-002" in uids

    def test_header_hints(self, prepared):
        _, uid_map = prepared
        headers = [e["header"] for e in uid_map]
        assert any("Seymour" in h for h in headers)
        assert any("East 2nd" in h for h in headers)


class TestCssClassStripping:
    def test_no_class_attributes(self, prepared):
        """CSS classes should be stripped to prevent Word COM style pollution."""
        from bs4 import BeautifulSoup
        html, _ = prepared
        soup = BeautifulSoup(html, "lxml")
        body = soup.body
        for el in body.find_all(True):
            assert not el.get("class"), f"Element <{el.name}> still has class={el.get('class')}"


class TestSectionOrder:
    def test_preamble_before_projects(self, prepared):
        """Preamble content should appear before project content."""
        html, _ = prepared
        preamble_pos = html.find("Ballard Fine Art")
        project_pos = html.find("Anthem - Seymour")
        assert preamble_pos < project_pos, "Preamble should come before projects"

    def test_proposals_between_preamble_and_projects(self, prepared):
        """Proposals section should appear between preamble and projects."""
        html, _ = prepared
        preamble_pos = html.find("Ballard Fine Art")
        proposals_pos = html.find("Proposals (New Projects)")
        project_pos = html.find("Anthem - Seymour")
        assert preamble_pos < proposals_pos < project_pos
