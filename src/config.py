import sys
from pathlib import Path

APP_NAME = "HR Absensi App"
APP_VERSION = "0.1.0"


def _resource_root() -> Path:
    """Where read-only bundled resources live (templates, icons).

    In a PyInstaller bundle, `sys._MEIPASS` points to the extracted
    resource directory (`_internal/` in --onedir, a temp dir in --onefile).
    In dev mode, falls back to the project root (parent of `src/`).
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _user_data_root() -> Path:
    """Where read/write user data lives (db, exports).

    In a PyInstaller bundle (`sys.frozen`), this is the directory of the
    .exe — so `data/hr.db` survives version updates that overwrite
    `_internal/`. In dev mode, falls back to the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


# Paths
RESOURCE_ROOT = _resource_root()
USER_DATA_ROOT = _user_data_root()
DATA_DIR = USER_DATA_ROOT / "data"
DB_PATH = DATA_DIR / "hr.db"
TEMPLATES_DIR = RESOURCE_ROOT / "src" / "reports" / "templates"

# Brand assets (Josaphat Tech Solution — see docs/superpowers/specs/2026-05-12-josaphat-tech-brand-design.md)
BRAND_DIR = RESOURCE_ROOT / "assets" / "brand"
BRAND_ICON_SVG = BRAND_DIR / "icon-04E.svg"
BRAND_LOCKUP_DARK_SVG = BRAND_DIR / "lockup-04E-dark.svg"
BRAND_LOCKUP_LIGHT_SVG = BRAND_DIR / "lockup-04E-light.svg"
BRAND_ANIMATION_SVG = BRAND_DIR / "animation-02-typing-04E.svg"
BRAND_ANIMATION_GIF = BRAND_DIR / "animation-02-typing-04E.gif"

# Defaults
DEFAULT_SCHEDULE_START = "08.00"
DEFAULT_SCHEDULE_END = "16.00"
DEFAULT_COACHING_THRESHOLD_MINUTES = 75

# Reason categories (canonical IDs used in DB and UI)
REASON_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "izin_sakit",
    "cuti",
    "terlambat_kerja",
    "terlambat_lain",
    "lupa_absen",
    "na",
)

# Reason category values that mark a row's lateness as work-justified —
# rows with one of these categories are EXCLUDED from the weekly
# terlambat_menit sum used for coaching_flag (see design spec section 6).
COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")
