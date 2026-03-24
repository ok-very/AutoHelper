"""Integration test: ingestion → DB → render pipeline → HTML verification.

Validates that the full pipeline produces HTML that _postprocess_docx can work with.
Does NOT require Word COM — tests up to the HTML stage boundary.
"""

import re
import pytest

from autohelper.config import get_settings
from autohelper.db import init_db
from autohelper.db.migrate import run_migrations


@pytest.fixture(scope="module")
def db_state():
    """Ensure DB is initialized and return repo + entries."""
    settings = get_settings()
    db = init_db(settings.db_path)
    run_migrations(db)
    from autohelper.modules.bfa_todo.pipeline.repo import BfaProjectRepo
    repo = BfaProjectRepo()
    entries = repo.get_all(include_archived=False)
    return repo, entries


class TestDbCounts:
    def test_project_count(self, db_state):
        _, entries = db_state
        projects = [e for e in entries if e["type"] == "project"]
        assert len(projects) >= 147, f"Expected >=147 projects, got {len(projects)}"

    def test_preamble_exists(self, db_state):
        _, entries = db_state
        preambles = [e for e in entries if e["type"] == "preamble"]
        assert len(preambles) >= 1

    def test_preamble_lists_exists(self, db_state):
        _, entries = db_state
        pl = [e for e in entries if e["type"] == "preamble-lists"]
        assert len(pl) >= 1

    def test_curated_count(self, db_state):
        _, entries = db_state
        curated = sum(1 for e in entries if e.get("fields", {}).get("ownership") == "curated")
        # At least the 147 ingested projects + 2 preambles
        assert curated >= 140, f"Expected >=140 curated, got {curated}"


class TestDbRichHtml:
    """Verify rich HTML is stored in section html fields."""

    def _find_project(self, entries, substring):
        for e in entries:
            if e["type"] == "project" and substring in e.get("header", {}).get("text", ""):
                return e
        pytest.fail(f"Project containing '{substring}' not found")

    def test_bold_in_contacts(self, db_state):
        _, entries = db_state
        p = self._find_project(entries, "East 2nd")
        html = p["sections"].get("contacts", {}).get("html", "")
        assert "<b>Contact:</b>" in html

    def test_italic_in_artwork(self, db_state):
        _, entries = db_state
        # Georgetown 2 has italic "Rise Together"
        p = self._find_project(entries, "Georgetown 2")
        html = p["sections"].get("artwork_title", {}).get("html", "")
        assert "<i>" in html, f"No italic in artwork_title html: {html[:200]}"

    def test_strikethrough_in_section(self, db_state):
        _, entries = db_state
        # East 2nd has strikethrough in next_steps
        p = self._find_project(entries, "East 2nd")
        all_html = " ".join(
            s.get("html", "") for s in p.get("sections", {}).values()
        )
        assert "<s>" in all_html, "No strikethrough found in East 2nd sections"

    def test_preamble_has_render_ready_html(self, db_state):
        _, entries = db_state
        preamble = next(e for e in entries if e["type"] == "preamble")
        html = preamble["sections"].get("content", {}).get("html", "")
        assert '<p style="' in html, "Preamble html should have inline styles"
        assert "font-size:" in html

    def test_preamble_text_html_parity(self, db_state):
        """Text line count must equal HTML block element count — drift causes paragraph swallowing."""
        from bs4 import BeautifulSoup
        _, entries = db_state
        for ptype in ("preamble", "preamble-lists"):
            entry = next((e for e in entries if e["type"] == ptype), None)
            if entry is None:
                continue
            for sec_name, sec in entry.get("sections", {}).items():
                text_lines = sec.get("text", "").split("\n")
                html_raw = sec.get("html", "")
                soup = BeautifulSoup(html_raw, "lxml")
                # Count top-level block elements: <p> and <table>
                blocks = soup.find_all(["p", "table"])
                assert len(text_lines) == len(blocks), (
                    f"{ptype}/{sec_name}: {len(text_lines)} text lines vs "
                    f"{len(blocks)} block elements — out of sync"
                )

    def test_preamble_parity_after_date_refresh(self, db_state):
        """Text/HTML parity must survive refresh_dynamic_preamble_dates."""
        from autohelper.modules.bfa_todo.service import refresh_dynamic_preamble_dates
        from bs4 import BeautifulSoup

        refresh_dynamic_preamble_dates()

        # Re-read from DB (not cached fixture)
        repo, _ = db_state
        entries = repo.get_all(include_archived=False)
        for ptype in ("preamble", "preamble-lists"):
            entry = next((e for e in entries if e["type"] == ptype), None)
            if entry is None:
                continue
            for sec_name, sec in entry.get("sections", {}).items():
                text_lines = sec.get("text", "").split("\n")
                soup = BeautifulSoup(sec.get("html", ""), "lxml")
                blocks = soup.find_all(["p", "table"])
                assert len(text_lines) == len(blocks), (
                    f"{ptype}/{sec_name} after refresh: {len(text_lines)} text lines "
                    f"vs {len(blocks)} block elements"
                )

    def test_preamble_has_no_format_prefixes(self, db_state):
        """Preamble html should NOT contain old format prefixes like b11|."""
        _, entries = db_state
        preamble = next(e for e in entries if e["type"] == "preamble")
        html = preamble["sections"].get("content", {}).get("html", "")
        assert "b11|" not in html
        assert "B8|" not in html
        assert "p8|" not in html


