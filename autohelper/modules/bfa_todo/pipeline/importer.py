"""
Pass 1: Tokenize the Google Docs HTML export into discrete project modules.

Preserves original HTML fragments per field for visual fidelity.
Extracts clean text for machine use.
"""

import re
from lxml import html as lxml_html
from lxml import etree
from . import config, utils


def extract_css(raw_html):
    match = re.search(
        r"<style[^>]*>(.*?)</style>", raw_html, re.DOTALL | re.IGNORECASE
    )
    if match:
        return match.group(1)
    return ""


def _serialize(element):
    return etree.tostring(element, method="html", encoding="unicode")


def _text_of(element):
    return utils.normalize_text(element.text_content())


def _is_empty_block(element):
    text = _text_of(element)
    return len(text) == 0


def _detect_header(text):
    if not text:
        return False
    has_team = bool(re.match(r"^\s*\(", text))
    has_install = bool(re.search(r"install", text, re.IGNORECASE))
    has_dash = bool(re.search(r"[\-–—:]", text))
    has_comma = "," in text
    if has_team and has_install:
        return True
    if has_team and has_dash and len(text) > 30:
        return True
    if has_team and has_comma and len(text) > 30:
        return True
    return False


def _detect_section_label(text):
    if not text:
        return None, None
    clean = re.sub(r"^[•·\-\*]\s*", "", text).strip()
    clean_lower = clean.lower().rstrip(":").strip()
    sorted_keys = sorted(config.SECTION_LABELS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if clean_lower == key:
            return config.SECTION_LABELS[key], None
        if clean_lower.startswith(key):
            after = clean_lower[len(key):]
            if after and after[0] in (":", " ", "\t"):
                remainder = clean[len(key):].lstrip(":").strip()
                if remainder:
                    return config.SECTION_LABELS[key], remainder
                return config.SECTION_LABELS[key], None
    return None, None


def _detect_inline_label(element):
    bolds = element.findall(".//b") + element.findall(".//strong") + element.findall(".//span[@class]")
    for b in bolds:
        b_text = utils.normalize_text(b.text_content()).lower().rstrip(":").strip()
        if b_text in config.SECTION_LABELS:
            return config.SECTION_LABELS[b_text]
    return None


def _is_inside(el, ancestor_tag):
    parent = el.getparent()
    while parent is not None:
        if parent.tag == ancestor_tag:
            return True
        parent = parent.getparent()
    return False


def tokenize_body(raw_html):
    doc = lxml_html.fromstring(raw_html)
    body = doc.body if doc.body is not None else doc

    blocks = []
    skip_tags = set()

    for el in body.iter():
        if el.tag in ("table", "hr"):
            blocks.append(el)
            continue

        if el.tag in ("ul", "ol"):
            if not _is_inside(el, "table"):
                blocks.append(el)
                skip_tags.add(id(el))
            continue

        if el.tag == "li":
            continue

        if el.tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6"):
            if _is_inside(el, "table"):
                continue
            if any(id(anc) in skip_tags for anc in el.iterancestors()):
                continue
            blocks.append(el)

    return blocks


def _parse_header_fields(text):
    info = {
        "owner_team": "BFA",
        "client": "TBC",
        "project_name": "TBC",
        "city": "TBC",
        "art_budget": "$TBC",
        "total_budget": "$TBC",
        "bfa_fee": "$TBC",
        "install_date": "TBC",
    }

    install_match = re.search(
        r"Install(?:ation)?\s*[:.\-\s]\s*(.*)$", text, re.IGNORECASE
    )
    if install_match:
        info["install_date"] = utils.normalize_text(install_match.group(1))
        main_part = text[: install_match.start()].strip()
    else:
        main_part = text

    # --- Extract budget values from main_part before stripping ---

    def _extract_budgets(s):
        """Pull budget values from text (parenthesized or bare)."""
        if re.search(r"total", s, re.IGNORECASE):
            val = utils.extract_money(s, "Total")
            if val != "$TBC":
                info["total_budget"] = val
        if re.search(r"art", s, re.IGNORECASE):
            val = utils.extract_money(s, "Art")
            if val != "$TBC":
                info["art_budget"] = val
        if re.search(r"fee", s, re.IGNORECASE):
            val = utils.extract_money(s, "BFA fee")
            if val != "$TBC":
                info["bfa_fee"] = val

    # Step 1: Strip parenthesized budget groups (closed parens)
    # Allow trailing text (dollar amounts, "1.5 million", etc.) after the closing paren
    while True:
        budget_match = re.search(
            r"\s*_*\(([^)]*(?:Art|Artwork|Total|Fee|Budget)[^)]*)\)"
            r"[^(]*$",
            main_part,
            re.IGNORECASE,
        )
        if budget_match:
            _extract_budgets(budget_match.group(1))
            _extract_budgets(main_part[budget_match.end():])
            main_part = main_part[: budget_match.start()].strip()
        else:
            break

    # Step 2: Strip budget parens (closed or unclosed) containing budget keywords + $ or :
    # e.g. "(Artwork: $135,000/Total: $200,580" or "(Total:TBC)" or "(Budget:"
    while True:
        budget_paren = re.search(
            r"\s*_*\(?[^A-Za-z(]*(?:Art|Artwork|Total|Fee|Budget)\s*[:$|/][^)]*\)?\s*$",
            main_part,
            re.IGNORECASE,
        )
        if budget_paren:
            _extract_budgets(main_part[budget_paren.start():])
            main_part = main_part[: budget_paren.start()].strip()
        else:
            break

    # Step 3: Strip bare (unparenthesized) budget text at end of string
    # e.g. "Total $3,887,326.08" or "BFA Project Budget$7,500.00" or ", Total"
    bare_budget = re.search(
        r"(?:^|[\s,|])"
        r"(?:(?:Total|Artwork|Art|BFA)\s*(?:Project\s*)?(?:Budget|Fee)?)"
        r"\s*[:.]?\s*(?:\(?[\s$\d,.]+.*)?$",
        main_part,
        re.IGNORECASE,
    )
    if bare_budget:
        # Only strip if there's actual budget content (not just "Gateway Artwork" as project name)
        matched = main_part[bare_budget.start():].strip()
        # Require either $ or : or ( or end-of-string-after-budget-keyword
        if re.search(r"[\$:(]|(?:Total|Budget|Fee)\s*$", matched, re.IGNORECASE):
            _extract_budgets(matched)
            main_part = main_part[: bare_budget.start()].strip()

    # Step 4: Strip bare dollar amounts at end (e.g. "| $50,000" or "Canada Goose $")
    bare_money = re.search(
        r"[\s|]+\$[\d,.]*[kK]?\s*$",
        main_part,
    )
    if bare_money:
        _extract_budgets(main_part[bare_money.start():])
        main_part = main_part[: bare_money.start()].strip()

    # Clean trailing pipes, underscores, dashes
    main_part = re.sub(r"[\s|_\-–—]+$", "", main_part).strip()

    team_match = re.match(r"^\s*\(([^)]*)\)\s*", main_part)
    if team_match:
        info["owner_team"] = utils.normalize_text(team_match.group(1))
        main_part = main_part[team_match.end():].strip()

    parts = re.split(r"\s*[\-–—]\s+|\s*:\s+", main_part, 1)
    if len(parts) > 1:
        info["client"] = utils.normalize_text(parts[0])
        proj_part = utils.normalize_text(parts[1])
        # Strip budget fragments that survived: require $ or : after keyword
        proj_part = re.sub(
            r"\s*\(?[^)]*(?:(?:Art|Artwork|Total|Fee)\s*[:|\s]\s*\$)[^)]*\)?\s*",
            " ", proj_part, flags=re.IGNORECASE,
        ).strip()
        # Strip bare dollar amounts (e.g. "$50,000" as entire proj_part)
        proj_part = re.sub(r"^\$[\d,.]+[kK]?\s*$", "", proj_part).strip()
        # Strip trailing stray parens, pipes, underscores
        proj_part = re.sub(r"[)|_\s]+$", "", proj_part).strip()
        # Strip trailing province codes (e.g. "Burnaby BC")
        proj_part = re.sub(r"\s+(?:BC|AB|ON|QC)\s*$", "", proj_part).strip()
        # Extract city from parens at end, e.g. "Broadview Village (City of Burnaby"
        city_paren = re.search(r"\((?:City\s+of\s+)?([A-Z][a-zA-Z\s]+?)\s*\)?\s*$", proj_part)
        if city_paren:
            city = utils.normalize_text(city_paren.group(1))
            city = re.sub(r"\s+(?:BC|AB|ON|QC)\s*$", "", city).strip()
            info["city"] = city
            proj_part = proj_part[:city_paren.start()].strip().rstrip(",")
            info["project_name"] = proj_part
        else:
            city_parts = proj_part.rsplit(", ", 1)
            if len(city_parts) > 1 and len(city_parts[1]) < 40:
                info["project_name"] = city_parts[0].strip()
                city = city_parts[1].strip()
                city = re.sub(r"\s+(?:BC|AB|ON|QC)\s*$", "", city).strip()
                info["city"] = city
            else:
                info["project_name"] = proj_part
    else:
        info["client"] = utils.normalize_text(main_part)

    return info


_SECTION_DIVIDER_RE = re.compile(
    r"^\s*(?:projects?\s+)?(?:on\s*hold|completed|inactive|paused)(?:\s+projects?)?\s*[\-\u2013\u2014:]*\s*$",
    re.IGNORECASE,
)


def _detect_section_divider(text):
    """Return a status string for section divider headings, or None."""
    if _SECTION_DIVIDER_RE.match(text.strip()):
        return "on_hold"
    return None


def _collect_project_blocks(blocks):
    projects = []
    preamble_blocks = []
    current = None
    current_blocks = []
    current_status = "active"

    for block in blocks:
        if block.tag == "hr":
            continue

        text = _text_of(block)

        # Detect section dividers like "On Hold" or "Completed Projects"
        if block.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            divider = _detect_section_divider(text)
            if divider:
                # Flush the current project before switching status
                if current is not None:
                    current["body_blocks"] = current_blocks
                    projects.append(current)
                    current = None
                    current_blocks = []
                current_status = divider
                continue

        if block.tag in ("h1", "h2", "h3", "h4", "h5", "h6") and _detect_header(text):
            if current is not None:
                current["body_blocks"] = current_blocks
                projects.append(current)
            elif current_blocks or preamble_blocks:
                all_pre = preamble_blocks + current_blocks
                if any(_text_of(b) for b in all_pre):
                    projects.append(
                        {
                            "type": "preamble",
                            "header_text": "",
                            "header_html": "",
                            "body_blocks": all_pre,
                        }
                    )
                preamble_blocks = []

            current = {
                "type": "project",
                "status": current_status,
                "header_text": text,
                "header_html": _serialize(block),
                "body_blocks": [],
            }
            current_blocks = []
            continue

        if current is None:
            preamble_blocks.append(block)
        else:
            if not _is_empty_block(block):
                current_blocks.append(block)

    if current is not None:
        current["body_blocks"] = current_blocks
        projects.append(current)

    return projects


CONTACT_RELATED_SECTIONS = {
    "architect", "landscape", "owner", "ppap", "dpap", "eoi",
    "sp1", "sp2", "ao", "selection_panel", "nvpaac_rep",
    "checklist",
}


def _classify_sections(body_blocks):
    sections = {}
    current_section = None
    current_html_parts = []
    current_text_parts = []

    def flush():
        nonlocal current_section, current_html_parts, current_text_parts
        if current_section and (current_html_parts or current_text_parts):
            store_as = current_section
            if store_as in CONTACT_RELATED_SECTIONS:
                store_as = "contacts"
            if store_as in sections:
                sections[store_as]["html"] += "\n" + "\n".join(current_html_parts)
                sections[store_as]["text"] += "\n" + "\n".join(current_text_parts)
            else:
                sections[store_as] = {
                    "html": "\n".join(current_html_parts),
                    "text": "\n".join(current_text_parts),
                }
        elif current_html_parts:
            if "unmapped" not in sections:
                sections["unmapped"] = {"html": "", "text": ""}
            sections["unmapped"]["html"] += "\n" + "\n".join(current_html_parts)
            sections["unmapped"]["text"] += "\n" + "\n".join(current_text_parts)
        current_html_parts = []
        current_text_parts = []

    for block in body_blocks:
        text = _text_of(block)
        html = _serialize(block)

        section_label, remainder = _detect_section_label(text)

        if section_label is None:
            inline = _detect_inline_label(block)
            if inline:
                section_label = inline

        if section_label:
            flush()
            current_section = section_label
            if remainder:
                current_text_parts.append(remainder)
                current_html_parts.append(html)
            else:
                current_html_parts.append(html)
                current_text_parts.append(text)
        else:
            current_html_parts.append(html)
            current_text_parts.append(text)

    flush()

    for key in sections:
        sections[key]["html"] = sections[key]["html"].strip()
        sections[key]["text"] = sections[key]["text"].strip()

    return sections


def import_document(filepath=None):
    filepath = filepath or config.INPUT_FILE
    with open(filepath, "rb") as f:
        raw_bytes = f.read()

    raw_html = raw_bytes.decode("utf-8", errors="replace")
    raw_html = utils.fix_encoding(raw_html)

    css = extract_css(raw_html)
    blocks = tokenize_body(raw_html)
    raw_projects = _collect_project_blocks(blocks)

    result = []
    for rp in raw_projects:
        if rp["type"] == "preamble":
            # Split preamble at "Proposals" into overview (single-col)
            # and project lists (two-col)
            split_idx = None
            for bi, b in enumerate(rp["body_blocks"]):
                t = _text_of(b)
                if t.startswith("Proposals"):
                    split_idx = bi
                    break

            chunks = []
            if split_idx is not None:
                chunks.append(("preamble", rp["body_blocks"][:split_idx]))
                chunks.append(("preamble-lists", rp["body_blocks"][split_idx:]))
            else:
                chunks.append(("preamble", rp["body_blocks"]))

            for ptype, pblocks in chunks:
                html_parts = []
                text_parts = []
                for b in pblocks:
                    html_parts.append(_serialize(b))
                    t = _text_of(b)
                    if t:
                        text_parts.append(t)

                if not any(text_parts):
                    continue

                fingerprint = f"{ptype}|{len(result)}"
                result.append(
                    {
                        "type": ptype,
                        "uid": utils.stable_uid(fingerprint),
                        "slug": f"bfa-{ptype}-{len(result)}",
                        "fingerprint": fingerprint,
                        "header": {"text": "", "html": ""},
                        "sections": {
                            "content": {
                                "html": "\n".join(html_parts),
                                "text": "\n".join(text_parts),
                            }
                        },
                        "fields": {},
                    }
                )
            continue

        header_text = rp["header_text"]
        header_html = rp["header_html"]
        fields = _parse_header_fields(header_text)

        fingerprint = utils.make_fingerprint(
            fields["client"], fields["project_name"], fields["city"]
        )
        uid = utils.stable_uid(fingerprint)
        slug = utils.make_slug(
            fields["client"], fields["project_name"], fields["city"]
        )

        sections = _classify_sections(rp["body_blocks"])

        result.append(
            {
                "type": "project",
                "status": rp.get("status", "active"),
                "uid": uid,
                "slug": slug,
                "fingerprint": fingerprint,
                "header": {"text": header_text, "html": header_html},
                "fields": fields,
                "sections": sections,
            }
        )

    return result, css
