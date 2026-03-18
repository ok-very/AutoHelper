import re
import uuid
import ftfy
from . import config


def fix_encoding(text):
    if not text:
        return ""
    return ftfy.fix_text(text)


def normalize_text(text):
    if not text:
        return ""
    text = fix_encoding(text)
    return re.sub(r"\s+", " ", text).strip()


def stable_uid(fingerprint):
    return str(uuid.uuid5(config.UUID_NAMESPACE, fingerprint.lower().strip()))


def make_slug(client, project_name, city=""):
    base = f"{client}-{project_name}"
    if city and city != "TBC":
        base += f"-{city}"
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return f"bfa-{slug[:60]}"


def make_fingerprint(client, project_name, city=""):
    parts = [
        normalize_text(client).lower(),
        normalize_text(project_name).lower(),
        normalize_text(city).lower() if city else "",
    ]
    return "|".join(parts)


def extract_money(text, label):
    label_pattern = label
    if label.lower() in ("art", "artwork"):
        label_pattern = r"(?:Art(?:work)?)"
    pattern = re.compile(
        rf"{label_pattern}\s*[:\-\s=]\s*"
        rf"(\$?\s*[0-9][0-9,]*(?:\.\d{{1,2}})?(?:\s*[KkMm])?|TBC)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        val = match.group(1).strip()
        val = re.sub(r",+$", "", val)        # trailing commas
        val = re.sub(r"^\$\s+", "$", val)    # leading space after $
        if not val.startswith("$"):
            val = "$" + val
        return val
    return "$TBC"


def normalize_date(date_str):
    if not date_str:
        return "TBC", "TBC"
    date_str = normalize_text(date_str)
    if not date_str or date_str.lower() in ("tbc", "tbd", "____"):
        return "TBC", "TBC"
    try:
        from dateutil import parser as dateparser
        d = dateparser.parse(date_str, dayfirst=True)
        if d:
            return d.strftime("%d %b %Y").lstrip("0"), d.strftime("%Y-%m-%d")
    except Exception:
        pass
    return date_str, "TBC"


def canonicalize_phase(text):
    norm = normalize_text(text).lower()
    if not norm:
        return "TBC"
    if norm in config.PHASE_CANON:
        return config.PHASE_CANON[norm]
    priority_keywords = [
        ("closeout", "Closeout"),
        ("complete", "Closeout"),
        ("install", "Install"),
        ("fabrication", "Fabrication"),
        ("approval", "Approvals"),
        ("detailed design", "Design development"),
        ("design development", "Design development"),
        ("concept", "Design development"),
        (" dd", "Design development"),
        ("dd;", "Design development"),
        ("dd ", "Design development"),
        ("contract", "Contracting"),
        ("artist selected", "Artist selected"),
        ("direct commission", "Contracting"),
        ("artist selection", "EOI/Shortlist"),
        ("selection process", "EOI/Shortlist"),
        ("shortlist", "EOI/Shortlist"),
        ("eoi", "EOI/Shortlist"),
        (" sp ", "EOI/Shortlist"),
        ("sp process", "EOI/Shortlist"),
        ("scoping", "Intake/Scoping"),
        ("intake", "Intake/Scoping"),
    ]
    for keyword, phase in priority_keywords:
        if keyword in norm:
            return phase
    return "TBC"


def normalize_html_whitespace(html_str):
    if not html_str:
        return html_str
    parts = re.split(r"(<[^>]+>)", html_str)
    for i, part in enumerate(parts):
        if not part.startswith("<"):
            parts[i] = re.sub(r"[ \t]{2,}", " ", part)
    return "".join(parts)


def html_to_text(html_str):
    from lxml import html as lxml_html
    try:
        doc = lxml_html.fromstring(html_str)
        return normalize_text(doc.text_content())
    except Exception:
        return normalize_text(re.sub(r"<[^>]+>", " ", html_str))


def migrate_phase(old_phase):
    if not old_phase or old_phase == "TBC":
        return "TBC"
    if old_phase in config.VALID_PHASES:
        return old_phase
    return config.PHASE_MIGRATION.get(old_phase, old_phase)


def parse_excel_name(name):
    if not name:
        return ("TBC", "TBC", "")
    name = fix_encoding(name.strip())
    parts = re.split(r"\s*[\-\u2013\u2014]\s+|\s+[\-\u2013\u2014]\s*", name)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 3:
        return (parts[0], parts[1], " - ".join(parts[2:]))
    elif len(parts) == 2:
        return (parts[0], parts[1], "")
    else:
        return (parts[0] if parts else "TBC", "TBC", "")


def fuzzy_match_score(a, b):
    import difflib
    if not a or not b:
        return 0.0
    a_norm = normalize_text(a).lower()
    b_norm = normalize_text(b).lower()
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
