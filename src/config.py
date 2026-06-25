import sys
from pathlib import Path

APP_NAME = "HR Absensi App"
APP_VERSION = "20.0.1"
APP_BUILD_DATE = "2026-06-26"  # YYYY-MM-DD; bumped manually with APP_VERSION on release
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
        "version": "20.0.1",
        "date": "2026-06-26",
        "changes": [
            ("fix", "Cetak Dashboard: angka pada tabel dan indikator naik/turun "
                    "tidak lagi memakai warna brand (magenta). Histogram 'Pola Jam "
                    "Masuk' kini bergradasi 'heat' hijau → kuning → oranye → merah "
                    "(warna ungu/pink dihapus) sehingga tingkat keterlambatan lebih "
                    "mudah dibaca sekilas."),
            ("fix", "Cetak Dashboard: warna jadi konsisten — karyawan teladan hijau, "
                    "kandidat coaching oranye, jumlah tidak hadir merah. Blok tanda "
                    "tangan tidak lagi terdorong ke halaman kosong, dan warna "
                    "dipastikan ikut tercetak walau opsi 'Background graphics' lupa "
                    "dicentang."),
            ("feat", "Cetak Heatmap: judul kolom ringkasan (HK, H, D, TR, TB, S, C, "
                     "LA, X) kini berwarna sesuai penandanya masing-masing (HK "
                     "biru) dan senada dengan warna sel di grid; angka 0 diredupkan "
                     "agar angka yang penting lebih menonjol."),
            ("feat", "Cetak Heatmap: ditambahkan blok tanda tangan 'HR Officer in "
                     "Charge' di akhir laporan, konsisten dengan Cetak Dashboard."),
            ("change", "Cetak Dashboard & Heatmap: ada pengingat di layar untuk "
                       "mematikan 'Headers and footers' di dialog cetak browser, "
                       "agar URL & tanggal lokal tidak ikut tercetak pada PDF."),
        ],
    },
    {
        "version": "20.0.0",
        "date": "2026-06-26",
        "changes": [
            ("change", "Penyegaran tampilan menyeluruh (design system v20). Warna "
                       "status dirombak agar konsisten: magenta kini khusus "
                       "brand/aksi, sedangkan keterlambatan memakai gradasi "
                       "'heat' (amber → oranye → merah) — Heatmap & Dashboard "
                       "jadi jauh lebih mudah dibaca."),
            ("feat", "Strip pola kehadiran bulanan per karyawan di tabel Ranking "
                     "Lengkap (Dashboard): titik berwarna sekilas memperlihatkan "
                     "pola hadir/telat/izin tiap orang, senada dengan Heatmap."),
            ("feat", "Ikon sidebar monokrom yang konsisten (Segoe Fluent) "
                     "menggantikan emoji; menu aktif disorot magenta."),
            ("feat", "Judul layar memakai huruf khas 'Space Grotesk' (otomatis "
                     "kembali ke Segoe UI bila font tak tersedia)."),
            ("feat", "Kartu KPI Dashboard menampilkan perbandingan dengan periode "
                     "sebelumnya (▲/▼ vs bulan/minggu lalu)."),
            ("change", "Tabel lebih rapi: baris lebih tinggi, angka rata kanan, "
                       "striping halus, dan tooltip untuk kolom Alasan yang "
                       "panjang."),
        ],
    },
    {
        "version": "19.0.0",
        "date": "2026-06-25",
        "changes": [
            ("fix", "Field 'Detail' pada panel Resolve (menu Issues & Severe "
                    "Lateness) sekarang bisa diketik dengan normal — sebelumnya "
                    "fokus keyboard tercuri setiap kali field diklik sehingga "
                    "ketikan tidak masuk / kursor hilang."),
            ("fix", "Dashboard kini langsung mencerminkan perubahan data: setiap "
                    "issue yang di-resolve, dibatalkan, di-resolve massal, atau "
                    "saat data fingerprint baru diimpor, angka & panel langsung "
                    "diperbarui — tanpa perlu menutup & membuka ulang aplikasi."),
        ],
    },
    {
        "version": "18.0.0",
        "date": "2026-06-10",
        "changes": [
            ("feat", "Menu baru 'Heatmap' (grup INSIGHT): peta kehadiran bulanan "
                     "per karyawan dengan kode warna status (hadir, terlambat, "
                     "dinas, sakit, cuti, lupa absen, absen). Tampil interaktif di "
                     "dalam aplikasi — cari & urutkan nama (kehadiran terendah / "
                     "paling sering telat / absen), hover & klik sel untuk detail, "
                     "navigasi antar bulan, plus panel ringkasan kehadiran "
                     "(% hadir, tepat waktu, total telat) per karyawan."),
            ("feat", "Versi cetak Heatmap (landscape): matriks Karyawan × Hari "
                     "berkode + ringkasan + lampiran detail. Dialog pra-cetak "
                     "untuk memilih tabel (Full / Matrix / Lampiran) dan "
                     "menyertakan/mengecualikan karyawan outlier."),
            ("feat", "Pengaturan baru 'Toleransi Telat (menit)' di Settings → Umum "
                     "(default 12): keterlambatan sampai ambang ini dianggap "
                     "hadir tepat waktu."),
        ],
    },
    {
        "version": "17.0.0",
        "date": "2026-06-09",
        "changes": [
            ("feat", "Menu baru 'Severe Lateness': mendeteksi keterlambatan harian "
                     "di atas ambang (default 60 menit) walau jam masuk & keluar "
                     "lengkap; resolusi alasan sama seperti Issues."),
            ("feat", "Pengaturan baru 'Severe Lateness Threshold (menit)' di "
                     "Settings → Umum (default 60, rentang 1–999)."),
        ],
    },
    {
        "version": "16.1.1",
        "date": "2026-06-09",
        "changes": [
            ("fix", "Klik di area selain search bar (header / KPI / panel) sekarang melepas fokus dari search."),
            ("fix", "Placeholder 'Cari karyawan...' yang kadang tetap muncul saat field sudah berisi text — sekarang konsisten."),
            ("change", "Warna badge FIX di changelog diganti dari merah ke kuning amber agar lebih pas dengan semantik 'caution'."),
        ],
    },
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
DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN = 60
DEFAULT_LATE_TOLERANCE_MIN = 12

# Heatmap colour grouping — reasons shown GREEN ("Dinas") on the attendance
# heatmap. Deliberately BROADER than COACHING_EXCLUDED (adds tugas_belajar):
# this is a presentation choice and does NOT change coaching/dashboard logic.
HEATMAP_DINAS_REASONS = (
    "tugas_lapangan", "tugas_paparan", "tugas_belajar", "terlambat_kerja",
)

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

# Reason categories shown in the Severe Lateness resolve panel — a subset of
# REASON_CATEGORIES relevant when BOTH punches are present (so lupa_absen_* and
# libur are excluded). terlambat_kerja is in COACHING_EXCLUDED (justified late →
# dropped from coaching); terlambat_lain is not (stays counted, just annotated).
SEVERE_LATENESS_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "terlambat_kerja",
    "terlambat_lain",
    "izin_sakit",
    "cuti",
    "na",
)

# Reason category values that mark a row's lateness as work-justified —
# rows with one of these categories are EXCLUDED from the weekly
# terlambat_menit sum used for coaching_flag (see design spec section 6).
COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")
