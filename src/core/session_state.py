"""Session-only UI state shared across screens — does NOT persist to DB.

Currently holds the focused-week key. Could be extended with other
ephemeral cross-screen state in future versions (e.g., last-searched query).
"""


class SessionPeriodState:
    """Holds the user's currently-focused week key.

    Default 'semua' on app launch. Updated only by explicit user clicks
    in any screen's WeekNavBar — internal WeekNavBar fallbacks (when
    'semua' is requested on a screen with include_all=False) do NOT
    write to this state.
    """

    def __init__(self):
        self._week_key = "semua"

    def get(self) -> str:
        """Returns 'semua' or 'minggu_N' (N in 1..6 per month length)."""
        return self._week_key

    def set(self, key: str) -> None:
        if not key:
            return  # defensive: empty key ignored
        self._week_key = key

    def reset(self) -> None:
        """For test isolation. Production code should never call this."""
        self._week_key = "semua"


# Module-level singleton. One instance per app process.
period_state = SessionPeriodState()


class SessionDataVersion:
    """Monotonic counter bumped whenever issue/attendance analytics inputs
    change, so cached analytics views (Dashboard) can detect staleness and
    refetch. Session-only; never persisted."""

    def __init__(self):
        self._version = 0

    def get(self) -> int:
        return self._version

    def bump(self) -> None:
        self._version += 1

    def reset(self) -> None:
        """For test isolation. Production code should never call this."""
        self._version = 0


# Module-level singleton. One instance per app process.
data_version = SessionDataVersion()


def notify_data_changed() -> None:
    """Call after any write that changes issue/attendance analytics inputs
    (resolve, reopen, batch resolve, import). Bumps the shared data_version."""
    data_version.bump()
