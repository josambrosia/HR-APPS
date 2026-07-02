"""Issues screen — resolve missing-punch issues (has_issue=1 rows).

All structure/behavior lives in ResolveScreenBase; this module supplies
only the Issues-specific knobs (data source, full reason-category list)
so the twin screens stay in sync by construction.
"""
from src.config import DB_PATH
from src.db.attendance import list_issues_for_period, count_issues_for_period
from src.core.session_state import notify_data_changed
from src.core.reason_mapper import REASON_LABELS
from src.ui.screens.resolve_base import ResolveScreenBase


class IssuesScreen(ResolveScreenBase):
    TITLE = "Issues"

    # Late-bound module globals — tests monkeypatch these on THIS module.

    def _db_path(self):
        return DB_PATH

    def _notify_data_changed(self):
        notify_data_changed()

    # Data source: has_issue=1 rows for the period.

    def _count_rows(self, conn, start, end):
        return count_issues_for_period(conn, start, end)

    def _list_rows(self, conn, start, end, *, resolved):
        return list_issues_for_period(conn, start, end, resolved=resolved)

    def _category_labels(self):
        return list(REASON_LABELS.values())

    # Resolution Rate uses the base default — the shared
    # insights.resolution_rate helper over the has_issue=1 population.
