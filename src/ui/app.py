import customtkinter as ctk
from typing import Dict

from src.ui.theme import FONT_FAMILY, COLOR_BG, COLOR_PANEL, COLOR_ACCENT, COLOR_TEXT, COLOR_TEXT_DIM

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class HRApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HR Absensi App")
        self.geometry("1180x720")
        self.minsize(800, 540)  # smaller minsize triggers scrollbar earlier
        # Set window icon (taskbar + title bar)
        try:
            from src.config import BRAND_ICON_ICO
            self.iconbitmap(str(BRAND_ICON_ICO))
        except Exception:
            pass  # icon optional; don't block app start

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color=COLOR_BG)
        self.bind_all("<Return>", self._on_return_key)

        self._build_sidebar()
        self._build_content_area()
        self._screens: Dict[str, ctk.CTkFrame] = {}
        self._show("Dashboard")

    def _on_return_key(self, event):
        """Walk up from the focused widget to find a CTkButton; invoke it."""
        widget = event.widget
        current = widget
        # Walk up to find a CTkButton
        while current is not None:
            if isinstance(current, ctk.CTkButton):
                current.invoke()
                return "break"
            current = getattr(current, "master", None)
        return None

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=COLOR_PANEL)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Header: small JTS icon + "HR ABSENSI" wordmark
        header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_frame.pack(pady=(20, 10), fill="x", padx=8)
        self._load_sidebar_icon(header_frame)
        ctk.CTkLabel(header_frame, text="HR ABSENSI",
                     font=(FONT_FAMILY, 16, "bold")
                     ).pack(side="left", padx=(4, 0))

        # ── Active month indicator (clickable shortcut to Riwayat Bulan) ──
        # Subtle magenta line under the header. User can see active month
        # at a glance from any screen, no need to open Riwayat Bulan menu.
        self._active_month_label = ctk.CTkLabel(
            self.sidebar,
            text=self._format_active_month_label(),
            font=(FONT_FAMILY, 11, "bold"),
            text_color="#EC4899",   # brand magenta
            anchor="w",
            cursor="hand2",
        )
        self._active_month_label.pack(fill="x", padx=12, pady=(0, 8))
        self._active_month_label.bind(
            "<Button-1>", lambda _e: self._show("Months"),
        )

        nav_items = [
            ("📊 Dashboard", "Dashboard"),
            ("📥 Import", "Import"),
            ("⚠ Issues", "Issues"),
            ("📋 Summary", "Summary"),
            ("📤 Export", "Export"),
            ("🗓 Riwayat Bulan", "Months"),
            ("🎯 Coaching", "Coaching"),
            ("⚙ Settings", "Settings"),
        ]
        for label, screen in nav_items:
            ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                command=lambda s=screen: self._show(s),
                fg_color="transparent", hover_color="#334155",
            ).pack(fill="x", padx=8, pady=2)

        # ── Footer: BRAND stacked emphasis + version + tagline ──
        # SB2 mockup: "Josaphat Tech" (white bold) / "Solution" (magenta bold)
        # → version mono / tagline mono. Brand readable at glance.
        from src.config import APP_VERSION, APP_TAGLINE, APP_BRAND_NAME
        from src.ui.theme import COLOR_TEXT

        # Brand magenta is the JTS accent (#EC4899) — NOT app's COLOR_ACCENT
        # which is orange. Hardcoded here to keep the brand link explicit
        # (hybrid theme approach: app=purple/orange, brand-marks=magenta).
        BRAND_MAGENTA = "#EC4899"

        # Split brand name into 2 lines on the last word for the stacked layout.
        # "Josaphat Tech Solution" → ["Josaphat Tech", "Solution"]
        brand_parts = APP_BRAND_NAME.rsplit(" ", 1)
        brand_line1 = brand_parts[0] if len(brand_parts) == 2 else APP_BRAND_NAME
        brand_line2 = brand_parts[1] if len(brand_parts) == 2 else ""

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=8, pady=(10, 14))

        # Thin separator above the footer block
        sep = ctk.CTkFrame(footer, fg_color=COLOR_TEXT_DIM, height=1)
        sep.pack(fill="x", pady=(0, 10))

        # Brand line 1: "Josaphat Tech" — white bold
        ctk.CTkLabel(
            footer, text=brand_line1,
            font=(FONT_FAMILY, 13, "bold"),
            text_color=COLOR_TEXT, anchor="w",
        ).pack(fill="x")

        # Brand line 2: "Solution" — magenta bold (visual accent)
        if brand_line2:
            ctk.CTkLabel(
                footer, text=brand_line2,
                font=(FONT_FAMILY, 13, "bold"),
                text_color=BRAND_MAGENTA, anchor="w",
            ).pack(fill="x", pady=(0, 6))

        # Version (mono, dim)
        ctk.CTkLabel(
            footer, text=f"v{APP_VERSION}",
            font=("Consolas", 10),
            text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(fill="x")

        # Tagline (mono, dim, smaller)
        ctk.CTkLabel(
            footer,
            text=f"// {APP_TAGLINE.rstrip('.').lower()}",
            font=("Consolas", 8),
            text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(fill="x")

    def _load_sidebar_icon(self, parent):
        """Render a small JTS icon (32x32) at the start of the sidebar header.

        Tries cairosvg first (cleanest rasterization from the SVG), falls
        back to loading the .ico file directly via Pillow.
        """
        try:
            from src.config import BRAND_ICON_SVG
            from PIL import Image
            import io
            try:
                import cairosvg
                png_bytes = cairosvg.svg2png(
                    url=str(BRAND_ICON_SVG),
                    output_width=32, output_height=32,
                )
                pil = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            except Exception:
                # Fallback: use the .ico file (multi-res) at 32px via PIL
                from src.config import BRAND_ICON_ICO
                pil = Image.open(str(BRAND_ICON_ICO))
                pil = pil.resize((32, 32), Image.LANCZOS).convert("RGBA")
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(32, 32))
            ctk.CTkLabel(parent, image=ctk_img, text="").pack(side="left")
            # Keep reference so image isn't garbage collected
            self._sidebar_icon_ref = ctk_img
        except Exception:
            # Icon optional; sidebar still works without it
            pass

    def _build_content_area(self):
        # Outer scrollable container — kicks in when window shrinks below content
        self._content_outer = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._content_outer.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        # Inner content area where screens grid into; preserves existing API
        self.content = ctk.CTkFrame(self._content_outer, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=20)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def _format_active_month_label(self) -> str:
        """Read current_month from DB, return '◆ Aktif: April 2026' or
        a 'no month yet' fallback. Safe to call before DB is initialized
        (returns empty string on any failure)."""
        try:
            from src.config import DB_PATH
            from src.db.connection import get_connection
            from src.db.settings import get_setting
            from src.core.report_generator import month_label
            with get_connection(DB_PATH) as conn:
                ym = get_setting(conn, "current_month") or ""
            if ym:
                return f"◆ Aktif: {month_label(ym)}"
            return "◆ Belum ada bulan aktif"
        except Exception:
            return ""

    def _refresh_active_month_label(self):
        """Re-read the active month from DB and update the sidebar label.
        Called from _show() so navigation away from a screen that changed
        current_month (e.g., Import auto-detect, Riwayat Bulan Pilih)
        reflects the new value immediately."""
        if hasattr(self, "_active_month_label"):
            try:
                self._active_month_label.configure(
                    text=self._format_active_month_label(),
                )
            except Exception:
                pass

    def _show(self, name: str):
        # Refresh sidebar active-month indicator on every navigation
        self._refresh_active_month_label()
        # Clear current content
        for child in self.content.winfo_children():
            child.destroy()
        if name == "Dashboard":
            from src.ui.screens.dashboard import DashboardScreen
            DashboardScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Import":
            from src.ui.screens.import_screen import ImportScreen
            ImportScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Issues":
            from src.ui.screens.issues import IssuesScreen
            IssuesScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Summary":
            from src.ui.screens.summary import SummaryScreen
            SummaryScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Export":
            from src.ui.screens.export import ExportScreen
            ExportScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Months":
            from src.ui.screens.months import MonthsScreen
            MonthsScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Coaching":
            from src.ui.screens.coaching import CoachingScreen
            CoachingScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Settings":
            from src.ui.screens.settings import SettingsScreen
            SettingsScreen(self.content).grid(row=0, column=0, sticky="nsew")
        else:
            # placeholder for other screens (will be replaced in next tasks)
            frame = ctk.CTkFrame(self.content, fg_color="transparent")
            frame.grid(row=0, column=0, sticky="nsew")
            ctk.CTkLabel(frame, text=name, font=(FONT_FAMILY, 28, "bold")).pack(pady=40)
            ctk.CTkLabel(frame, text=f"Screen '{name}' — to be implemented in next tasks.",
                         font=(FONT_FAMILY, 13)).pack()
