
import os
import time
import shutil
import sqlite3
from pathlib import Path

# Paths (Adjust to your local dev environment)
DB_PATH = "c:/Users/silen/Documents/automatiq/AutoHelper/autohelper/db/dev.db" # Default dev db
TEST_ROOT = "c:/Users/silen/Documents/automatiq/AutoHelper/test_playground" # A root we will create

def setup_db_mock(db_path):
    # Ensure tables exist (normally migration script does this)
    # This assumes migrations ran. 
    # If not, we might need to run them or just check the table exists.
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Check if file_aliases exists
    try:
        cur.execute("SELECT 1 FROM file_aliases LIMIT 1")
    except sqlite3.OperationalError:
        print("ERROR: file_aliases table does not exist. Migrations not run?")
        return False
    return conn

def manual_test():
    print("--- Starting Manual Verification ---")
    
    # 1. Setup Test Root
    test_root_path = Path(TEST_ROOT)
    if test_root_path.exists():
        shutil.rmtree(test_root_path)
    test_root_path.mkdir(exist_ok=True)
    
    # Create test file
    org_file = test_root_path / "original.txt"
    org_file.write_text("Unique content for rename detection test." + str(time.time()))
    print(f"Created {org_file}")

    # 2. Boot Service (Simulated)
    # We need to import the service classes from the project
    # Assumes python path is set correctly
    import sys
    sys.path.append("c:/Users/silen/Documents/automatiq/AutoHelper")
    
    from autohelper.db import get_db
    from autohelper.modules.index.service import IndexService
    from autohelper.modules.reference.service import ReferenceService
    from autohelper.modules.search.service import SearchService
    from autohelper.modules.reference.schemas import ReferenceCreate

    # Hack: Inject DB override via context/dependency shim if needed
    # Standard get_db() should pickup config.
    
    index_service = IndexService()
    ref_service = ReferenceService()
    search_service = SearchService()
    
    conn = get_db()

    # 3. Register Root (Direct SQL bypass for test speed)
    root_id = "test_root_1"
    conn.execute("INSERT OR REPLACE INTO roots (root_id, path, enabled) VALUES (?, ?, 1)", (root_id, str(test_root_path)))
    conn.commit()
    
    # 4. First Scan (Register file)
    print("Running Scan 1...")
    stats = index_service._scan_root(root_id, test_root_path, False)
    print(f"Stats 1: {stats}")
    
    # Get File ID
    row = conn.execute("SELECT file_id FROM files WHERE rel_path = 'original.txt'").fetchone()
    file_id = row["file_id"]
    print(f"File ID: {file_id}")
    
    # 5. Create Reference (Crucial Step: Registry Check)
    print("Registering Reference...")
    # Manually insert into refs because ref_service requires WorkItemId etc
    conn.execute("INSERT INTO refs (ref_id, work_item_id, context_id, file_id, canonical_path) VALUES (?, ?, ?, ?, ?)", 
                 ("ref_1", "wi_1", "ctx_1", file_id, str(org_file)))
    conn.commit()

    # 6. Rename File
    print("Renaming file on disk...")
    # Wait minimal time to ensure fs checks happen? or just mtime check handles it
    renamed_file = test_root_path / "renamed_auto_verif.txt"
    org_file.rename(renamed_file)
    
    # 7. Second Scan (Should Detect Rename)
    print("Running Scan 2...")
    stats = index_service._scan_root(root_id, test_root_path, False)
    print(f"Stats 2: {stats}")
    
    # 8. Verification
    # Check Files Table
    row_new = conn.execute("SELECT file_id, canonical_path FROM files WHERE rel_path = 'renamed_auto_verif.txt'").fetchone()
    if not row_new:
        print("FAIL: Renamed file not found in files table")
        return
        
    if row_new["file_id"] != file_id:
        print(f"FAIL: File ID changed! Old: {file_id}, New: {row_new['file_id']}")
    else:
        print("PASS: File ID persisted.")

    # Check Aliases Table
    alias_count = conn.execute("SELECT count(*) as c FROM file_aliases WHERE file_id = ? AND old_canonical_path = ?", (file_id, str(org_file))).fetchone()["c"]
    if alias_count > 0:
        print("PASS: Alias record found.")
    else:
        print("FAIL: No alias record found.")

    # 9. Search Verification
    print("Searching for 'original'...")
    res = search_service.search("original", 10)
    
    found = False
    for item in res.items:
        if item.path == str(renamed_file):
            print(f"PASS: Search for 'original' returned 'renamed_auto_verif.txt'")
            found = True
            break
            
    if not found:
        print("FAIL: Search by old name failed.")
        print(f"Results: {[i.path for i in res.items]}")

if __name__ == "__main__":
    manual_test()
