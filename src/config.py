from pathlib import Path

APP_NAME = "HR Absensi App"
APP_VERSION = "0.1.0"

# Paths (resolved relative to .exe / project root at runtime)
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "hr.db"
TEMPLATES_DIR = ROOT_DIR / "src" / "reports" / "templates"

# Defaults
DEFAULT_SCHEDULE_START = "08.00"
DEFAULT_SCHEDULE_END = "16.00"
DEFAULT_COACHING_THRESHOLD_MIN = 75

# Reason categories (canonical IDs)
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

# Categories that EXCLUDE terlambat_menit from coaching counter
COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")
