"""Unit tests for docx_run_extractor — verifies run-level formatting extraction."""

import re
import pytest
from autohelper.modules.bfa_todo.docx_run_extractor import (
    extract_project_paragraph_html,
    extract_preamble_paragraph_html,
)


class TestExtractProjectParagraphHtml:
    """Project paragraphs → semantic HTML (no inline style on <p>)."""

    def test_bold_label(self, pm_doc):
        """Para 142: 'Contact: Duncan Wade...' → <b>Contact:</b>"""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[142])
        assert "<b>Contact:</b>" in html
        assert "Duncan Wade" in html
        assert html.startswith("<p>")
        assert html.endswith("</p>")
        # No style attribute on project <p>
        assert 'style=' not in html

    def test_italic(self, pm_doc):
        """Para 150: 'Artwork Title: TBC' — TBC is italic."""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[150])
        assert "<b>Artwork Title:</b>" in html
        assert "<i>TBC</i>" in html

    def test_strikethrough(self, pm_doc):
        """Para 157: entire line is struck through."""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[157])
        assert "<s>" in html
        assert "Kick off" in html

    def test_bold_status_line(self, pm_doc):
        """Para 152: 'Project Status: ...' — entire line bold."""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[152])
        assert "<b>" in html
        assert "Project Status" in html

    def test_plain_text_returned(self, pm_doc):
        """Plain text field matches paragraph .text."""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[142])
        assert "Contact" in text
        assert "Duncan Wade" in text

    def test_empty_paragraph(self, pm_doc):
        """Para 151 is empty → empty <p>."""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[151])
        assert text.strip() == ""
        assert html in ("<p></p>", "<p>&nbsp;</p>")

    def test_multiple_bold_labels_on_one_line(self, pm_doc):
        """Para 144: 'Architect: ... Landscape: ...' — multiple bold labels."""
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[144])
        assert html.count("<b>") >= 2
        assert "Architect" in html
        assert "Landscape" in html

    def test_html_entities_escaped(self, pm_doc):
        """Text content should have HTML entities escaped."""
        # Use para 141 header which has $ signs and parens (benign but
        # we check that < and > would be escaped)
        text, html = extract_project_paragraph_html(pm_doc.paragraphs[141])
        # No raw unescaped < or > in text content (only in tags)
        inner = re.sub(r"<[^>]+>", "", html)  # strip tags
        assert "<" not in inner
        assert ">" not in inner


class TestExtractPreambleParagraphHtml:
    """Preamble paragraphs → render-ready HTML with inline styles."""

    def test_title_bold(self, pm_doc):
        """Para 0: 'Ballard Fine Art - To Do List ...' — bold, 11pt."""
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[0])
        assert "font-weight:700" in html
        assert "font-size:11pt" in html
        assert "Ballard Fine Art" in html

    def test_highlight_yellow(self, pm_doc):
        """Para 7: Contact line with yellow highlight."""
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[7])
        assert "background-color:#ffff00" in html.lower() or "background-color:#FFFF00" in html
        assert "Contact" in text

    def test_bullet_paragraph(self, pm_doc):
        """Para 8: bullet list item with ● and margin."""
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[8])
        assert "&#x25cf;" in html or "●" in html
        assert "margin-left:18pt" in html
        assert "text-indent:-12pt" in html

    def test_8pt_font_size(self, pm_doc):
        """Para 6: 'Vancouver: (Checklist...)' — 8pt city policy heading."""
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[6])
        assert "font-size:8pt" in html
        assert "Vancouver" in text

    def test_color_run(self, pm_doc):
        """Para 1: has red-colored text '3rd Mon. of month'."""
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[1])
        assert 'color:#FF0000' in html or 'color:#ff0000' in html

    def test_hyperlink(self, pm_doc):
        """Para 1 or 2: has hyperlink to vancouver.ca."""
        # Para 1 has a hyperlink
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[1])
        text2, html2 = extract_preamble_paragraph_html(pm_doc.paragraphs[2])
        combined = html + html2
        assert '<a href=' in combined
        assert "vancouver.ca" in combined

    def test_has_style_attribute(self, pm_doc):
        """All preamble paragraphs should have style= on <p>."""
        text, html = extract_preamble_paragraph_html(pm_doc.paragraphs[3])
        assert '<p style="' in html


class TestAggregateFormattingCounts:
    """Verify total formatting counts across the full docx."""

    def test_total_bold_runs(self, pm_doc):
        """Docx has 1244 bold runs — extracted HTML should have ~1200+ <b> tags."""
        bold_count = 0
        for p in pm_doc.paragraphs:
            _, html = extract_project_paragraph_html(p)
            bold_count += html.count("<b>")
        # Allow some tolerance (nested tags, empty runs filtered)
        assert bold_count >= 1100, f"Expected >=1100 bold tags, got {bold_count}"

    def test_total_italic_runs(self, pm_doc):
        italic_count = 0
        for p in pm_doc.paragraphs:
            _, html = extract_project_paragraph_html(p)
            italic_count += html.count("<i>")
        assert italic_count >= 60, f"Expected >=60 italic tags, got {italic_count}"

    def test_total_strike_runs(self, pm_doc):
        strike_count = 0
        for p in pm_doc.paragraphs:
            _, html = extract_project_paragraph_html(p)
            strike_count += html.count("<s>")
        assert strike_count >= 80, f"Expected >=80 strike tags, got {strike_count}"

    def test_total_hyperlinks(self, pm_doc):
        link_count = 0
        for p in pm_doc.paragraphs:
            _, html = extract_project_paragraph_html(p)
            link_count += html.count("<a href=")
        assert link_count >= 15, f"Expected >=15 hyperlinks, got {link_count}"

    def test_total_highlights(self, pm_doc):
        hl_count = 0
        for p in pm_doc.paragraphs:
            _, html = extract_project_paragraph_html(p)
            hl_count += html.count("background-color:")
        assert hl_count >= 200, f"Expected >=200 highlights, got {hl_count}"
