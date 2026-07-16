"""Pure detection of import-vs-manual conflicts.

A conflict = an incoming import row whose (no_staff, tanggal) matches an
existing MANUAL-edited row AND at least one watched field differs. Rows
without a manual match never conflict — they import silently as before. The
caller passes `existing_manual` already filtered to manual-edited rows (see
db.attendance.manual_rows_for_import), keeping this module free of I/O.
See spec §7.1.
"""
CONFLICT_FIELDS = ("tipe", "jadwal", "masuk", "keluar",
                   "kerja_jam", "lembur_jam", "terlambat_menit")


def _differ(a, b):
    """True when a and b are meaningfully different. Treats None and '' alike,
    and compares numbers numerically (8 == 8.0, '8.1' == 8.1)."""
    if a is None and b is None:
        return False
    try:
        if a is not None and b is not None and float(a) == float(b):
            return False
    except (TypeError, ValueError):
        pass
    return (a if a not in ("", None) else None) != (b if b not in ("", None) else None)


def find_conflicts(pending_rows, existing_manual):
    """Return a list of conflict dicts (one per clashing row).

    pending_rows: objects with attributes no_staff, tanggal, hari + CONFLICT_FIELDS.
    existing_manual: {(no_staff, tanggal): {nama, <CONFLICT_FIELDS...>}} — already
        limited to manual-edited rows.

    Each conflict: {key, no_staff, nama, tanggal, hari, manual, incoming, changed}.
    """
    out = []
    for r in pending_rows:
        key = (r.no_staff, r.tanggal)
        ex = existing_manual.get(key)
        if not ex:
            continue
        changed = [f for f in CONFLICT_FIELDS if _differ(getattr(r, f, None), ex.get(f))]
        if not changed:
            continue
        out.append({
            "key": key,
            "no_staff": r.no_staff,
            "nama": ex.get("nama"),
            "tanggal": r.tanggal,
            "hari": getattr(r, "hari", None),
            "manual": {f: ex.get(f) for f in CONFLICT_FIELDS},
            "incoming": {f: getattr(r, f, None) for f in CONFLICT_FIELDS},
            "changed": changed,
        })
    return out
