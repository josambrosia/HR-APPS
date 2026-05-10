import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.ui.components.kpi_card import KPICard
from src.ui.theme import COLOR_OK, COLOR_WARN, COLOR_ERR, FONT_FAMILY


class DashboardScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self):
        with get_connection(DB_PATH) as conn:
            month = get_setting(conn, "current_month", default="-")
            open_cnt = conn.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE has_issue=1 AND reason_category IS NULL"
            ).fetchone()[0]
            resolved_cnt = conn.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE has_issue=1 AND reason_category IS NOT NULL"
            ).fetchone()[0]
            na_cnt = conn.execute(
                "SELECT COUNT(*) FROM attendance_records WHERE reason_category='na'"
            ).fetchone()[0]
            last_import = conn.execute(
                "SELECT MAX(imported_at), imported_from FROM attendance_records"
            ).fetchone()
            last_import_text = (
                f"{last_import[1]} ({last_import[0][:10]})" if last_import[0] else "(belum ada impor)"
            )

        ctk.CTkLabel(self, text=f"Dashboard — {month}",
                     font=(FONT_FAMILY, 24, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 20))

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.grid(row=1, column=0, sticky="ew")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)

        KPICard(cards, "Resolved", str(resolved_cnt), value_color=COLOR_OK).grid(row=0, column=0, padx=4, sticky="ew")
        KPICard(cards, "Open", str(open_cnt), value_color=COLOR_WARN).grid(row=0, column=1, padx=4, sticky="ew")
        KPICard(cards, "NA", str(na_cnt), value_color=COLOR_ERR).grid(row=0, column=2, padx=4, sticky="ew")
        KPICard(cards, "Last Import", last_import_text).grid(row=0, column=3, padx=4, sticky="ew")
