"""Design tokens — Josaphat Tech Solution palette + scale system.

Single source of truth untuk color, spacing, font, radius. Semua screen
harus import token dari sini — tidak ada hardcoded hex literal.

Refactor history: started purple/indigo (MVP) → adopted Hybrid A brand
(magenta at entry points only) → full JTS overhaul (2026-05-13). Lihat
docs/superpowers/specs/2026-05-13-ui-jts-theme-overhaul-design.md.
"""

# === SURFACE TIER (4 levels for hierarchy in dark UI) ===
COLOR_SIDEBAR       = "#000000"   # Pure black — sidebar (1 step darker than bg)
COLOR_BG            = "#0A0A0A"   # App background (brand black)
COLOR_SURFACE       = "#141414"   # Cards, panels (1 step lighter than bg)
COLOR_SURFACE_HIGH  = "#1F1F1F"   # Hover, active row, treeview heading

# === BORDERS (kritis untuk dark UI hierarchy) ===
COLOR_BORDER        = "#262626"   # Subtle 1px border default
COLOR_BORDER_STRONG = "#404040"   # Focused / selected outline / dashed dropzone

# === TEXT TIER (4 levels grayscale) ===
COLOR_TEXT          = "#FFFFFF"   # Primary
COLOR_TEXT_DIM      = "#A3A3A3"   # Secondary (brand tagline color)
COLOR_TEXT_MUTED    = "#737373"   # Captions, placeholders
COLOR_TEXT_DISABLED = "#525252"   # Disabled, divider labels

# === BRAND ACCENT (Magenta — JTS primary, 3 states) ===
COLOR_ACCENT        = "#EC4899"   # Primary action, active state, brand
COLOR_ACCENT_HOVER  = "#F472B6"   # Hover lighter magenta
COLOR_ACCENT_DEEP   = "#DB2777"   # Pressed darker magenta

# === SECONDARY BRAND (Violet — analogous to magenta) ===
COLOR_SECONDARY        = "#A855F7"   # Top 5 Teladan title, Settings tab indicator
COLOR_SECONDARY_HOVER  = "#C084FC"
COLOR_SECONDARY_DEEP   = "#9333EA"

# === SEMANTIC (dev-tool palette) ===
COLOR_INFO          = "#22D3EE"   # Cyan — Periode, neutral data, sakit, info toast
COLOR_SUCCESS       = "#10B981"   # Emerald — hadir / Teladan VALUE, Sudah, success
COLOR_WARN          = "#FBBF24"   # Amber — late-light, open, Belum, caution
COLOR_DANGER        = "#F97316"   # Orange — late-heavy (between warn and error)
COLOR_ERROR         = "#EF4444"   # Red — absen tanpa alasan, errors, destructive

# === ROW TINTS (4% saturation over COLOR_SURFACE for subtle differentiation) ===
COLOR_ROW_TINT_OPEN     = "#1F1B12"  # subtle amber tint — Issues OPEN rows (needs attention)
COLOR_ROW_TINT_RESOLVED = "#13181B"  # subtle emerald tint — Issues RESOLVED rows
COLOR_ROW_TINT_SUDAH    = "#1B2820"  # subtle emerald tint — Coaching SUDAH rows
COLOR_ROW_TINT_BELUM    = "#1F1B12"  # subtle amber tint — Coaching BELUM rows (needs attention)

# === SPACING SCALE (8pt grid) ===
SPACE_XS  = 4
SPACE_SM  = 8
SPACE_MD  = 12
SPACE_LG  = 16
SPACE_XL  = 24
SPACE_XXL = 32

# === FONT FAMILIES ===
FONT_FAMILY = "Segoe UI"
FONT_MONO   = "Consolas"
# Display family — upgraded to "Space Grotesk" at startup by
# src.ui.fonts.apply_display_font() (which also rebuilds the display tuples
# below). Falls back to FONT_FAMILY when the bundled font can't be loaded.
FONT_DISPLAY_FAMILY = FONT_FAMILY

# === FONT TUPLES (drop into CTkLabel(font=...)) ===
FONT_KPI         = (FONT_DISPLAY_FAMILY, 28, "bold")
FONT_DISPLAY     = (FONT_DISPLAY_FAMILY, 24, "bold")
FONT_HEADING     = (FONT_DISPLAY_FAMILY, 18, "bold")
FONT_SUBHEAD     = (FONT_FAMILY, 14, "bold")
FONT_BODY        = (FONT_FAMILY, 12)
FONT_BODY_BOLD   = (FONT_FAMILY, 12, "bold")
FONT_SMALL       = (FONT_FAMILY, 11)
FONT_LABEL       = (FONT_FAMILY, 10, "bold")

FONT_MONO_DATA   = (FONT_MONO, 12)
FONT_MONO_BRAND  = (FONT_MONO, 13, "bold")
FONT_MONO_SMALL  = (FONT_MONO, 10)

# === RADIUS ===
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12

# === SEMANTIC TINTS (v22 — bg/border/text sets for banners, badges, chips) ===
# Low-saturation dark tints paired with the SEMANTIC colors above. Formerly
# duplicated hex literals across Import/Export/Outlier/Holiday/app sidebar.
COLOR_INFO_TINT_BG        = "#08222B"   # cyan 8% on dark — active-month banner/badge bg
COLOR_INFO_TINT_BORDER    = "#12454F"   # cyan tint border
COLOR_INFO_TINT_TEXT      = "#5FB8C8"   # cyan 30% — "BULAN AKTIF" caption on tint bg

COLOR_WARN_TINT_BG        = "#2A0A14"   # rose — mismatch / warning banner bg
COLOR_WARN_TINT_BORDER    = "#5C1E2A"   # rose tint border
COLOR_WARN_TINT_BADGE_BG  = "#22141A"   # muted rose — partial-result badge bg (export history)

COLOR_SUCCESS_TINT_BG     = "#0F2218"   # emerald — success strip / full-result badge bg
COLOR_SUCCESS_TINT_BORDER = "#1A4434"   # emerald tint border

COLOR_VIOLET_TINT_BG      = "#160E1C"   # violet — excluded (Outlier) / holiday row bg
COLOR_VIOLET_TINT_BORDER  = "#3A2348"   # violet tint border

COLOR_ACCENT_TINT_BG      = "#27101C"   # magenta 10% — sidebar active-month chip bg
COLOR_ACCENT_TINT_BORDER  = "#5A1E3A"   # magenta 25% — sidebar active-month chip border

# === TEXT TIER (extension) ===
COLOR_TEXT_SOFT           = "#C0C0C0"   # Nav item resting text — between TEXT and TEXT_DIM
