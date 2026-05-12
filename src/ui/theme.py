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
COLOR_INFO          = "#22D3EE"   # Cyan — Periode, neutral data, info toast
COLOR_SUCCESS       = "#10B981"   # Emerald — Teladan VALUE, Sudah, success
COLOR_WARN          = "#F43F5E"   # Rose — late data, Belum, warning
COLOR_ERROR         = "#DC2626"   # Red (dark) — errors, destructive

# === LEGACY ALIASES (transitional — removed in Phase 6a Commit 7) ===
COLOR_PANEL          = COLOR_SURFACE          # alias (every screen)
COLOR_OK             = COLOR_SUCCESS           # alias (was gold)
COLOR_ERR            = COLOR_ERROR             # alias
COLOR_PANEL_OPEN     = "#1F1F1F"               # Issues OPEN row tint
COLOR_PANEL_RESOLVED = "#141414"               # Issues RESOLVED row tint

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

# === FONT TUPLES (drop into CTkLabel(font=...)) ===
FONT_KPI         = (FONT_FAMILY, 28, "bold")
FONT_DISPLAY     = (FONT_FAMILY, 24, "bold")
FONT_HEADING     = (FONT_FAMILY, 18, "bold")
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
