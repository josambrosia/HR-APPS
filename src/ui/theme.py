"""Color palette + typography constants for the app.

Theme inspired by user-provided palette:
- Dark indigo background, medium purple panels
- Warm orange + gold accents (replacing the old cool blue palette)
"""

# Base
COLOR_BG = "#1E104E"          # dark indigo — app background
COLOR_PANEL = "#452E5A"       # medium purple — cards, panels, treeview body

# Accents
COLOR_ACCENT = "#FF653F"      # vivid orange — active state, primary actions, errors
COLOR_OK = "#FFC85C"          # gold — success / teladan / warnings (softer than orange)
COLOR_WARN = "#FFC85C"        # gold — same as OK; reserved for cautionary info
COLOR_ERR = "#FF653F"         # orange — destructive / hard errors

# Subtle table-row backgrounds — close to COLOR_PANEL but distinguishable
# (slight warm vs cool tint without high contrast)
COLOR_PANEL_OPEN = "#523456"        # slightly warmer / lighter purple
COLOR_PANEL_RESOLVED = "#3B2A4D"    # slightly cooler / darker purple

# Text
COLOR_TEXT = "#F5F1FF"         # near-white with hint of lavender
COLOR_TEXT_DIM = "#A9A0C5"     # muted lavender for sub-text

FONT_FAMILY = "Segoe UI"
