#!/bin/bash
# PostToolUse hook: run BFA test suite after edits to bfa_todo files.
# Blocks the edit if tests fail, so regressions are caught immediately.

INPUT=$(cat)

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/Scripts/python"

# Extract file_path from JSON using Python (no jq on this system)
FILE_PATH=$(echo "$INPUT" | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Normalize to forward slashes for matching
FILE_PATH="${FILE_PATH//\\//}"

# Only gate on bfa_todo module, ingestion script, and test files
case "$FILE_PATH" in
  */modules/bfa_todo/*|*/scripts/ingest_gdocs_docx.py|*/tests/test_docx_run*|*/tests/test_prepare_html*|*/tests/test_render_round*)
    ;;
  *)
    exit 0
    ;;
esac

if [ ! -f "$PYTHON" ]; then
  echo '{"decision":"block","reason":"Python venv not found at .venv/Scripts/python — run mise run venv"}'
  exit 0
fi

# Run fast unit tests (extractor + prepare_html). ~4s.
TEST_OUTPUT=$("$PYTHON" -m pytest \
  "$PROJECT_DIR/tests/test_docx_run_extractor.py" \
  "$PROJECT_DIR/tests/test_prepare_html_for_word.py" \
  -x -q --tb=short 2>&1)
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
  # Truncate and escape output for JSON
  TRUNCATED=$(echo "$TEST_OUTPUT" | tail -30)
  ESCAPED=$(echo "$TRUNCATED" | "$PYTHON" -c "import sys,json; print(json.dumps(sys.stdin.read()))" | sed 's/^"//;s/"$//')
  echo "{\"decision\":\"block\",\"reason\":\"BFA tests failed after editing $FILE_PATH:\\n$ESCAPED\"}"
  exit 0
fi

# Tests passed — continue
exit 0
