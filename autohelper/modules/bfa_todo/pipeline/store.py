"""
Manages the YAML project modules on disk.
One file per project in data_dir()/bfa_todo/projects/<uid>.yaml
Index file at data_dir()/bfa_todo/index.yaml
Aliases file at data_dir()/bfa_todo/aliases.yaml
"""

import yaml
from . import config


def save_project(project_data):
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    uid = project_data["uid"]
    filepath = config.PROJECTS_DIR / f"{uid}.yaml"

    # Strip transient derived data (runs, inline_html) before persisting
    data = project_data.copy()
    if "sections" in data:
        cleaned_sections = {}
        for key, sec in data["sections"].items():
            cleaned = {k: v for k, v in sec.items() if k not in ("runs", "inline_html")}
            cleaned_sections[key] = cleaned
        data["sections"] = cleaned_sections
    if "header" in data and isinstance(data["header"], dict):
        data["header"] = {k: v for k, v in data["header"].items() if k != "inline_html"}

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            width=120,
            sort_keys=False,
        )
    return str(filepath)


def save_index(projects):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    for p in projects:
        entry = {
            "uid": p["uid"],
            "slug": p["slug"],
            "type": p["type"],
        }
        if p["type"] == "project":
            entry["client"] = p["fields"].get("client", "TBC")
            entry["project_name"] = p["fields"].get("project_name", "TBC")
        index.append(entry)

    filepath = config.DATA_DIR / "index.yaml"
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(
            {"version": 2, "project_count": len(index), "projects": index},
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
    return str(filepath)


def load_index():
    filepath = config.DATA_DIR / "index.yaml"
    if not filepath.exists():
        return {"version": 2, "project_count": 0, "projects": []}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_project(uid):
    filepath = config.PROJECTS_DIR / f"{uid}.yaml"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_projects(include_archived=False):
    """Load all projects from disk.

    If include_archived is False, projects with status='archived' are excluded.
    """
    index = load_index()
    projects = []
    seen_uids = set()
    for entry in index.get("projects", []):
        uid = entry["uid"]
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        p = load_project(uid)
        if p:
            if not include_archived and p.get("status") == "archived":
                continue
            projects.append(p)
    return projects


def archive_project(uid):
    """Set a project's status to 'archived' (does not delete the file)."""
    project = load_project(uid)
    if project:
        project["status"] = "archived"
        save_project(project)
        return True
    return False


def load_aliases():
    """Load the aliases.yaml identity mapping table."""
    if not config.ALIASES_FILE.exists():
        return {
            "version": 1,
            "mappings": [],
            "rollups": [],
            "ignored": [],
            "client_aliases": {},
        }
    with open(config.ALIASES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def save_aliases(aliases):
    """Write the aliases.yaml identity mapping table."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.ALIASES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(
            aliases,
            f,
            default_flow_style=False,
            allow_unicode=True,
            width=120,
            sort_keys=False,
        )
    return str(config.ALIASES_FILE)
