import os
import time
import shutil
import sqlite3
import sys
from pathlib import Path

"""Manual verification script for rename logic.

This module is intended for local, ad-hoc verification only and should not be
imported by production code.
"""

# Customizable paths via environment variables
# Defaults assume running from project root
AUTOHELPER_ROOT = Path(os.getenv("AUTOHELPER_ROOT", "."))
DB_PATH = os.getenv("AUTOHELPER_DEV_DB", str(AUTOHELPER_ROOT / "autohelper/db/dev.db"))
TEST_ROOT = os.getenv("AUTOHELPER_TEST_ROOT", str(AUTOHELPER_ROOT / "test_playground"))

def setup_path():
    """Ensure autohelper can be imported."""
    sys.path.append(str(AUTOHELPER_ROOT.resolve()))

def manual_test():
    setup_path() # Ensure we can import the app
    
    print("--- Starting Manual Verification ---")
    print(f"DB Path: {DB_PATH}")
    print(f"Test Root: {TEST_ROOT}")
    
    # 1. Setup Test Root
    test_root_path = Path(TEST_ROOT)
    if test_root_path.exists():
        shutil.rmtree(test_root_path)
    test_root_path.mkdir(parents=True, exist_ok=True)
    
    # Create test file
    org_file = test_root_path / "original.txt"
    org_file.write_text("Unique content for rename detection test." + str(time.time()))
    print(f"Created {org_file}")

    # 2. Boot Service (Simulated)
    try:
        from autohelper.db import get_db, init_db
        from autohelper.modules.index.service import IndexService
        from autohelper.modules.reference.service import ReferenceService
        from autohelper.modules.search.service import SearchService
    except ImportError as e:
        print(f"Error importing autohelper: {e}")
        print("Please run this script from the project root or set AUTOHELPER_ROOT.")
        return

    # Ensure DB is initialized if using a temp one or check existing
    # For this script we assume the dev env is set up, but we can try to connect.
    
    # Initialize Service
    try:
        init_db(Path(DB_PATH))
    except Exception as e:
        print(f"Failed to init db: {e}")
        return
        
    conn = get_db()
    
    # Initialize Schema if needed
    try:
        conn.execute("SELECT 1 FROM roots LIMIT 1")
    except sqlite3.OperationalError:
        print("Initializing schema...")
        with open(AUTOHELPER_ROOT / "autohelper/db/migrations/0001_init.sql", "r") as f:
            conn.connect().executescript(f.read())
        # Also run 0003 if needed for aliases?
        # For this test we need aliases table!
        # Check if 0003 exists and run it
        mig_3 = AUTOHELPER_ROOT / "autohelper/db/migrations/0003_file_aliases.sql"
        if mig_3.exists():
            with open(mig_3, "r") as f:
                 conn.connect().executescript(f.read())
        conn.commit()

    index_service = IndexService()
    search_service = SearchService()
    
    # conn is already got above

    # 3. Register Root (Direct SQL bypass for test speed)
    root_id = "test_root_manual_1"
    conn.execute("INSERT OR REPLACE INTO roots (root_id, path, enabled) VALUES (?, ?, 1)", (root_id, str(test_root_path)))
    conn.commit()
    
    # 4. First Scan (Register file)
    print("Running Scan 1...")
    stats = index_service._scan_root(root_id, test_root_path, False)
    print(f"Stats 1: {stats}")
    
    # Get File ID
    row = conn.execute("SELECT file_id FROM files WHERE rel_path = 'original.txt' AND root_id = ?", (root_id,)).fetchone()
    if not row:
        print("FAIL: File not indexed after scan 1")
        return
        
    file_id = row["file_id"]
    print(f"File ID: {file_id}")
    
    # 5. Create Reference (Crucial Step: Registry Check)
    print("Registering Reference...")
    # Manually insert into refs because ref_service requires WorkItemId etc
    conn.execute("INSERT INTO refs (ref_id, work_item_id, context_id, file_id, canonical_path) VALUES (?, ?, ?, ?, ?)", 
                 (f"ref_manual_{int(time.time())}", "wi_1", "ctx_1", file_id, str(org_file)))
    conn.commit()

    # 6. Rename File
    print("Renaming file on disk...")
    renamed_file = test_root_path / "renamed_auto_verif.txt"
    try:
        org_file.rename(renamed_file)
    except OSError as e:
        print(f"Rename failed: {e}")
        return
    
    # 7. Second Scan (Should Detect Rename)
    print("Running Scan 2...")
    stats = index_service._scan_root(root_id, test_root_path, False)
    print(f"Stats 2: {stats}")
    
    # 8. Verification
    # Check Files Table
    row_new = conn.execute("SELECT file_id, canonical_path FROM files WHERE rel_path = 'renamed_auto_verif.txt' AND root_id = ?", (root_id,)).fetchone()
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
        
    # Cleanup
    try:
        shutil.rmtree(test_root_path)
    except:
        pass

if __name__ == "__main__":
    manual_test()
