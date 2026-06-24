"""Tests for src.core.session_state — ephemeral cross-screen UI state."""
from src.core.session_state import SessionPeriodState, period_state


def test_default_is_semua():
    s = SessionPeriodState()
    assert s.get() == "semua"


def test_set_and_get_roundtrip():
    s = SessionPeriodState()
    s.set("minggu_3")
    assert s.get() == "minggu_3"


def test_reset_returns_to_semua():
    s = SessionPeriodState()
    s.set("minggu_2")
    s.reset()
    assert s.get() == "semua"


def test_empty_set_is_ignored():
    """Defensive: empty key should be a no-op, not corrupt state."""
    s = SessionPeriodState()
    s.set("minggu_4")
    s.set("")
    assert s.get() == "minggu_4"


def test_module_singleton_exists():
    """The module-level `period_state` is the shared instance used by screens."""
    assert isinstance(period_state, SessionPeriodState)


from src.core.session_state import (
    SessionDataVersion, data_version, notify_data_changed,
)


def test_data_version_starts_at_zero():
    v = SessionDataVersion()
    assert v.get() == 0


def test_data_version_bump_increments():
    v = SessionDataVersion()
    v.bump()
    v.bump()
    assert v.get() == 2


def test_data_version_reset_zeroes():
    v = SessionDataVersion()
    v.bump()
    v.reset()
    assert v.get() == 0


def test_notify_data_changed_bumps_singleton():
    before = data_version.get()
    notify_data_changed()
    assert data_version.get() == before + 1


def test_data_version_module_singleton_type():
    assert isinstance(data_version, SessionDataVersion)
