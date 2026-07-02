"""Severe Lateness screen — Hari Kerja rows with both punches present and
terlambat_menit >= threshold (Pengaturan).

Twin of IssuesScreen: all shared structure/behavior lives in
ResolveScreenBase; this module supplies only the severe-specific knobs
(threshold-filtered data source, category subset, Telat column).
"""
import customtkinter as ctk

from src.config import DB_PATH, SEVERE_LATENESS_CATEGORIES
from src.db.settings import read_severe_lateness_threshold
from src.db.attendance import (
    list_severe_lateness_for_period, count_severe_lateness_for_period,
)
from src.core.session_state import notify_data_changed
from src.core.reason_mapper import REASON_LABELS
from src.ui.screens.resolve_base import ResolveScreenBase
from src.ui.theme import COLOR_TEXT_MUTED, FONT_BODY, SPACE_LG


class SevereLatenessScreen(ResolveScreenBase):
    TITLE = "Severe Lateness"
    EXTRA_COLUMNS = (("terlambat", "Telat (mnt)", 80, True),)

    # Late-bound module globals — tests monkeypatch these on THIS module.

    def _db_path(self):
        return DB_PATH

    def _notify_data_changed(self):
        notify_data_changed()

    # Data source: threshold-filtered severe-lateness rows.

    def _load_extra_settings(self, conn):
        self._threshold = read_severe_lateness_threshold(conn)

    def _count_rows(self, conn, start, end):
        return count_severe_lateness_for_period(conn, start, end, self._threshold)

    def _list_rows(self, conn, start, end, *, resolved):
        return list_severe_lateness_for_period(
            conn, start, end, self._threshold, resolved=resolved)

    def _category_labels(self):
        return [REASON_LABELS[c] for c in SEVERE_LATENESS_CATEGORIES]

    def _batch_lister_fn(self):
        return lambda conn, s, e: list_severe_lateness_for_period(
            conn, s, e, self._threshold, resolved=False)

    def _resolution_rate(self, counts):
        # Compute resolution rate locally from the count dict. (The shared
        # insights.resolution_rate is hardcoded to has_issue=1 and would be
        # wrong for this severe-lateness set, which has has_issue=0 rows.)
        total = counts["total"]
        rate = round(counts["resolved"] / total * 100) if total else 0
        return {"total": total, "rate_pct": rate}

    def _extra_row_values(self, row):
        telat = row["terlambat_menit"] if row["terlambat_menit"] is not None else "—"
        return (telat,)

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.right,
                     text="Pilih issue di kiri untuk input alasan",
                     font=FONT_BODY, text_color=COLOR_TEXT_MUTED
                     ).pack(pady=80, padx=SPACE_LG)
