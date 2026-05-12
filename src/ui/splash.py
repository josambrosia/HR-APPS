"""SplashScreen — branded hero with animated progress bar (Option D design).

Visual mockup chosen by user: HD icon card + app name + version inline at top,
tagline below, a determinate progress bar that fills 0→100% over 2s, and the
"Josaphat Tech Solution" brand credit right-aligned below the bar.

Pure customtkinter rendering — no GIF, no SVG rasterization, no PIL pixelation.
The brand icon is reproduced via a `CTkFrame` (rounded card) + nested
`CTkLabel` ("j" glyph) + small `CTkFrame` (magenta cursor strip), all
positioned via `.place()` to mirror the proportions of `icon-04E.svg`.
"""
import customtkinter as ctk

from src.config import APP_VERSION, APP_TAGLINE, APP_BRAND_NAME


class SplashScreen(ctk.CTkToplevel):
    WINDOW_W = 520
    WINDOW_H = 360
    PROGRESS_MS = 2000     # total animation duration
    PROGRESS_STEPS = 100   # number of update calls (20ms per step)

    BG_COLOR = "#0A0A0A"
    ICON_BG = "#1a1a1a"        # slight contrast vs splash bg → rounded card visible
    ACCENT_COLOR = "#EC4899"   # JTS magenta
    TEXT_COLOR = "#FFFFFF"
    DIM_COLOR = "#A3A3A3"
    DIMMER_COLOR = "#525252"
    PROGRESS_BG = "#1a1a1a"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=self.BG_COLOR)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.WINDOW_W) // 2
        y = (self.winfo_screenheight() - self.WINDOW_H) // 2
        self.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}+{x}+{y}")

        self._after_id = None
        self._build_content()
        self._start_progress()

    # ─────────────────────────────────────────────── Layout

    def _build_content(self):
        """S2 — Centered Brand Block: big icon → BRAND NAME (prominent) →
        tagline → progress bar → small app/version line at bottom.
        """
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=30, pady=30)

        # Inner centered stack (vertical centering via expand)
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(expand=True)

        # ── BIG ICON CARD (80×80) ──
        icon = self._make_icon_card(inner, size=80)
        icon.pack(pady=(0, 18))

        # ── BRAND NAME — prominent, 19pt mono bold ──
        ctk.CTkLabel(
            inner, text=APP_BRAND_NAME,
            font=("Consolas", 19, "bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        ).pack(pady=(0, 4))

        # ── TAGLINE — magenta accent ──
        ctk.CTkLabel(
            inner,
            text=f"// {APP_TAGLINE.rstrip('.').lower()}",
            font=("Consolas", 12),
            text_color=self.ACCENT_COLOR,
            fg_color="transparent",
        ).pack(pady=(0, 22))

        # ── PROGRESS BAR — fixed width 320, centered ──
        self._progress = ctk.CTkProgressBar(
            inner,
            width=320, height=6, corner_radius=3,
            progress_color=self.ACCENT_COLOR,
            fg_color=self.PROGRESS_BG,
        )
        self._progress.pack(pady=(0, 14))
        self._progress.set(0)

        # ── APP NAME + VERSION — small, dim, mono ──
        ctk.CTkLabel(
            inner, text=f"HR Absensi · v{APP_VERSION}",
            font=("Consolas", 11),
            text_color=self.DIM_COLOR,
            fg_color="transparent",
        ).pack()

    # ─────────────────────────────────────────────── Icon

    def _make_icon_card(self, parent, size: int = 56):
        """Render brand icon card at the given square size.

        Base proportions are calibrated at size=56 ('j' font 32, strip
        11×22 at place(33,17)). All values scale linearly with the
        size/56 ratio so the same visual identity holds at 56, 80, etc.
        Derived from assets/brand/icon-04E.svg (256×256 viewBox).
        """
        ratio = size / 56
        radius = int(10 * ratio)
        j_font = int(32 * ratio)
        j_x = int(10 * ratio)
        j_y = int(4 * ratio)
        strip_x = int(33 * ratio)
        strip_y = int(17 * ratio)
        strip_w = int(11 * ratio)
        strip_h = int(22 * ratio)

        card = ctk.CTkFrame(
            parent, width=size, height=size,
            corner_radius=radius, fg_color=self.ICON_BG,
        )
        card.pack_propagate(False)

        # "j" character — top-left positioned, scaled font
        ctk.CTkLabel(
            card, text="j",
            font=("Consolas", j_font, "bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        ).place(x=j_x, y=j_y)

        # Magenta cursor strip
        ctk.CTkFrame(
            card, width=strip_w, height=strip_h,
            corner_radius=0, fg_color=self.ACCENT_COLOR,
        ).place(x=strip_x, y=strip_y)

        return card

    # ─────────────────────────────────────────────── Progress animation

    def _start_progress(self):
        step_ms = self.PROGRESS_MS // self.PROGRESS_STEPS
        self._animate_progress(0, step_ms)

    def _animate_progress(self, step: int, step_ms: int):
        if step > self.PROGRESS_STEPS:
            return
        self._progress.set(step / self.PROGRESS_STEPS)
        if step < self.PROGRESS_STEPS:
            self._after_id = self.after(
                step_ms, self._animate_progress, step + 1, step_ms,
            )

    def destroy(self):
        """Cancel pending animation timer before tearing down the window."""
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()
