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
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(expand=True, fill="both", padx=50, pady=40)

        # ── TOP ROW: icon card + app name/version stack ──
        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(anchor="w", pady=(0, 24))

        icon = self._make_icon_card(top)
        icon.pack(side="left", padx=(0, 16))

        text_col = ctk.CTkFrame(top, fg_color="transparent")
        text_col.pack(side="left", anchor="w")
        ctk.CTkLabel(
            text_col, text="HR Absensi",
            font=("Segoe UI", 22, "bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col, text=f"v{APP_VERSION}",
            font=("Consolas", 13, "bold"),
            text_color=self.ACCENT_COLOR,
            fg_color="transparent",
        ).pack(anchor="w")

        # ── TAGLINE ──
        ctk.CTkLabel(
            outer,
            text=f"// {APP_TAGLINE.rstrip('.').lower()}",
            font=("Consolas", 13),
            text_color=self.DIM_COLOR,
            fg_color="transparent",
        ).pack(anchor="w", pady=(0, 20))

        # ── STATUS TEXT ──
        ctk.CTkLabel(
            outer, text="Loading data & screens...",
            font=("Consolas", 11),
            text_color=self.DIMMER_COLOR,
            fg_color="transparent",
        ).pack(anchor="w", pady=(0, 8))

        # ── PROGRESS BAR (CTkProgressBar — clean native rendering) ──
        self._progress = ctk.CTkProgressBar(
            outer,
            height=6, corner_radius=3,
            progress_color=self.ACCENT_COLOR,
            fg_color=self.PROGRESS_BG,
        )
        self._progress.pack(fill="x", pady=(0, 24))
        self._progress.set(0)

        # ── BRAND CREDIT (right-aligned, below progress) ──
        ctk.CTkLabel(
            outer, text=APP_BRAND_NAME,
            font=("Consolas", 10),
            text_color=self.DIMMER_COLOR,
            fg_color="transparent",
        ).pack(anchor="e")

    # ─────────────────────────────────────────────── Icon

    def _make_icon_card(self, parent):
        """Render 56×56 brand icon card with 'j' glyph + magenta cursor strip.

        Proportions derived from assets/brand/icon-04E.svg (256×256 viewBox
        scaled by 56/256 ≈ 0.219×):
          - corner radius   56 × 0.219 ≈ 12  → use 10 (CTk visual)
          - 'j' font size   152 × 0.219 ≈ 33 → 32 (round)
          - magenta strip   x=142 y=78 w=56 h=108 → x≈31 y≈17 w≈12 h≈24
        """
        card = ctk.CTkFrame(
            parent, width=56, height=56,
            corner_radius=10, fg_color=self.ICON_BG,
        )
        card.pack_propagate(False)

        # "j" character — top-left positioned, scaled font
        ctk.CTkLabel(
            card, text="j",
            font=("Consolas", 32, "bold"),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        ).place(x=10, y=4)

        # Magenta cursor strip (small filled frame)
        ctk.CTkFrame(
            card, width=11, height=22,
            corner_radius=0, fg_color=self.ACCENT_COLOR,
        ).place(x=33, y=17)

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
