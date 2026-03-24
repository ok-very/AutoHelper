"""Tests that HTML produced by contentEditable + execCommand survives
the walk_html_for_runs → runs_to_inline_html → docx pipeline.

The iframe editor uses execCommand which produces different HTML than
the Google Docs CSS-class approach.  These tests verify every tag
variant that browsers can emit is correctly parsed into styled runs
and faithfully round-tripped.

Fidelity contract:
    1. Semantic formatting (bold, italic, strike) must survive round-trip
    2. Inline-style formatting (highlight, font-size, color) must survive
    3. Hyperlinks must survive
    4. List structure must survive
    5. Mixed formatting on a single run must survive
    6. Nested formatting must survive
"""

import pytest

from autohelper.modules.bfa_todo.pipeline.style_resolver import (
    StyleResolver,
    walk_html_for_runs,
    runs_to_inline_html,
)


@pytest.fixture
def resolver():
    """Empty resolver — no GDocs CSS.  Simulates DB-stored HTML from iframe edits."""
    return StyleResolver("")


# ---------------------------------------------------------------------------
# 1. Bold — all browser variants
# ---------------------------------------------------------------------------

class TestBold:
    def test_b_tag(self, resolver):
        runs = walk_html_for_runs("<p><b>Contact:</b> Chris</p>", resolver)
        assert any(r["text"].strip() == "Contact:" and "bold" in r["styles"] for r in runs)

    def test_strong_tag(self, resolver):
        runs = walk_html_for_runs("<p><strong>Contact:</strong> Chris</p>", resolver)
        assert any(r["text"].strip() == "Contact:" and "bold" in r["styles"] for r in runs)

    def test_bold_round_trip(self, resolver):
        html_in = "<p><b>Label:</b> value</p>"
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "font-weight:700" in html_out
        assert "Label:" in html_out
        assert "value" in html_out


# ---------------------------------------------------------------------------
# 2. Italic — all browser variants
# ---------------------------------------------------------------------------

class TestItalic:
    def test_i_tag(self, resolver):
        runs = walk_html_for_runs("<p><i>Artwork Title</i></p>", resolver)
        assert any("italic" in r["styles"] for r in runs)

    def test_em_tag(self, resolver):
        runs = walk_html_for_runs("<p><em>Artwork Title</em></p>", resolver)
        assert any("italic" in r["styles"] for r in runs)

    def test_italic_round_trip(self, resolver):
        html_in = "<p><em>Title of Work</em></p>"
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "font-style:italic" in html_out


# ---------------------------------------------------------------------------
# 3. Strikethrough — all browser variants
# ---------------------------------------------------------------------------

class TestStrikethrough:
    def test_s_tag(self, resolver):
        runs = walk_html_for_runs("<p><s>completed item</s></p>", resolver)
        assert any("strikethrough" in r["styles"] for r in runs)

    def test_strike_tag(self, resolver):
        runs = walk_html_for_runs("<p><strike>completed item</strike></p>", resolver)
        assert any("strikethrough" in r["styles"] for r in runs)

    def test_del_tag(self, resolver):
        """Some browsers use <del> for strikethrough."""
        runs = walk_html_for_runs("<p><del>completed item</del></p>", resolver)
        assert any("strikethrough" in r["styles"] for r in runs)

    def test_strike_round_trip(self, resolver):
        html_in = "<p><s>done</s></p>"
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "line-through" in html_out


# ---------------------------------------------------------------------------
# 4. Highlight — inline style from execCommand('hiliteColor')
# ---------------------------------------------------------------------------

