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
        self.minsize(1024, 640)

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

        ctk.CTkLabel(self.sidebar, text="HR ABSENSI",
                     font=(FONT_FAMILY, 16, "bold")).pack(pady=(20, 10))

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

    def _build_content_area(self):
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

    def _show(self, name: str):
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
