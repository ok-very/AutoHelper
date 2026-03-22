"""Inspect BFA To Do entries — identity binding, phase names, next steps.

Usage: python scripts/bfa_inspect.py [--clickup-only] [--uid UID]
"""

import sys
import io
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from autohelper.shared.paths import data_dir
from autohelper.db.conn import init_db

init_db(data_dir() / "autohelper.db")

from autohelper.modules.bfa_todo.pipeline.repo import BfaProjectRepo


def main():
    parser = argparse.ArgumentParser(description="Inspect BFA To Do entries")
    parser.add_argument("--clickup-only", action="store_true", help="Only show ClickUp-sourced entries")
    parser.add_argument("--uid", help="Show a single entry by UID")
    parser.add_argument("--all-phases", action="store_true", help="Show all entries with their phase")
    args = parser.parse_args()

    repo = BfaProjectRepo()

    if args.uid:
        entry = repo.get(args.uid)
        if not entry:
            print(f"Not found: {args.uid}")
            return
        _print_entry(entry, verbose=True)
        return

    entries = repo.get_all()
    projects = [e for e in entries if e.get("type") == "project"]

    if args.clickup_only:
        projects = [e for e in projects if e.get("source") == "clickup"]

    if args.all_phases:
        for p in projects:
            fields = p.get("fields", {})
            client = fields.get("client", "?")
            name = fields.get("project_name", "?")
            phase = p.get("bfa_phase_canonical", "?")
            rec_id = p.get("project_record_id", "")
            marker = " [linked]" if rec_id else ""
            print(f"  {client} - {name}: {phase}{marker}")
        print(f"\n{len(projects)} projects ({sum(1 for p in projects if p.get('project_record_id'))} linked)")
        return

    print(f"Entries: {len(projects)} projects")
    if args.clickup_only:
        print("(filtered to source=clickup)")
    print()
    for p in projects:
        _print_entry(p)


def _print_entry(entry, verbose=False):
    fields = entry.get("fields", {})
    sec = entry.get("sections", {})
    print(f"{fields.get('client', '?')} - {fields.get('project_name', '?')}")
    print(f"  uid: {entry.get('uid')}")
    print(f"  source: {entry.get('source')}")
    print(f"  project_record_id: {entry.get('project_record_id')}")
    print(f"  bfa_phase_canonical: {entry.get('bfa_phase_canonical')}")
    ns = sec.get("next_steps", {}).get("text", "")
    print(f"  next_steps: {ns[:150]}")
    if verbose:
        print(f"  header: {entry.get('header', {}).get('text', '')[:120]}")
        for sec_name, sec_data in sec.items():
            print(f"  section/{sec_name}: {sec_data.get('text', '')[:100]}")
    print()


if __name__ == "__main__":
    main()