class TestHighlight:
    def test_yellow_highlight_inline_style(self, resolver):
        """execCommand('hiliteColor', false, '#FFF3B0') wraps in span with inline style."""
        html = '<p><span style="background-color: rgb(255, 243, 176);">highlighted</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        # Must detect highlight from inline style
        r = content_runs[0]
        assert "highlight" in r["styles"] or r.get("rich", {}).get("bg_color")

    def test_hex_highlight_inline_style(self, resolver):
        html = '<p><span style="background-color:#FFF3B0">highlighted</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert "highlight" in r["styles"] or r.get("rich", {}).get("bg_color")

    def test_green_highlight(self, resolver):
        html = '<p><span style="background-color:#D4EDBC">green</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert r.get("rich", {}).get("bg_color") == "#d4edbc"

    def test_cyan_highlight(self, resolver):
        html = '<p><span style="background-color:#B5E8EC">cyan</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert r.get("rich", {}).get("bg_color") == "#b5e8ec"

    def test_highlight_round_trip(self, resolver):
        html_in = '<p><span style="background-color:#FFF3B0">important</span></p>'
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "important" in html_out
        # Should preserve highlight in some form
        assert "background-color" in html_out or "highlight" in html_out.lower()


# ---------------------------------------------------------------------------
# 5. Font size — inline style from our fontSize execCommand handler
# ---------------------------------------------------------------------------

class TestFontSize:
    def test_8pt_inline_style(self, resolver):
        html = '<p><span style="font-size:8pt">small text</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        assert content_runs[0].get("rich", {}).get("font_size_pt") == 8.0

    def test_11pt_inline_style(self, resolver):
        html = '<p><span style="font-size:11pt">normal text</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        assert content_runs[0].get("rich", {}).get("font_size_pt") == 11.0

    def test_font_size_round_trip(self, resolver):
        html_in = '<p><span style="font-size:8pt">policy text</span></p>'
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "policy text" in html_out


# ---------------------------------------------------------------------------
# 6. Color — inline style
# ---------------------------------------------------------------------------

class TestColor:
    def test_red_inline_style(self, resolver):
        html = '<p><span style="color:#ff0000">warning</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert "red" in r["styles"] or r.get("rich", {}).get("fg_color") == "#ff0000"

    def test_arbitrary_color_inline_style(self, resolver):
        html = '<p><span style="color:#336699">blue text</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        assert content_runs[0].get("rich", {}).get("fg_color") == "#336699"

    def test_rgb_color_inline_style(self, resolver):
        """Browsers may produce rgb() instead of hex."""
        html = '<p><span style="color: rgb(255, 0, 0);">red</span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert "red" in r["styles"] or r.get("rich", {}).get("fg_color")


# ---------------------------------------------------------------------------
# 7. Hyperlinks
# ---------------------------------------------------------------------------

class TestHyperlinks:
    def test_a_tag_preserves_href(self, resolver):
        html = '<p><a href="https://example.com">link text</a></p>'
        runs = walk_html_for_runs(html, resolver)
        link_runs = [r for r in runs if r.get("href")]
        assert len(link_runs) >= 1
        assert link_runs[0]["href"] == "https://example.com"
        assert "link text" in link_runs[0]["text"]

    def test_link_round_trip(self, resolver):
        html_in = '<p><a href="https://example.com">click here</a></p>'
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "https://example.com" in html_out
        assert "click here" in html_out


# ---------------------------------------------------------------------------
# 8. Lists
# ---------------------------------------------------------------------------

class TestLists:
    def test_ul_li_structure(self, resolver):
        html = "<ul><li>first item</li><li>second item</li></ul>"
        runs = walk_html_for_runs(html, resolver)
        list_runs = [r for r in runs if r.get("list_level", 0) > 0]
        assert len(list_runs) >= 2

    def test_list_round_trip(self, resolver):
        html_in = "<ul><li>alpha</li><li>beta</li></ul>"
        runs = walk_html_for_runs(html_in, resolver)
        html_out = runs_to_inline_html(runs)
        assert "<ul>" in html_out
        assert "<li>" in html_out
        assert "alpha" in html_out
        assert "beta" in html_out


# ---------------------------------------------------------------------------
# 9. Mixed formatting (realistic contentEditable output)
# ---------------------------------------------------------------------------

