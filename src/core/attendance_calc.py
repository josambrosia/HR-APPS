"""Pure recompute of derived attendance fields from raw punches + schedule.

No I/O. Given the raw ``masuk``/``keluar``/``tipe`` a user typed plus the
global work schedule, produce ``has_issue``, ``terlambat_menit``,
``kerja_jam``, ``lembur_jam`` — the four derived fields the rest of the app
reads. Mirrors the fingerprint machine's semantics closely enough; the
divergence risk (no break deduction) is covered by the dialog's manual
override. See spec §6.1 (D2/D8/D9).
"""
import re

# Accept both "HH:MM" (masuk/keluar) and "HH.MM" (schedule settings).
_TIME_RE = re.compile(r"^(\d{1,2})[:.](\d{2})$")


def to_minutes(s):
    """'08:15' -> 495, '08.00' -> 480. None/blank/garbage/out-of-range -> None."""
    if not s:
        return None
    m = _TIME_RE.match(str(s).strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def recompute(*, tipe, masuk, keluar, schedule_start, schedule_end):
    """Return {has_issue, terlambat_menit, kerja_jam, lembur_jam}.

    - has_issue: Hari Kerja with a missing punch (identik core.issue_detector).
    - terlambat_menit: raw minutes late vs schedule_start (Hari Kerja + masuk);
      tolerance is applied downstream, not here.
    - kerja_jam: (keluar - masuk) hours, no break deduction; clamped >= 0.
    - lembur_jam: (keluar - schedule_end) hours; clamped >= 0.
    """
    ms, ks = to_minutes(masuk), to_minutes(keluar)
    start = to_minutes(schedule_start) or 0
    end = to_minutes(schedule_end) or 0
    is_kerja = tipe == "Hari Kerja"

    has_issue = 1 if (is_kerja and (ms is None or ks is None)) else 0
    terlambat = max(0, ms - start) if (is_kerja and ms is not None) else 0
    kerja = round(max(0, ks - ms) / 60, 1) if (ms is not None and ks is not None) else 0.0
    lembur = round(max(0, ks - end) / 60, 1) if ks is not None else 0.0

    return {
        "has_issue": has_issue,
        "terlambat_menit": terlambat,
        "kerja_jam": kerja,
        "lembur_jam": lembur,
    }
