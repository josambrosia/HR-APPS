import sys
from pathlib import Path

APP_NAME = "HR Absensi App"
APP_VERSION = "16.1.0"
APP_BUILD_DATE = "2026-06-09"  # YYYY-MM-DD; bumped manually with APP_VERSION on release
APP_TAGLINE = "From Concept to Code."
APP_BRAND_NAME = "Josaphat Tech Solution"

# Changelog displayed in the About dialog.
# Format: list of dicts with 'version', 'date' (YYYY-MM-DD), 'changes' list.
# Each change is a (kind, description) tuple. Kinds:
#   "feat"   — fitur baru
#   "fix"    — perbaikan bug
#   "change" — perubahan / penyesuaian perilaku
#   "remove" — penghapusan fitur
#
# DISCIPLINE: every new version MUST prepend an entry here. Newest at top.
APP_CHANGELOG = [
    {
        "version": "16.1.0",
        "date": "2026-06-09",
        "changes": [
            ("feat", "Menu About sekarang menampilkan changelog tiap versi (apa yang baru / berubah / diperbaiki)."),
            ("fix", "Ctrl+F sekarang berfungsi dari mana saja di Issues & Outlier — sebelumnya tidak nyala kalau fokus ada di tabel."),
            ("fix", "Enter submit Save di panel kanan Issues sekarang berfungsi saat fokus ada di field kategori / detail."),
            ("remove", "Strip 'Status Issues' di print dashboard dihilangkan (informasi sudah cukup dari KPI cards)."),
        ],
    },
    {
        "version": "16.0.2",
        "date": "2026-06-09",
        "changes": [
            ("change", "Search bar dipindah dari header ke dekat tabel (Issues) dan ke baris bawah header (Outlier) agar tidak crowding."),
            ("fix", "Placeholder 'Cari karyawan...' sekarang terlihat (sebelumnya tampak kosong karena bug CTkEntry + StringVar)."),
        ],
    },
    {
        "version": "16.0.1",
        "date": "2026-06-09",
        "changes": [
            ("fix", "Tombol + Resolve Massal yang hilang dari header Issues — sebelumnya ter-push off-screen oleh search bar."),
        ],
    },
    {
        "version": "16.0.0",
        "date": "2026-06-09",
        "changes": [
            ("feat", "Cross-screen week selection — pilihan minggu nempel saat pindah antar menu (Issues / Dashboard / Coaching)."),
            ("feat", "Search/filter karyawan di Issues (Open + Resolved) dan Outlier (section Disertakan)."),
            ("feat", "Keyboard shortcuts: Ctrl+F fokus search, Esc tutup dialog, Enter submit di dialog."),
            ("feat", "Menu About di sidebar (info versi, build, Python, database path)."),
            ("feat", "Print dashboard: badge dinamis WEEKLY/MONTHLY, period inline di judul, KPI delta vs periode sebelumnya, garis transparansi outlier."),
        ],
    },
    {
        "version": "15.3.0",
        "date": "2026-05-25",
        "changes": [
            ("fix", "Tombol Resolve / Batal yang hilang di dialog Resolve Massal saat pilih kategori tanpa kolom detail — arsitektur header/scrollable/footer."),
        ],
    },
    {
        "version": "15.0.0",
        "date": "2026-05-24",
        "changes": [
            ("feat", "Kategori 'Lupa Absen' dipecah jadi Lupa Absen Datang (kena penalti) dan Lupa Absen Pulang (tidak)."),
            ("feat", "Penalti Lupa Absen Datang bisa diatur di Settings (default 15 menit, validasi 0-999)."),
            ("change", "Format baris Hari Libur di Laporan Bulanan: Tipe='Hari Libur', Masuk/Keluar kosong, fill kuning krim."),
            ("fix", "Awal upaya perbaikan tombol Resolve Massal (selesai di v15.3)."),
        ],
    },
    {
        "version": "14.0.0",
        "date": "2026-05-23",
        "changes": [
            ("feat", "Coaching threshold dinamis: kuota mnt/hari × jumlah hari kerja periode."),
            ("feat", "Windows installer (per-user install, Start Menu shortcut, Add/Remove Programs)."),
        ],
    },
]


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
# Template path UPDATED for folder consolidation (was: RESOURCE_ROOT / "templates" / ...)
TEMPLATE_LAPORAN_BULANAN = RESOURCE_ROOT / "assets" / "templates" / "laporan_bulanan_template.xlsx"

# Brand assets (Josaphat Tech Solution — see docs/superpowers/specs/2026-05-12-josaphat-tech-brand-design.md)
BRAND_DIR = RESOURCE_ROOT / "assets" / "brand"
BRAND_ICON_SVG = BRAND_DIR / "icon-04E.svg"
BRAND_ICON_ICO = BRAND_DIR / "icon-04E.ico"
BRAND_LOCKUP_DARK_SVG = BRAND_DIR / "lockup-04E-dark.svg"
BRAND_LOCKUP_LIGHT_SVG = BRAND_DIR / "lockup-04E-light.svg"
BRAND_ANIMATION_SVG = BRAND_DIR / "animation-02-typing-04E.svg"
BRAND_ANIMATION_GIF = BRAND_DIR / "animation-02-typing-04E.gif"

# Defaults
DEFAULT_SCHEDULE_START = "08.00"
DEFAULT_SCHEDULE_END = "16.00"
DEFAULT_COACHING_THRESHOLD_PER_DAY = 15
DEFAULT_LUPA_PENALTY_MIN = 15

# Reason categories (canonical IDs used in DB and UI)
REASON_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "izin_sakit",
    "cuti",
    "tugas_belajar",
    "terlambat_kerja",
    "terlambat_lain",
    "lupa_absen_datang",
    "lupa_absen_pulang",
    "libur",
    "na",
)

# Reason category values that mark a row's lateness as work-justified —
# rows with one of these categories are EXCLUDED from the weekly
# terlambat_menit sum used for coaching_flag (see design spec section 6).
COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")
