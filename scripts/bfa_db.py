"""BFA To Do database utility — inspect, query, and debug DB state.

Usage:
    python scripts/bfa_db.py recent              # recently modified sections
    python scripts/bfa_db.py section UID NAME     # dump a section's html/text
    python scripts/bfa_db.py project UID           # full project detail
    python scripts/bfa_db.py preambles             # list preamble entries
    python scripts/bfa_db.py stats                 # summary counts
    python scripts/bfa_db.py search QUERY          # search sections by text
    python scripts/bfa_db.py sql "SELECT ..."      # raw SQL (read-only)
"""

import sys
import io
import argparse
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from autohelper.shared.paths import data_dir
from autohelper.db.conn import init_db, get_db

init_db(data_dir() / "autohelper.db")


def cmd_recent(args):
    db = get_db()
    rows = db.execute("""
        SELECT s.project_uid, s.name, s.updated_at,
               length(s.html) as html_len, length(s.text) as text_len,
               substr(replace(s.text, char(10), ' '), 1, 80) as preview
        FROM bfa_sections s
        ORDER BY s.updated_at DESC
        LIMIT ?
    """, (args.limit,)).fetchall()
    if not rows:
        print("No sections found.")
        return
    print(f"{'UID':24s} | {'Section':20s} | {'Updated':20s} | {'HTML':>5s} | {'Text':>5s} | Preview")
    print("-" * 120)
    for r in rows:
        uid = (r[0] or "")[:24]
        sec = (r[1] or "")[:20]
        updated = (r[2] or "")[:20]
        html_len = r[3] or 0
        text_len = r[4] or 0
        preview = (r[5] or "")[:60]
        print(f"{uid:24s} | {sec:20s} | {updated:20s} | {html_len:5d} | {text_len:5d} | {preview}")


def cmd_section(args):
    db = get_db()
    row = db.execute("""
        SELECT s.project_uid, s.name, s.text, s.html, s.updated_at
        FROM bfa_sections s
        WHERE s.project_uid = ? AND s.name = ?
    """, (args.uid, args.name)).fetchone()
    if not row:
        print(f"Not found: {args.uid} / {args.name}")
        return
    print(f"UID:     {row[0]}")
    print(f"Section: {row[1]}")
    print(f"Updated: {row[4]}")
    print(f"\n--- TEXT ({len(row[2] or '')} chars) ---")
    print(row[2] or "(empty)")
    print(f"\n--- HTML ({len(row[3] or '')} chars) ---")
    print(row[3] or "(empty)")


def cmd_project(args):
    db = get_db()
    proj = db.execute("""
        SELECT uid, slug, type, source, fields_json, phase_canonical, header_text
        FROM bfa_projects WHERE uid = ?
    """, (args.uid,)).fetchone()
    if not proj:
        print(f"Not found: {args.uid}")
        return
    print(f"UID:    {proj[0]}")
    print(f"Slug:   {proj[1]}")
    print(f"Type:   {proj[2]}")
    print(f"Source: {proj[3]}")
    fields = json.loads(proj[4]) if proj[4] else {}
    print(f"Client: {fields.get('client', '?')}")
    print(f"Project: {fields.get('project_name', '?')}")
    print(f"Phase:  {proj[5] or '?'}")
    print(f"Header: {(proj[6] or '')[:100]}")
    print(f"Ownership: {fields.get('ownership', 'input')}")

    sections = db.execute("""
        SELECT name, length(text), length(html), updated_at
        FROM bfa_sections WHERE project_uid = ?
        ORDER BY name
    """, (args.uid,)).fetchall()
    if sections:
        print(f"\nSections ({len(sections)}):")
        for s in sections:
            print(f"  {s[0]:20s}  text={s[1] or 0:5d}  html={s[2] or 0:5d}  updated={s[3]}")


def cmd_preambles(args):
    db = get_db()
    rows = db.execute("""
        SELECT uid, slug, type, source FROM bfa_projects
        WHERE type IN ('preamble', 'preamble-lists')
        ORDER BY type, slug
    """).fetchall()
    for r in rows:
        print(f"{r[0]:30s} | {r[2]:16s} | {r[1]} | source={r[3]}")
    sections = db.execute("""
        SELECT s.project_uid, s.name, length(s.html), s.updated_at
        FROM bfa_sections s
        JOIN bfa_projects e ON e.uid = s.project_uid
        WHERE e.type IN ('preamble', 'preamble-lists')
        ORDER BY s.updated_at DESC
    """).fetchall()
    if sections:
        print(f"\nPreamble sections ({len(sections)}):")
        for s in sections:
            print(f"  {s[0][:24]:24s} | {s[1]:20s} | html={s[2] or 0:5d} | {s[3]}")


def cmd_stats(args):
    db = get_db()
    entries = db.execute("SELECT type, count(*) FROM bfa_projects GROUP BY type").fetchall()
    print("Entries:")
    for e in entries:
        print(f"  {e[0]:20s}: {e[1]}")
    total_sections = db.execute("SELECT count(*) FROM bfa_sections").fetchone()[0]
    with_html = db.execute("SELECT count(*) FROM bfa_sections WHERE html IS NOT NULL AND html != ''").fetchone()[0]
    with_text = db.execute("SELECT count(*) FROM bfa_sections WHERE text IS NOT NULL AND text != ''").fetchone()[0]
    print(f"\nSections: {total_sections} total, {with_html} with HTML, {with_text} with text")
    curated = db.execute("""
        SELECT count(*) FROM bfa_projects
        WHERE json_extract(fields_json, '$.ownership') = 'curated'
    """).fetchone()[0]
    print(f"Curated entries: {curated}")


def cmd_search(args):
    db = get_db()
    query = f"%{args.query}%"
    rows = db.execute("""
        SELECT s.project_uid, s.name,
               substr(replace(s.text, char(10), ' '), 1, 100) as preview
        FROM bfa_sections s
        WHERE s.text LIKE ? OR s.html LIKE ?
        LIMIT 20
    """, (query, query)).fetchall()
    if not rows:
        print(f"No matches for '{args.query}'")
        return
    for r in rows:
        print(f"{r[0][:24]:24s} | {r[1]:20s} | {r[2]}")


def cmd_sql(args):
    db = get_db()
    stmt = args.statement.strip()
    if not stmt.upper().startswith("SELECT"):
        print("Only SELECT statements allowed.")
        return
    rows = db.execute(stmt).fetchall()
    for r in rows:
        print(" | ".join(str(c) for c in r))


def main():
    parser = argparse.ArgumentParser(description="BFA To Do database utility")
    sub = parser.add_subparsers(dest="command")

    p_recent = sub.add_parser("recent", help="Recently modified sections")
    p_recent.add_argument("--limit", type=int, default=15)

    p_section = sub.add_parser("section", help="Dump a section's text and HTML")
    p_section.add_argument("uid")
    p_section.add_argument("name")

    p_project = sub.add_parser("project", help="Full project detail")
    p_project.add_argument("uid")

    sub.add_parser("preambles", help="List preamble entries")
    sub.add_parser("stats", help="Summary counts")

    p_search = sub.add_parser("search", help="Search sections by text")
    p_search.add_argument("query")

    p_sql = sub.add_parser("sql", help="Raw SQL (read-only SELECT)")
    p_sql.add_argument("statement")

    args = parser.parse_args()
    commands = {
        "recent": cmd_recent,
        "section": cmd_section,
        "project": cmd_project,
        "preambles": cmd_preambles,
        "stats": cmd_stats,
        "search": cmd_search,
        "sql": cmd_sql,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