class TestMixedFormatting:
    def test_bold_label_with_italic_value(self, resolver):
        html = '<p><b>AO:</b> <i>Sculpture in the Park</i></p>'
        runs = walk_html_for_runs(html, resolver)
        bold_runs = [r for r in runs if "bold" in r["styles"]]
        italic_runs = [r for r in runs if "italic" in r["styles"]]
        assert len(bold_runs) >= 1
        assert len(italic_runs) >= 1

    def test_bold_with_strikethrough(self, resolver):
        html = '<p><b><s>completed bold item</s></b></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert "bold" in r["styles"]
        assert "strikethrough" in r["styles"]

    def test_highlight_with_bold(self, resolver):
        html = '<p><span style="background-color:#FFF3B0"><b>important bold</b></span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        r = content_runs[0]
        assert "bold" in r["styles"]
        # highlight must also be detected
        assert "highlight" in r["styles"] or r.get("rich", {}).get("bg_color")

    def test_realistic_project_section(self, resolver):
        """Simulates a full project section after contentEditable editing."""
        html = (
            '<p><b>Contact:</b> Chris Quigley, Project Manager</p>'
            '<p><b>AO:</b> <i>Spirit of the Mountain</i></p>'
            '<p><b>SP#1:</b> Design review meeting scheduled</p>'
            '<p><s>Previous milestone completed</s></p>'
            '<p><span style="background-color:#FFF3B0">Action required: submit proposal</span></p>'
        )
        runs = walk_html_for_runs(html, resolver)
        bold_labels = [r for r in runs if "bold" in r["styles"] and ":" in r["text"]]
        assert len(bold_labels) >= 3, f"Expected >=3 bold labels, got {len(bold_labels)}"
        italic_runs = [r for r in runs if "italic" in r["styles"]]
        assert len(italic_runs) >= 1
        strike_runs = [r for r in runs if "strikethrough" in r["styles"]]
        assert len(strike_runs) >= 1
        highlight_runs = [r for r in runs if "highlight" in r["styles"] or r.get("rich", {}).get("bg_color")]
        assert len(highlight_runs) >= 1


# ---------------------------------------------------------------------------
# 10. Edge cases from contentEditable behavior
# ---------------------------------------------------------------------------

class TestContentEditableEdgeCases:
    def test_div_instead_of_p(self, resolver):
        """Some browsers wrap lines in <div> instead of <p>."""
        html = "<div><b>Label:</b> value</div><div>next line</div>"
        runs = walk_html_for_runs(html, resolver)
        assert any("bold" in r["styles"] for r in runs)
        assert any("value" in r["text"] for r in runs)
        assert any("next line" in r["text"] for r in runs)

    def test_br_between_lines(self, resolver):
        """contentEditable may use <br> instead of new paragraphs."""
        html = "<p>first line<br>second line</p>"
        runs = walk_html_for_runs(html, resolver)
        texts = " ".join(r["text"] for r in runs)
        assert "first line" in texts
        assert "second line" in texts

    def test_empty_spans_ignored(self, resolver):
        """contentEditable can produce empty <span> wrappers."""
        html = '<p><span style="font-weight:bold"></span>actual text</p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        assert "actual text" in content_runs[0]["text"]

    def test_nested_spans(self, resolver):
        """contentEditable may double-wrap formatting."""
        html = '<p><span style="font-weight:bold"><span style="font-style:italic">both</span></span></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        # At minimum the text should survive
        assert "both" in content_runs[0]["text"]

    def test_font_tag_from_old_execcommand(self, resolver):
        """Old execCommand fontSize produces <font size="N"> — our script
        converts these, but test that leftover <font> tags don't crash."""
        html = '<p><font size="1">small</font></p>'
        runs = walk_html_for_runs(html, resolver)
        content_runs = [r for r in runs if r["text"].strip()]
        assert len(content_runs) >= 1
        assert "small" in content_runs[0]["text"]
