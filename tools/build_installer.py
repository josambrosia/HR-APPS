"""Build the HR-Absensi installer.

Single-command end-to-end build: PyInstaller bundle → Inno Setup installer.

Steps:
  1. Pre-flight: verify Inno Setup CLI (ISCC.exe) is on PATH; verify
     HR-Absensi.exe is not currently running (PyInstaller would fail);
     read APP_VERSION from src/config.py.
  2. PyInstaller: produce dist/HR-Absensi/ from HR-Absensi.spec.
  3. ISCC: run installer/HR-Absensi.iss with /DAppVersion=<value>,
     producing installer/Output/HR-Absensi-Setup-vX.Y.Z.exe.

Usage:
  python -m tools.build_installer            # full build
  python -m tools.build_installer --skip-pyi # skip PyInstaller (re-package existing dist/)
  python -m tools.build_installer --allow-dirty  # don't warn about uncommitted changes

Fail-fast: any step's non-zero exit code aborts the build.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PY = WORKTREE_ROOT / "src" / "config.py"
ISS_FILE = WORKTREE_ROOT / "installer" / "HR-Absensi.iss"
ISS_OUTPUT_DIR = WORKTREE_ROOT / "installer" / "Output"
PYI_DIST_DIR = WORKTREE_ROOT / "dist" / "HR-Absensi"
PYI_EXE = PYI_DIST_DIR / "HR-Absensi.exe"

INNO_INSTALL_URL = "https://jrsoftware.org/isdl.php"
INNO_DEFAULT_PATH_HINT = (
    "Default install path: C:\\Program Files (x86)\\Inno Setup 6\\ "
    "(ISCC.exe must be on PATH or in that folder)"
)


def read_app_version() -> str:
    """Parse APP_VERSION literal from src/config.py without importing it."""
    text = CONFIG_PY.read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.MULTILINE)
    if not m:
        sys.exit(f"ERROR: could not parse APP_VERSION from {CONFIG_PY}")
    return m.group(1)


def find_iscc() -> str:
    """Locate ISCC.exe on PATH; exit with install hint if missing."""
    iscc = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if iscc:
        return iscc
    sys.exit(
        f"ERROR: Inno Setup CLI (ISCC.exe) not found on PATH.\n"
        f"  Install from: {INNO_INSTALL_URL}\n"
        f"  {INNO_DEFAULT_PATH_HINT}\n"
        f"  After install, restart your shell so PATH refreshes."
    )


def check_exe_not_running() -> None:
    """Warn if HR-Absensi.exe is running (PyInstaller would fail)."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq HR-Absensi.exe"],
            text=True, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return  # tasklist not available (non-Windows dev env?) — skip
    if "HR-Absensi.exe" in out:
        sys.exit(
            "ERROR: HR-Absensi.exe is currently running. Close it before rebuilding "
            "(PyInstaller can't overwrite a running .exe)."
        )


def check_git_clean(allow_dirty: bool) -> None:
    """Warn (not fail) if there are uncommitted changes."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            text=True, cwd=WORKTREE_ROOT, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return
    if out.strip() and not allow_dirty:
        print(
            "WARNING: working tree has uncommitted changes. The built installer "
            "may not match any committed version. Use --allow-dirty to silence."
        )


def run_pyinstaller() -> None:
    print("=== Step 2/3: PyInstaller ===")
    rc = subprocess.call(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "HR-Absensi.spec"],
        cwd=WORKTREE_ROOT,
    )
    if rc != 0:
        sys.exit(f"ERROR: PyInstaller failed with exit code {rc}")
    if not PYI_EXE.exists():
        sys.exit(f"ERROR: PyInstaller succeeded but {PYI_EXE} is missing")


def run_iscc(iscc: str, version: str) -> Path:
    print(f"=== Step 3/3: Inno Setup (version {version}) ===")
    rc = subprocess.call(
        [iscc, f"/DAppVersion={version}", str(ISS_FILE)],
        cwd=WORKTREE_ROOT,
    )
    if rc != 0:
        sys.exit(f"ERROR: ISCC failed with exit code {rc}")
    out_path = ISS_OUTPUT_DIR / f"HR-Absensi-Setup-v{version}.exe"
    if not out_path.exists():
        sys.exit(f"ERROR: ISCC succeeded but {out_path} is missing")
    return out_path


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Build the HR-Absensi installer.")
    parser.add_argument("--skip-pyi", action="store_true",
                        help="Skip PyInstaller; reuse existing dist/HR-Absensi/")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Suppress the uncommitted-changes warning")
    args = parser.parse_args(argv)

    print("=== Step 1/3: Pre-flight ===")
    iscc = find_iscc()
    print(f"  ISCC: {iscc}")
    check_exe_not_running()
    print("  HR-Absensi.exe: not running")
    check_git_clean(args.allow_dirty)
    version = read_app_version()
    print(f"  APP_VERSION: {version}")

    if args.skip_pyi:
        if not PYI_EXE.exists():
            sys.exit(
                f"ERROR: --skip-pyi was passed but {PYI_EXE} is missing. "
                "Run without --skip-pyi to build it first."
            )
        print("  Skipping PyInstaller (--skip-pyi)")
    else:
        run_pyinstaller()

    out_path = run_iscc(iscc, version)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print()
    print(f"=== Build complete ===")
    print(f"  Output: {out_path}")
    print(f"  Size:   {size_mb:.1f} MB")
    print()
    print("Next: smoke-test by running the .exe on a clean Windows account,")
    print("or by following installer/README.md section 'Manual smoke checklist'.")


if __name__ == "__main__":
    main(sys.argv[1:])
