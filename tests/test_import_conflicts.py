from types import SimpleNamespace

from src.core.import_conflicts import find_conflicts


def _row(**kw):
    base = dict(no_staff="S1", tanggal="2026-05-06", hari="Rabu",
                tipe="Hari Kerja", jadwal="", masuk="08:00", keluar=None,
                kerja_jam=0.0, lembur_jam=0.0, terlambat_menit=0)
    base.update(kw)
    return SimpleNamespace(**base)


def _manual(**kw):
    base = dict(nama="Budi", tipe="Hari Kerja", jadwal="", masuk="08:00",
                keluar="16:05", kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0)
    base.update(kw)
    return base


def test_conflict_when_manual_row_differs():
    pending = [_row(keluar=None)]
    existing = {("S1", "2026-05-06"): _manual(keluar="16:05")}
    c = find_conflicts(pending, existing)
    assert len(c) == 1
    assert "keluar" in c[0]["changed"]
    assert c[0]["nama"] == "Budi"
    assert c[0]["key"] == ("S1", "2026-05-06")


def test_no_conflict_when_identical():
    pending = [_row(keluar="16:05", kerja_jam=8.1, lembur_jam=0.1)]
    existing = {("S1", "2026-05-06"): _manual()}
    assert find_conflicts(pending, existing) == []


def test_numeric_equality_ignores_type():
    # incoming ints vs stored floats must not register as a change
    pending = [_row(keluar="16:00", kerja_jam=8, lembur_jam=0, terlambat_menit=0)]
    existing = {("S1", "2026-05-06"): _manual(keluar="16:00", kerja_jam=8.0,
                                              lembur_jam=0.0, terlambat_menit=0)}
    assert find_conflicts(pending, existing) == []


def test_no_conflict_when_not_manual():
    assert find_conflicts([_row()], {}) == []          # nothing manual -> silent import


def test_only_flagged_row_conflicts_among_many():
    pending = [_row(no_staff="S1", tanggal="2026-05-06", keluar=None),
               _row(no_staff="S2", tanggal="2026-05-06", keluar="16:00")]
    existing = {("S1", "2026-05-06"): _manual(keluar="16:05")}   # only S1 is manual
    c = find_conflicts(pending, existing)
    assert [x["no_staff"] for x in c] == ["S1"]
