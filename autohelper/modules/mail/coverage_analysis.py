"""
Project Coverage Analysis
Pull project states from Monday.com and cross-reference with inference engine.
"""

from monday_api import search_boards, get_board_items, get_board_schema
from typing import Dict, List
import json

# Neal's projects
NEAL_PROJECTS = [
    "Aragon – E 49th",
    "AviSina – Broadway Village",
    "Intracorp – Arbutus",
    "Keltic – 6620 Sussex",
    "Lowtide – Canada Goose",
]

# Assist projects
ASSIST_PROJECTS = [
    ("UBC Gateway", "Ellen"),
    ("PC Urban – Barnard", "Ellen"),
    ("PC Urban - Uptown", "Ellen"),
    ("NSPH – All Nations Sacred Space", "Alannah"),
    ("NSPH Exterior", "Alannah"),
    ("NSPH Interior", "Alannah"),
]

# Policy matrix stages for cross-reference
STAGES = {
    3: "Checklist",
    4: "PPAP",
    5: "DPAP",
    6: "Selection",
    7: "Contract",
    8: "Management",
    9: "Installation",
    10: "Final Doc",
}

# Keywords that indicate stage (from policyMatrix.ts)
STAGE_KEYWORDS = {
    "PPAP": ["ppap", "preliminary", "proposal"],
    "DPAP": ["dpap", "detailed", "pac feedback"],
    "Selection": ["selection", "panel", "longlist", "shortlist", "eoi"],
    "Contract": ["contract", "agreement"],
    "Management": ["update", "status", "report", "progress"],
    "Installation": ["installation", "install", "fabrication"],
    "Final Doc": ["final", "report", "plaque", "maintenance", "maintenance manual"],
}


def search_project(project_name: str) -> Dict:
    """Search for a project board and get its items"""
    # Clean project name for search
    search_terms = project_name.replace("–", "-").split("-")
    
    # Try different search strategies
    for term in search_terms:
        term = term.strip()
        if len(term) < 3:
            continue
        
        results = search_boards(term, limit=10)
        if "error" not in results and results.get("boards"):
            # Find best match
            for board in results["boards"]:
                if any(t.lower() in board["name"].lower() for t in search_terms):
                    return {
                        "found": True,
                        "board": board,
                        "search_term": term
                    }
    
    return {"found": False, "search_term": project_name}


def analyze_board_items(board_id: str) -> Dict:
    """Analyze board items for stage coverage"""
    items = get_board_items(board_id, limit=100)
    
    if "error" in items:
        return items
    
    analysis = {
        "total_items": items["count"],
        "columns": items["columns"],
        "stage_coverage": {},
        "items_by_stage": {},
    }
    
    # Analyze each item for stage keywords
    for item in items["items"]:
        item_text = f"{item['name']} {item.get('group', '')}".lower()
        
        for stage, keywords in STAGE_KEYWORDS.items():
            for kw in keywords:
                if kw in item_text:
                    if stage not in analysis["stage_coverage"]:
                        analysis["stage_coverage"][stage] = 0
                        analysis["items_by_stage"][stage] = []
                    analysis["stage_coverage"][stage] += 1
                    analysis["items_by_stage"][stage].append(item["name"])
                    break
    
    return analysis


def run_analysis():
    """Run full project coverage analysis"""
    print("=" * 60)
    print("PROJECT COVERAGE ANALYSIS")
    print("=" * 60)
    
    all_projects = []
    coverage_stats = {stage: 0 for stage in STAGE_KEYWORDS.keys()}
    
    # Analyze Neal's projects
    print("\n📋 NEAL'S PROJECTS")
    print("-" * 40)
    
    for project in NEAL_PROJECTS:
        print(f"\n🔍 Searching: {project}")
        result = search_project(project)
        
        if result["found"]:
            board = result["board"]
            print(f"   ✓ Found: {board['name']} (ID: {board['id']})")
            
            analysis = analyze_board_items(board["id"])
            if "error" not in analysis:
                print(f"   Items: {analysis['total_items']}")
                print(f"   Stage coverage: {list(analysis['stage_coverage'].keys())}")
                
                all_projects.append({
                    "name": project,
                    "owner": "Neal",
                    "board": board,
                    "analysis": analysis
                })
                
                for stage in analysis["stage_coverage"]:
                    coverage_stats[stage] += 1
        else:
            print(f"   ✗ Not found")
            all_projects.append({
                "name": project,
                "owner": "Neal",
                "board": None,
                "analysis": None
            })
    
    # Analyze Assist projects
    print("\n📋 ASSIST PROJECTS")
    print("-" * 40)
    
    for project, lead in ASSIST_PROJECTS:
        print(f"\n🔍 Searching: {project} ({lead})")
        result = search_project(project)
        
        if result["found"]:
            board = result["board"]
            print(f"   ✓ Found: {board['name']} (ID: {board['id']})")
            
            analysis = analyze_board_items(board["id"])
            if "error" not in analysis:
                print(f"   Items: {analysis['total_items']}")
                print(f"   Stage coverage: {list(analysis['stage_coverage'].keys())}")
                
                all_projects.append({
                    "name": project,
                    "owner": lead,
                    "board": board,
                    "analysis": analysis
                })
                
                for stage in analysis["stage_coverage"]:
                    coverage_stats[stage] += 1
        else:
            print(f"   ✗ Not found")
            all_projects.append({
                "name": project,
                "owner": lead,
                "board": None,
                "analysis": None
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("COVERAGE SUMMARY")
    print("=" * 60)
    
    found_count = sum(1 for p in all_projects if p["board"])
    print(f"\nBoards found: {found_count}/{len(all_projects)}")
    
    print("\nStage coverage across all projects:")
    for stage, count in coverage_stats.items():
        bar = "█" * count + "░" * (len(all_projects) - count)
        print(f"  {stage:15} [{bar}] {count}/{len(all_projects)}")
    
    # Identify gaps
    print("\n" + "=" * 60)
    print("INFERENCE ENGINE IMPROVEMENTS NEEDED")
    print("=" * 60)
    
    missing_stages = [s for s, c in coverage_stats.items() if c == 0]
    if missing_stages:
        print(f"\n⚠️  No coverage for stages: {', '.join(missing_stages)}")
    
    # Check for columns we're not mapping
    all_columns = set()
    for p in all_projects:
        if p["analysis"]:
            all_columns.update(p["analysis"]["columns"])
    
    print(f"\n📊 Unique columns found across boards:")
    for col in sorted(all_columns):
        print(f"   - {col}")
    
    return all_projects, coverage_stats


if __name__ == "__main__":
    projects, stats = run_analysis()
    
    # Save results
    with open("coverage_analysis.json", "w") as f:
        json.dump({
            "projects": [{
                "name": p["name"],
                "owner": p["owner"],
                "found": p["board"] is not None,
                "board_name": p["board"]["name"] if p["board"] else None,
                "stage_coverage": p["analysis"]["stage_coverage"] if p["analysis"] else {}
            } for p in projects],
            "stats": stats
        }, f, indent=2)
    
    print("\n✓ Results saved to coverage_analysis.json")
