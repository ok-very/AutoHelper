"""
Build orchestrator — runs PyInstaller to produce autohelper.exe.

The installer is built by Electron Forge (desktop/).
This script handles the PyInstaller step and copies the output
to desktop/autohelper/ where Forge expects it.

Usage:
    python scripts/build_installer.py
    python scripts/build_installer.py --skip-pyinstaller   # Reuse existing dist/
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SPEC_FILE = ROOT / "scripts" / "autohelper.spec"
DESKTOP_AUTOHELPER = ROOT / "desktop" / "autohelper"

DEFAULT_VERSION = "0.1.0"


def run(cmd: list[str], label: str, cwd: Path | None = None) -> None:
    """Run a command, print output, and exit on failure."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n")

    result = subprocess.run(cmd, cwd=str(cwd or ROOT))
    if result.returncode != 0:
        print(f"\nERROR: {label} failed (exit code {result.returncode})")
        sys.exit(result.returncode)



def get_version() -> str:
    """Read version from __init__.py."""
    init_file = ROOT / "autohelper" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text()
        match = re.search(r'__version__\s*=\s*"(.+?)"', content)
        if match:
            return match.group(1)
    return DEFAULT_VERSION


def step_pyinstaller(skip: bool) -> None:
    """Step 1: Run PyInstaller."""
    if skip:
        print("Skipping PyInstaller (--skip-pyinstaller)")
        return

    run(
        [sys.executable, "-m", "PyInstaller", str(SPEC_FILE), "--clean", "--noconfirm"],
        "PyInstaller Build",
    )


def verify_pyinstaller_output() -> None:
    """Verify PyInstaller produced the expected executable."""
    autohelper_exe = DIST / "autohelper" / "autohelper.exe"

    if not autohelper_exe.exists():
        print(f"ERROR: Expected {autohelper_exe} not found")
        print("Run without --skip-pyinstaller first.")
        sys.exit(1)

    print(f"\nPyInstaller output:")
    print(f"  {autohelper_exe}")


def step_copy_to_desktop() -> None:
    """Copy PyInstaller output to apps/desktop/autohelper/ for Electron Forge."""
    src = DIST / "autohelper"
    dst = DESKTOP_AUTOHELPER

    print(f"\n{'=' * 60}")
    print(f"  Copying to {dst}")
    print(f"{'=' * 60}\n")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"  {src} -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AutoHelper via PyInstaller")
    parser.add_argument(
        "--skip-pyinstaller", action="store_true",
        help="Skip PyInstaller step (reuse existing dist/)",
    )
    parser.add_argument(
        "--version", type=str, default=None,
        help="Override version (default: read from __init__.py)",
    )
    args = parser.parse_args()

    version = args.version or get_version()
    print(f"Building AutoHelper v{version}")

    # Step 1: PyInstaller
    step_pyinstaller(args.skip_pyinstaller)
    verify_pyinstaller_output()

    # Step 2: Copy to apps/desktop/autohelper for Electron Forge
    step_copy_to_desktop()

    print(f"\n{'=' * 60}")
    print(f"  Build complete")
    print(f"{'=' * 60}")
    print(f"\n  dist/autohelper/autohelper.exe")
    print(f"  {DESKTOP_AUTOHELPER}/autohelper.exe")


if __name__ == "__main__":
    main()