class TestProjectTextHtmlParity:
    """Same parity invariant for project sections."""

    def test_project_sections_parity(self, db_state):
        """Docx-ingested project sections must have text/html parity.

        Only checks sections from our ingestion (source=gdocs, ownership=curated).
        ClickUp-sourced sections may have text without HTML — that's expected.
        """
        from bs4 import BeautifulSoup
        _, entries = db_state
        failures = []
        for e in entries:
            if e["type"] != "project":
                continue
            if e.get("source") != "gdocs":
                continue
            header = e.get("header", {}).get("text", "")[:50]
            for sec_name, sec in e.get("sections", {}).items():
                text = sec.get("text", "")
                html_raw = sec.get("html", "")
                if not text and not html_raw:
                    continue
                # Skip sections not from docx ingestion (ClickUp-only or empty)
                if not html_raw.strip() or "<p>" not in html_raw:
                    continue
                text_lines = text.split("\n")
                soup = BeautifulSoup(html_raw, "lxml")
                p_tags = soup.find_all("p")
                if len(text_lines) != len(p_tags):
                    failures.append(
                        f"{header}/{sec_name}: {len(text_lines)} text vs {len(p_tags)} <p>"
                    )
        assert not failures, f"Parity failures:\n" + "\n".join(failures[:10])


class TestUpdatePreambleDateRenderer:
    """Test _update_preamble_date in renderer.py preserves parity."""

    def test_parity_not_worsened_by_date_update(self, db_state):
        """_update_preamble_date must not change the text/html line count delta."""
        from autohelper.modules.bfa_todo.pipeline.renderer import _update_preamble_date
        from bs4 import BeautifulSoup
        import copy

        repo, _ = db_state
        projects = repo.get_all(include_archived=False)

        # Snapshot before
        before = {}
        for p in projects:
            if p["type"] != "preamble":
                continue
            for sec_name, sec in p.get("sections", {}).items():
                text_n = len(sec.get("text", "").split("\n"))
                html_n = len(BeautifulSoup(sec.get("html", ""), "lxml").find_all("p"))
                before[(p["uid"], sec_name)] = (text_n, html_n)

        projects_copy = copy.deepcopy(projects)
        _update_preamble_date(projects_copy)

        # Check after — counts must not diverge further
        for p in projects_copy:
            if p["type"] != "preamble":
                continue
            for sec_name, sec in p.get("sections", {}).items():
                text_n = len(sec.get("text", "").split("\n"))
                html_n = len(BeautifulSoup(sec.get("html", ""), "lxml").find_all("p"))
                old = before.get((p["uid"], sec_name), (0, 0))
                assert (text_n, html_n) == old, (
                    f"preamble/{sec_name}: counts changed from {old} to ({text_n}, {html_n})"
                )


