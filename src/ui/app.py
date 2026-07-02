import customtkinter as ctk
from typing import Dict

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SIDEBAR, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_ACCENT_TINT_BG, COLOR_ACCENT_TINT_BORDER,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    COLOR_TEXT_SOFT,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    FONT_BODY, FONT_BODY_BOLD, FONT_LABEL,
    FONT_MONO_SMALL,
    RADIUS_MD,
)
from src.ui.icons import glyph, icon_font

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class HRApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HR Absensi App")
        self.geometry("1180x720")
        self.minsize(800, 540)  # smaller minsize triggers scrollbar earlier
        # Set window icon (taskbar + title bar)
        self._apply_brand_icon()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color=COLOR_BG)
        self.bind_all("<Return>", self._on_return_key)

        self._build_sidebar()
        self._build_content_area()
        # Screen instances are cached: built once on first visit, then
        # hidden/re-shown via grid_remove()/grid() so navigation is instant
        # and per-screen UI state (search query, scroll, picked file)
        # survives. Cached screens get .on_show() on every re-display to
        # re-read volatile data — see _show().
        self._screens: Dict[str, ctk.CTkFrame] = {}
        self._visible_name: str = ""
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

    def _apply_brand_icon(self):
        """Apply JTS brand icon via iconbitmap + iconphoto.

        iconphoto with default=True applies the icon as the default for
        all Toplevels (splash, dialogs, etc.) and survives withdraw/deiconify
        cycles better than iconbitmap alone on Windows. Both APIs are called
        for defense-in-depth — if one fails (e.g., PIL missing, file missing),
        the other may still succeed.
        """
        try:
            from src.config import BRAND_ICON_ICO
            self.iconbitmap(str(BRAND_ICON_ICO))
        except Exception:
            pass
        try:
            from src.config import BRAND_ICON_ICO
            from PIL import Image, ImageTk
            pil = Image.open(str(BRAND_ICON_ICO))
            photo = ImageTk.PhotoImage(pil)
            self.iconphoto(True, photo)
            # Keep reference to prevent GC — Tk doesn't hold one for iconphoto.
            self._brand_icon_ref = photo
        except Exception:
            pass

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0, fg_color=COLOR_SIDEBAR,
            border_width=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Header: JTS icon + "HR ABSENSI" wordmark + mono subtitle
        header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_frame.pack(pady=(SPACE_LG, SPACE_MD), fill="x", padx=SPACE_LG)
        self._load_sidebar_icon(header_frame)  # icon size 36

        title_stack = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_stack.pack(side="left", padx=(SPACE_SM, 0))
        ctk.CTkLabel(
            title_stack, text="HR ABSENSI",
            font=(FONT_FAMILY, 14, "bold"),
            text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_stack, text="attendance manager",
            font=FONT_MONO_SMALL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w")

        # ── Active month chip — clickable card with subtle magenta tint ──
        self._active_month_chip = ctk.CTkFrame(
            self.sidebar,
            fg_color=COLOR_ACCENT_TINT_BG,
            border_width=1,
            border_color=COLOR_ACCENT_TINT_BORDER,
            corner_radius=RADIUS_MD,
            cursor="hand2",
        )
        self._active_month_chip.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_MD))

        # Label "BULAN AKTIF" uppercase
        bulan_lbl = ctk.CTkLabel(
            self._active_month_chip,
            text="BULAN AKTIF",
            font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
        )
        bulan_lbl.pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, 0))

        # Value (active month display)
        self._active_month_label = ctk.CTkLabel(
            self._active_month_chip,
            text=self._format_active_month_label(),
            font=FONT_BODY_BOLD,
            text_color=COLOR_ACCENT_HOVER,  # lighter magenta for value text
            anchor="w",
        )
        self._active_month_label.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))

        # Make entire chip + children clickable
        def _on_chip_click(_e):
            self._show("ActiveMonth")

        for widget in (self._active_month_chip, self._active_month_label, bulan_lbl):
            widget.bind("<Button-1>", _on_chip_click)

        # ── Sections (label + items) — categorized navigation ──
        nav_groups = [
            ("INSIGHT", [
                ("📊", "Dashboard", "Dashboard"),
                ("⊞", "Heatmap", "Heatmap"),
            ]),
            ("DATA MANAGEMENT", [
                ("📥", "Import", "Import"),
                ("📤", "Export", "Export"),
                ("📆", "Active Month", "ActiveMonth"),
            ]),
            ("WORKFLOW", [
                ("🚩", "Issues", "Issues"),
                ("◷", "Severe Lateness", "SevereLateness"),
                ("💬", "WhatsApp Assistant", "WhatsAppAssistant"),
                ("🎯", "Coaching", "Coaching"),
            ]),
            ("EXCEPTIONAL CASE", [
                ("🔸", "Outlier", "Outlier"),
                ("🌴", "Hari Libur", "Holiday"),
            ]),
            ("SYSTEM", [
                ("⚙", "Settings", "Settings"),
                ("ℹ", "About", "About"),
            ]),
        ]

        self._nav_items: dict[str, ctk.CTkFrame] = {}
        self._active_nav_key: str = "Dashboard"  # default starting screen

        for group_label, items in nav_groups:
            # Section label
            ctk.CTkLabel(
                self.sidebar,
                text=group_label,
                font=FONT_LABEL,
                text_color=COLOR_TEXT_DISABLED,
                anchor="w",
            ).pack(fill="x", padx=SPACE_LG, pady=(SPACE_XS, 2))

            # Nav items in group
            for icon, label, screen_key in items:
                item = self._build_nav_item(icon, label, screen_key)
                item.pack(fill="x", pady=0)
                self._nav_items[screen_key] = item

        # ── Footer: brand row ("Josaphat Tech" + "Solution") + 1 mono line ──
        # Compact 2-line layout (version + tagline combined) to save sidebar height.
        from src.config import APP_VERSION, APP_TAGLINE, APP_BRAND_NAME

        # Split brand name into 2 lines on the last word for the stacked layout.
        # "Josaphat Tech Solution" → ["Josaphat Tech", "Solution"]
        brand_parts = APP_BRAND_NAME.rsplit(" ", 1)
        brand_line1 = brand_parts[0] if len(brand_parts) == 2 else APP_BRAND_NAME
        brand_line2 = brand_parts[1] if len(brand_parts) == 2 else ""

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=8, pady=(SPACE_SM, 10))

        sep = ctk.CTkFrame(footer, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", pady=(0, SPACE_SM))

        # Brand — single horizontal row: "Josaphat Tech" white + "Solution" magenta
        brand_row = ctk.CTkFrame(footer, fg_color="transparent")
        brand_row.pack(fill="x")
        ctk.CTkLabel(
            brand_row, text=brand_line1, font=(FONT_FAMILY, 12, "bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")
        if brand_line2:
            ctk.CTkLabel(
                brand_row, text=f" {brand_line2}",
                font=(FONT_FAMILY, 12, "bold"), text_color=COLOR_ACCENT,
            ).pack(side="left")

        # Version + tagline — single mono line
        ctk.CTkLabel(
            footer,
            text=f"v{APP_VERSION} · {APP_TAGLINE.rstrip('.').lower()}",
            font=("Consolas", 8), text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(fill="x", pady=(2, 0))

    def _build_nav_item(self, icon: str, label: str, screen_key: str) -> ctk.CTkFrame:
        """Custom nav item with active state indicator (3px magenta left bar).

        Frame layout: [left bar 3px] [icon + label content]
        State stored visually — when this item becomes active, left bar shows
        + bg tints. Click handled by binding on the entire frame.
        """
        frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=32)
        frame.pack_propagate(False)

        # Left active bar — created hidden, shown when active
        left_bar = ctk.CTkFrame(
            frame, fg_color=COLOR_ACCENT, width=3, corner_radius=0,
        )
        # Pack hidden initially; activate via _set_active_nav_item

        # Inner content row; left bar (when active) packs to left via before=new._content
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=SPACE_LG)

        # Prefer a monochrome Segoe Fluent Icons glyph; fall back to the emoji
        # passed in nav_groups if the icon font / glyph is unavailable.
        _g = glyph(screen_key)
        icon_lbl = ctk.CTkLabel(
            content, text=(_g or icon),
            font=((icon_font(), 16) if _g else FONT_BODY),
            text_color=COLOR_TEXT_DIM, anchor="w", width=22,
        )
        icon_lbl.pack(side="left")

        text_lbl = ctk.CTkLabel(
            content, text=label, font=FONT_BODY,
            text_color=COLOR_TEXT_SOFT, anchor="w",
        )
        text_lbl.pack(side="left", padx=(SPACE_SM, 0))

        # Store refs on frame for state updates
        frame._left_bar = left_bar
        frame._content = content
        frame._icon_lbl = icon_lbl
        frame._text_lbl = text_lbl
        frame._screen_key = screen_key

        # Click handler (bind on frame + children to catch all)
        def _on_click(_e):
            self._show(screen_key)

        for widget in (frame, content, icon_lbl, text_lbl):
            widget.bind("<Button-1>", _on_click)
            widget.configure(cursor="hand2")

        # Hover handlers
        def _on_enter(_e):
            if frame._screen_key != self._active_nav_key:
                frame.configure(fg_color=COLOR_SURFACE)

        def _on_leave(_e):
            if frame._screen_key != self._active_nav_key:
                frame.configure(fg_color="transparent")

        for widget in (frame, content, icon_lbl, text_lbl):
            widget.bind("<Enter>", _on_enter)
            widget.bind("<Leave>", _on_leave)

        return frame

    def _set_active_nav_item(self, screen_key: str):
        """Toggle visual active state on nav items.

        Show left magenta bar + bg tint + bold text on newly active item.
        Hide indicators on previously active item.
        """
        # Idempotent: no-op if already active (Important #2)
        if screen_key == self._active_nav_key and screen_key in self._nav_items:
            # Still re-apply visuals in case this is first activation after init
            new = self._nav_items[screen_key]
            new.configure(fg_color=COLOR_SURFACE_HIGH)
            if not new._left_bar.winfo_ismapped():
                new._left_bar.pack(side="left", fill="y", pady=SPACE_XS, before=new._content)
            new._text_lbl.configure(text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
            new._icon_lbl.configure(text_color=COLOR_ACCENT)
            return

        prev = self._nav_items.get(self._active_nav_key)
        if prev is not None:
            prev.configure(fg_color="transparent")
            prev._left_bar.pack_forget()
            prev._text_lbl.configure(text_color=COLOR_TEXT_SOFT, font=FONT_BODY)
            prev._icon_lbl.configure(text_color=COLOR_TEXT_DIM)

        new = self._nav_items.get(screen_key)
        if new is not None:
            new.configure(fg_color=COLOR_SURFACE_HIGH)
            # before=new._content ensures bar packs to the LEFT of content
            # (without this, pack manager appends bar to end of slave list)
            new._left_bar.pack(side="left", fill="y", pady=SPACE_XS, before=new._content)
            new._text_lbl.configure(text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
            new._icon_lbl.configure(text_color=COLOR_ACCENT)
            self._active_nav_key = screen_key

    def _load_sidebar_icon(self, parent):
        """Render a JTS icon (36x36) at the start of the sidebar header.

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
                    output_width=64, output_height=64,
                )
                pil = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
                pil = pil.resize((36, 36), Image.LANCZOS)
            except Exception:
                # Fallback: use the .ico file (multi-res) at 36px via PIL
                from src.config import BRAND_ICON_ICO
                pil = Image.open(str(BRAND_ICON_ICO))
                pil = pil.resize((36, 36), Image.LANCZOS).convert("RGBA")
            ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(36, 36))
            ctk.CTkLabel(parent, image=ctk_img, text="").pack(side="left")
            # Keep reference so image isn't garbage collected
            self._sidebar_icon_ref = ctk_img
        except Exception:
            # Icon optional; sidebar still works without it
            pass

    def _build_content_area(self):
        # Regular frame — CTkScrollableFrame was breaking viewport-fill expansion
        # in screens with content smaller than viewport. Each individual screen
        # handles its own scrolling needs internally (Treeviews scroll, Active
        # Month uses CTkScrollableFrame for card list, WhatsApp uses one for
        # employee list). HRApp.minsize prevents too-small windows from clipping.
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def _format_active_month_label(self) -> str:
        """Return short-form active month for chip value display."""
        try:
            from src.config import DB_PATH
            from src.db.connection import get_connection
            from src.db.settings import get_setting
            from src.core.report_generator import month_label
            with get_connection(DB_PATH) as conn:
                ym = get_setting(conn, "current_month") or ""
            if ym:
                return f"◆ {month_label(ym)}"
            return "◆ Belum diset"
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

    def _create_screen(self, name: str) -> ctk.CTkFrame:
        """Construct (without gridding) the screen instance for `name`.

        Imports stay lazy inside each branch so startup only pays for the
        first screen actually shown."""
        if name == "Dashboard":
            from src.ui.screens.dashboard import DashboardScreen
            return DashboardScreen(self.content)
        elif name == "Heatmap":
            from src.ui.screens.heatmap import HeatmapScreen
            return HeatmapScreen(self.content)
        elif name == "Import":
            from src.ui.screens.import_screen import ImportScreen
            return ImportScreen(self.content)
        elif name == "Issues":
            from src.ui.screens.issues import IssuesScreen
            return IssuesScreen(self.content)
        elif name == "SevereLateness":
            from src.ui.screens.severe_lateness import SevereLatenessScreen
            return SevereLatenessScreen(self.content)
        elif name == "WhatsAppAssistant":
            from src.ui.screens.whatsapp_assistant import WhatsAppAssistantScreen
            return WhatsAppAssistantScreen(self.content)
        elif name == "Export":
            from src.ui.screens.export import ExportScreen
            return ExportScreen(self.content)
        elif name == "ActiveMonth":
            from src.ui.screens.active_month import ActiveMonthScreen
            return ActiveMonthScreen(self.content)
        elif name == "Coaching":
            from src.ui.screens.coaching import CoachingScreen
            return CoachingScreen(self.content)
        elif name == "Outlier":
            from src.ui.screens.outlier import OutlierScreen
            return OutlierScreen(self.content)
        elif name == "Holiday":
            from src.ui.screens.holiday import HolidayScreen
            return HolidayScreen(self.content)
        elif name == "Settings":
            from src.ui.screens.settings import SettingsScreen
            return SettingsScreen(self.content)
        # Placeholder for unknown names (defensive; nav never sends these).
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        ctk.CTkLabel(frame, text=name, font=(FONT_FAMILY, 28, "bold")).pack(pady=40)
        ctk.CTkLabel(frame, text=f"Screen '{name}' — to be implemented in next tasks.",
                     font=(FONT_FAMILY, 13)).pack()
        return frame

    def _show(self, name: str):
        # Dialogs open as overlays without navigating away from the current screen.
        if name == "About":
            self._show_about()
            return
        # Refresh sidebar active-month indicator on every navigation
        self._refresh_active_month_label()
        # Update sidebar nav visual state
        self._set_active_nav_item(name)

        screen = self._screens.get(name)
        if screen is not None and not screen.winfo_exists():
            screen = None  # defensive: stale entry (should not happen)

        # Hide the currently visible screen. grid_remove (not destroy)
        # keeps the instance + its grid options for instant re-show.
        prev = self._screens.get(self._visible_name)
        if prev is not None and prev is not screen and prev.winfo_exists():
            prev.grid_remove()

        if screen is None:
            # First visit — build fresh. __init__ already renders current
            # data, so on_show() is NOT called here (see contract below).
            screen = self._create_screen(name)
            self._screens[name] = screen
            screen.grid(row=0, column=0, sticky="nsew")
        else:
            # Cached — re-show, then let the screen re-read volatile data.
            # on_show() contract: fast + idempotent; re-reads current_month/
            # settings/period_state and refreshes rows WITHOUT rebuilding
            # its chrome, so user state (search, scroll, picks) survives.
            screen.grid()
            on_show = getattr(screen, "on_show", None)
            if callable(on_show):
                on_show()
        self._visible_name = name

    def _show_about(self):
        from src.ui.dialogs.about_dialog import AboutDialog
        AboutDialog(self)