class TestPrepareHtmlOnRealOutput:
    """Test _prepare_html_for_word against the actual rendered HTML."""

    @pytest.fixture(scope="class")
    def prepared_real(self, db_state):
        from unittest.mock import patch
        from autohelper.modules.bfa_todo.pipeline import config
        path = config.SITE_DIR / "index_pasteable.html"
        if not path.exists():
            pytest.skip("index_pasteable.html not found")
        html = path.read_text(encoding="utf-8")
        with patch(
            "autohelper.modules.bfa_todo.docx_renderer._get_on_hold_uids",
            return_value=set(),
        ):
            from autohelper.modules.bfa_todo.docx_renderer import _prepare_html_for_word
            cleaned, uid_map = _prepare_html_for_word(html)
        return cleaned, uid_map

    def test_date_present(self, prepared_real):
        """Title date must be present (set by refresh_dynamic_preamble_dates, not _prepare_html_for_word)."""
        import re
        html, _ = prepared_real
        assert re.search(r"To Do List\s+\w+ \d{1,2},?\s*\d{4}", html), (
            "Title date not found in prepared HTML"
        )

    def test_vancouver_checklist_anchor(self, prepared_real):
        from bs4 import BeautifulSoup
        html, _ = prepared_real
        soup = BeautifulSoup(html, "lxml")
        found = False
        for el in soup.find_all(True):
            t = el.get_text()
            if "Vancouver" in t and "Checklist" in t:
                found = True
                break
        assert found, "Vancouver/Checklist anchor missing in real prepared HTML"

    def test_proposals_anchor(self, prepared_real):
        from bs4 import BeautifulSoup
        html, _ = prepared_real
        soup = BeautifulSoup(html, "lxml")
        found = any(
            p.get_text(strip=True).startswith("Proposals") and "New" in p.get_text()
            for p in soup.find_all("p")
        )
        assert found, "Proposals anchor missing in real prepared HTML"

    def test_first_project_header_anchor(self, prepared_real):
        from bs4 import BeautifulSoup
        html, _ = prepared_real
        soup = BeautifulSoup(html, "lxml")
        found = any(
            el.get_text(strip=True).startswith("(")
            and ":" in el.get_text()
            and any(k in el.get_text() for k in ("Artwork", "Total", "Install"))
            for el in soup.find_all(["h3", "p"])
        )
        assert found, "First project header missing in real prepared HTML"

    def test_uid_map_count(self, prepared_real):
        _, uid_map = prepared_real
        assert len(uid_map) >= 147, f"Expected >=147 UIDs, got {len(uid_map)}"

    def test_no_class_attributes_in_body(self, prepared_real):
        from bs4 import BeautifulSoup
        html, _ = prepared_real
        soup = BeautifulSoup(html, "lxml")
        for el in soup.body.find_all(True):
            assert not el.get("class"), (
                f"<{el.name}> still has class={el.get('class')}"
            )


class TestRenderedHtml:
    """Verify the rendered index_pasteable.html has correct structure."""

    @pytest.fixture(scope="class")
    def pasteable_html(self, db_state):
        from autohelper.modules.bfa_todo.pipeline import config
        path = config.SITE_DIR / "index_pasteable.html"
        if not path.exists():
            pytest.skip("index_pasteable.html not found — run render_pipeline first")
        return path.read_text(encoding="utf-8")

    def test_preamble_section_exists(self, pasteable_html):
        assert 'class="bfa-preamble"' in pasteable_html

    def test_preamble_lists_section_exists(self, pasteable_html):
        assert 'class="bfa-preamble-lists"' in pasteable_html

    def test_project_sections_exist(self, pasteable_html):
        count = pasteable_html.count('class="bfa-project"')
        assert count >= 147, f"Expected >=147 project sections, got {count}"

    def test_preamble_has_inline_styles(self, pasteable_html):
        """Preamble should have <p style= (render-ready), not format prefixes."""
        # Find preamble section
        m = re.search(
            r'class="bfa-preamble".*?</section>',
            pasteable_html,
            re.DOTALL,
        )
        assert m, "Preamble section not found"
        preamble = m.group()
        assert '<p style="' in preamble
        assert "b11|" not in preamble

    def test_project_has_rich_tags(self, pasteable_html):
        """Project sections should contain bold formatting (as spans or <b> tags)."""
        # runs_to_inline_html renders bold as <span style="font-weight:700">
        # so count both representations
        bold_count = 0
        for m in re.finditer(
            r'class="bfa-project".*?</section>',
            pasteable_html,
            re.DOTALL,
        ):
            section = m.group()
            bold_count += section.count("font-weight:700")
            bold_count += section.count("<b>")
        assert bold_count >= 500, f"Expected >=500 bold elements in projects, got {bold_count}"

    def test_vancouver_checklist_text_exists(self, pasteable_html):
        """The Vancouver/Checklist anchor text must exist for _postprocess_docx."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(pasteable_html, "lxml")
        found = False
        for el in soup.find_all(True):
            text = el.get_text()
            if "Vancouver" in text and "Checklist" in text:
                found = True
                break
        assert found, "Vancouver/Checklist anchor not found in rendered HTML"

    def test_proposals_text_exists(self, pasteable_html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(pasteable_html, "lxml")
        found = False
        for el in soup.find_all(True):
            t = el.get_text(strip=True)
            if t.startswith("Proposals") and "New" in t:
                found = True
                break
        assert found, "Proposals anchor not found in rendered HTML"

    def test_first_project_header_exists(self, pasteable_html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(pasteable_html, "lxml")
        found = False
        for el in soup.find_all(["h3", "p"]):
            t = el.get_text(strip=True)
            if t.startswith("(") and ":" in t and any(
                k in t for k in ("Artwork", "Total", "Install")
            ):
                found = True
                break
        assert found, "First project header anchor not found in rendered HTML"
