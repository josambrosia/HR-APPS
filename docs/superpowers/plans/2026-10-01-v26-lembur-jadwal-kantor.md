# v26.0.0 — Jam Kantor Berjadwal + Lembur: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ganti jam kantor ke 09.00–17.00 dengan riwayat berlaku per tanggal (cutoff 14 Sep 2026) dan tambah menu "Lembur" dengan deteksi otomatis + alur verifikasi Open → Diajukan → Diterima/Tidak Diterima.

**Architecture:** Tabel baru `schedule_periods` (jadwal effective-dated) dan `overtime_decisions` (keputusan, snapshot jam saat diputus). Deteksi lembur dihitung ulang saat baca dari `attendance_records` + jadwal tanggal itu; semua titik hardcode 08:00/16:00 diganti resolver `schedule_for(conn, tanggal)`. UI mengikuti pola v22/v25 (screen cache + `on_show`, `run_bg`/`BusyGuard`, search debounce, motion tokens).

**Tech Stack:** Python 3.x, customtkinter, SQLite, Jinja2, pytest, openpyxl.

Spec: `docs/superpowers/specs/2026-10-01-v26-lembur-jadwal-kantor-design.md`

---

### Task 1: Config + skema + migrasi jadwal

**Files:**
- Modify: `src/config.py` (defaults ~line 449-455)
- Modify: `src/db/schema.py` (DDL, DEFAULT_SETTINGS, `_migrate`)
- Test: `tests/test_schema.py` (update A1/A2 + tambah migrasi), `tests/test_settings_repo.py`

- [ ] **Step 1: Tulis tes yang gagal** — tambah di `tests/test_schema.py`:

```python
def test_init_db_seeds_new_schedule_defaults(temp_db_path):
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    assert rows["schedule_start"] == "09.00"
    assert rows["schedule_end"] == "17.00"
    assert rows["overtime_threshold"] == "18.00"

def test_init_db_seeds_single_period_for_fresh_db(temp_db_path):
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = conn.execute(
            "SELECT effective_from, start_time, end_time FROM schedule_periods"
        ).fetchall()
    assert rows == [("1970-01-01", "09.00", "17.00")]

def test_migrate_legacy_schedule_creates_cutover_periods(temp_db_path):
    # DB lama: settings 08.00/16.00 tanpa tabel riwayat
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('schedule_start','08.00')")
        conn.execute("INSERT INTO settings VALUES ('schedule_end','16.00')")
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = conn.execute(
            "SELECT effective_from, start_time, end_time FROM schedule_periods "
            "ORDER BY effective_from"
        ).fetchall()
    assert rows == [
        ("1970-01-01", "08.00", "16.00"),
        ("2026-09-14", "09.00", "17.00"),
    ]

def test_migrate_custom_schedule_preserved(temp_db_path):
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('schedule_start','08.30')")
        conn.execute("INSERT INTO settings VALUES ('schedule_end','16.30')")
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = conn.execute(
            "SELECT effective_from, start_time, end_time FROM schedule_periods"
        ).fetchall()
    assert rows == [("1970-01-01", "08.30", "16.30")]

def test_schedule_migration_idempotent(temp_db_path):
    init_db(temp_db_path)
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        n = conn.execute("SELECT COUNT(*) FROM schedule_periods").fetchone()[0]
    assert n == 1
```

Perbarui `test_init_db_seeds_default_settings` ke nilai baru (09.00/17.00) dan `tests/test_settings_repo.py::test_get_default_settings`.

- [ ] **Step 2: Jalankan, pastikan gagal** — `.venv\Scripts\python.exe -m pytest tests/test_schema.py tests/test_settings_repo.py -q` → FAIL (`no such table: schedule_periods`).

- [ ] **Step 3: Implementasi**

`src/config.py` (ganti blok defaults):

```python
# Defaults
DEFAULT_SCHEDULE_START = "09.00"
DEFAULT_SCHEDULE_END = "17.00"
DEFAULT_OVERTIME_THRESHOLD = "18.00"
OLD_SCHEDULE_START = "08.00"
OLD_SCHEDULE_END = "16.00"
SCHEDULE_CUTOVER_DATE = "2026-09-14"
DEFAULT_COACHING_THRESHOLD_PER_DAY = 15
DEFAULT_LUPA_PENALTY_MIN = 15
DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN = 60
DEFAULT_LATE_TOLERANCE_MIN = 12
```

`src/db/schema.py` — tambah ke `DDL`:

```sql
CREATE TABLE IF NOT EXISTS schedule_periods (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from TEXT NOT NULL UNIQUE,
    start_time     TEXT NOT NULL,
    end_time       TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS overtime_decisions (
    employee_id   INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    tanggal       TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    approved_minutes INTEGER,
    detected_minutes_at_decision INTEGER,
    note          TEXT,
    submitted_at  TEXT,
    decided_at    TEXT,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (employee_id, tanggal)
);

CREATE INDEX IF NOT EXISTS idx_overtime_tanggal ON overtime_decisions(tanggal);
```

`DEFAULT_SETTINGS` → `"schedule_start": "09.00"`, `"schedule_end": "17.00"`, plus `"overtime_threshold": "18.00"`.

Di `_migrate(conn)`, di akhir fungsi:

```python
    # v26: seed riwayat jadwal dari setelan tunggal. Fresh DB (belum ada
    # settings) memakai default baru; DB lama default 08.00/16.00 dipecah
    # pada cutoff 14 Sep 2026; nilai custom dipertahankan apa adanya.
    has_period = conn.execute(
        "SELECT 1 FROM schedule_periods LIMIT 1").fetchone()
    if has_period is None:
        from src.config import (
            DEFAULT_SCHEDULE_START, DEFAULT_SCHEDULE_END,
            OLD_SCHEDULE_START, OLD_SCHEDULE_END, SCHEDULE_CUTOVER_DATE)
        srow = conn.execute(
            "SELECT value FROM settings WHERE key='schedule_start'").fetchone()
        erow = conn.execute(
            "SELECT value FROM settings WHERE key='schedule_end'").fetchone()
        start = srow[0] if srow else DEFAULT_SCHEDULE_START
        end = erow[0] if erow else DEFAULT_SCHEDULE_END
        now = datetime.now(UTC).isoformat(timespec="seconds")
        if (start, end) == (OLD_SCHEDULE_START, OLD_SCHEDULE_END):
            conn.executemany(
                "INSERT INTO schedule_periods "
                "(effective_from, start_time, end_time, created_at) VALUES (?,?,?,?)",
                [("1970-01-01", OLD_SCHEDULE_START, OLD_SCHEDULE_END, now),
                 (SCHEDULE_CUTOVER_DATE, DEFAULT_SCHEDULE_START,
                  DEFAULT_SCHEDULE_END, now)])
        else:
            conn.execute(
                "INSERT INTO schedule_periods "
                "(effective_from, start_time, end_time, created_at) VALUES (?,?,?,?)",
                ("1970-01-01", start, end, now))
```

Tambah import `from datetime import UTC, datetime` di `schema.py`.

- [ ] **Step 4: Jalankan tes** → PASS. Lalu `.venv\Scripts\python.exe -m pytest tests/test_schema.py tests/test_settings_repo.py -q`.
- [ ] **Step 5: Commit** — `git add src/config.py src/db/schema.py tests/test_schema.py tests/test_settings_repo.py && git commit -m "feat(v26): skema jadwal berjadwal + keputusan lembur + migrasi cutoff"`

---

### Task 2: `src/db/schedule.py` + `src/core/schedule.py`

**Files:**
- Create: `src/db/schedule.py`, `src/core/schedule.py`
- Test: `tests/test_schedule.py`

- [ ] **Step 1: Tes gagal**

```python
import pytest
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.schedule import add_period, current_schedule, list_periods, schedule_for
from src.core.schedule import validate_period

def _db(tmp_path):
    p = tmp_path / "s.db"; init_db(p); return p

def test_schedule_for_boundaries(tmp_path):
    p = _db(tmp_path)
    with get_connection(p) as conn:
        add_period(conn, effective_from="2026-09-14", start="09.00", end="17.00")
        assert schedule_for(conn, "2026-09-13") == ("09.00", "17.00")   # fresh DB period
        assert schedule_for(conn, "2026-09-14") == ("09.00", "17.00")

def test_legacy_then_cutover(tmp_path):
    p = tmp_path / "s.db"
    with sqlite3.connect(p) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('schedule_start','08.00')")
        conn.execute("INSERT INTO settings VALUES ('schedule_end','16.00')")
        conn.commit()
    init_db(p)
    with get_connection(p) as conn:
        assert schedule_for(conn, "2026-09-13") == ("08.00", "16.00")
        assert schedule_for(conn, "2026-09-14") == ("09.00", "17.00")

def test_add_period_mirrors_settings(tmp_path):
    p = _db(tmp_path)
    with get_connection(p) as conn:
        add_period(conn, effective_from="2026-10-01", start="10.00", end="18.00")
        assert current_schedule(conn) == ("10.00", "18.00")
        from src.db.settings import get_setting
        assert get_setting(conn, "schedule_start") == "10.00"

def test_validate_period_rejects_bad_input():
    assert validate_period("2026-10-01", "17.00", "09.00") is not None
    assert validate_period("bukan-tanggal", "09.00", "17.00") is not None
    assert validate_period("2026-10-01", "09.00", "17.00") is None
```

- [ ] **Step 2: Jalankan → gagal (module not found).**
- [ ] **Step 3: Implementasi**

`src/db/schedule.py`:

```python
"""Data access for effective-dated work schedules (v26)."""
import sqlite3
from datetime import UTC, datetime

from src.config import DEFAULT_SCHEDULE_END, DEFAULT_SCHEDULE_START
from src.db.settings import set_setting


def list_periods(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, effective_from, start_time, end_time, created_at "
        "FROM schedule_periods ORDER BY effective_from ASC").fetchall()
    return [dict(r) for r in rows]


def schedule_for(conn, tanggal: str) -> tuple[str, str]:
    """(start, end) dot-format untuk tanggal; fallback default aplikasi."""
    row = conn.execute(
        "SELECT start_time, end_time FROM schedule_periods "
        "WHERE effective_from <= ? ORDER BY effective_from DESC LIMIT 1",
        (tanggal,)).fetchone()
    if row:
        return row["start_time"], row["end_time"]
    return DEFAULT_SCHEDULE_START, DEFAULT_SCHEDULE_END


def current_schedule(conn) -> tuple[str, str]:
    return schedule_for(conn, datetime.now(UTC).date().isoformat())


def add_period(conn, *, effective_from: str, start: str, end: str) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO schedule_periods "
        "(effective_from, start_time, end_time, created_at) VALUES (?,?,?,?)",
        (effective_from, start, end, now))
    latest = conn.execute(
        "SELECT start_time, end_time FROM schedule_periods "
        "ORDER BY effective_from DESC LIMIT 1").fetchone()
    set_setting(conn, "schedule_start", latest["start_time"])
    set_setting(conn, "schedule_end", latest["end_time"])


def delete_period(conn, period_id: int) -> None:
    conn.execute("DELETE FROM schedule_periods WHERE id = ?", (period_id,))
    latest = conn.execute(
        "SELECT start_time, end_time FROM schedule_periods "
        "ORDER BY effective_from DESC LIMIT 1").fetchone()
    if latest:
        set_setting(conn, "schedule_start", latest["start_time"])
        set_setting(conn, "schedule_end", latest["end_time"])
```

`src/core/schedule.py`:

```python
"""Pure helpers for schedule periods (v26)."""
from datetime import date

from src.core.attendance_calc import to_minutes


def validate_period(effective_from: str, start: str, end: str) -> str | None:
    """Pesan error, atau None bila valid."""
    try:
        d = date.fromisoformat(effective_from)
    except (TypeError, ValueError):
        return "Tanggal berlaku harus format YYYY-MM-DD."
    sm, em = to_minutes(start), to_minutes(end)
    if sm is None or em is None:
        return "Jam masuk/pulang harus format HH.MM (mis. 09.00)."
    if sm >= em:
        return "Jam masuk harus lebih awal dari jam pulang."
    return None


def is_future(effective_from: str) -> bool:
    try:
        return date.fromisoformat(effective_from) > date.today()
    except (TypeError, ValueError):
        return False
```

- [ ] **Step 4: Tes PASS.**
- [ ] **Step 5: Commit** — `feat(v26): resolver jadwal berjadwal (db + validasi)`

---

### Task 3: `src/db/overtime.py` (keputusan)

**Files:**
- Create: `src/db/overtime.py`
- Test: `tests/test_overtime_db.py`

- [ ] **Step 1: Tes gagal**

```python
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.overtime import apply_status, get_decision, set_note_approved

def test_status_lifecycle(tmp_path):
    p = tmp_path / "o.db"; init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="S1", nama="Agus", dept="Ops")
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        d = get_decision(conn, eid, "2026-10-01")
        assert d["status"] == "diajukan" and d["submitted_at"]
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=120, note="disetujui 2 jam")
        d = get_decision(conn, eid, "2026-10-01")
        assert d["status"] == "diterima"
        assert d["approved_minutes"] == 120
        assert d["detected_minutes_at_decision"] == 150
        assert d["decided_at"]

def test_revert_to_open_deletes_row(tmp_path):
    p = tmp_path / "o.db"; init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="S1", nama="Agus", dept="Ops")
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="open", detected_minutes=150)
        assert get_decision(conn, eid, "2026-10-01") is None

def test_set_note_approved_requires_row(tmp_path):
    p = tmp_path / "o.db"; init_db(p)
    with get_connection(p) as conn:
        eid = upsert_employee(conn, no_staff="S1", nama="Agus", dept="Ops")
        set_note_approved(conn, employee_id=eid, tanggal="2026-10-01",
                          note="cek", approved_minutes=None)
        assert get_decision(conn, eid, "2026-10-01") is None
```

- [ ] **Step 2: Jalankan → gagal.**
- [ ] **Step 3: Implementasi**

```python
"""Verification decisions for overtime rows (v26).

Open = ketiadaan baris. Status selain open di-upsert; kembali ke open
menghapus baris. detected_minutes_at_decision = snapshot audit angka yang
terdeteksi saat aksi verifikasi terakhir.
"""
import sqlite3
from datetime import UTC, datetime

VALID_STATUSES = ("open", "diajukan", "diterima", "tidak_diterima")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def get_decision(conn, employee_id: int, tanggal: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM overtime_decisions WHERE employee_id = ? AND tanggal = ?",
        (employee_id, tanggal)).fetchone()
    return dict(row) if row else None


def apply_status(conn, *, employee_id: int, tanggal: str, status: str,
                 detected_minutes: int | None,
                 approved_minutes: int | None = None,
                 note: str | None = None, now: str | None = None) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status tidak dikenal: {status!r}")
    if status == "open":
        conn.execute(
            "DELETE FROM overtime_decisions WHERE employee_id = ? AND tanggal = ?",
            (employee_id, tanggal))
        return
    ts = now or _now()
    existing = get_decision(conn, employee_id, tanggal)
    submitted_at = (existing or {}).get("submitted_at")
    if status in ("diajukan", "diterima", "tidak_diterima") and not submitted_at:
        submitted_at = ts
    decided_at = ts if status in ("diterima", "tidak_diterima") else None
    if existing and existing.get("decided_at") and status in ("diterima", "tidak_diterima"):
        decided_at = ts
    conn.execute(
        """
        INSERT INTO overtime_decisions
            (employee_id, tanggal, status, approved_minutes,
             detected_minutes_at_decision, note, submitted_at, decided_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(employee_id, tanggal) DO UPDATE SET
            status = excluded.status,
            approved_minutes = excluded.approved_minutes,
            detected_minutes_at_decision = excluded.detected_minutes_at_decision,
            note = COALESCE(excluded.note, overtime_decisions.note),
            submitted_at = excluded.submitted_at,
            decided_at = excluded.decided_at,
            updated_at = excluded.updated_at
        """,
        (employee_id, tanggal, status, approved_minutes,
         detected_minutes, note, submitted_at, decided_at, ts))


def set_note_approved(conn, *, employee_id: int, tanggal: str,
                      note: str | None, approved_minutes: int | None,
                      now: str | None = None) -> None:
    if get_decision(conn, employee_id, tanggal) is None:
        return
    ts = now or _now()
    conn.execute(
        "UPDATE overtime_decisions SET note = ?, approved_minutes = ?, updated_at = ? "
        "WHERE employee_id = ? AND tanggal = ?",
        (note, approved_minutes, ts, employee_id, tanggal))
```

- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit** — `feat(v26): penyimpanan keputusan lembur + snapshot audit`

---

### Task 4: `src/core/overtime.py` (deteksi + agregasi)

**Files:**
- Create: `src/core/overtime.py`
- Modify: `src/db/settings.py` (reader ambang)
- Test: `tests/test_overtime_core.py`

- [ ] **Step 1: Tes gagal** — kasus: hari kerja di atas ambang, keluar antara jam pulang dan ambang (tidak muncul), hari libur tanpa ambang, weekend, tipe Hari Libur, jam kosong, durasi ≤ 0, `format_duration`, `changed` flag, badge count.

```python
from src.core.overtime import detect_minutes, format_duration

def test_workday_above_threshold():
    assert detect_minutes(tipe="Hari Kerja", masuk="09:00", keluar="19:30",
                          schedule=("09.00", "17.00"), threshold_min=18*60,
                          is_holiday=False) == 150

def test_workday_between_end_and_threshold_not_counted():
    assert detect_minutes(tipe="Hari Kerja", masuk="09:00", keluar="17:30",
                          schedule=("09.00", "17.00"), threshold_min=18*60,
                          is_holiday=False) is None

def test_holiday_full_duration_without_threshold():
    assert detect_minutes(tipe="Hari Libur", masuk="09:00", keluar="14:00",
                          schedule=("09.00", "17.00"), threshold_min=18*60,
                          is_holiday=True) == 300

def test_missing_punch_skipped():
    assert detect_minutes(tipe="Hari Kerja", masuk=None, keluar="19:00",
                          schedule=("09.00", "17.00"), threshold_min=18*60,
                          is_holiday=False) is None

def test_format_duration():
    assert format_duration(150) == "2j 30m"
    assert format_duration(300) == "5j"
    assert format_duration(0) == "0m"
```

- [ ] **Step 2: Jalankan → gagal.**
- [ ] **Step 3: Implementasi**

`src/db/settings.py` tambah:

```python
from src.config import DEFAULT_OVERTIME_THRESHOLD

def read_overtime_threshold(conn) -> str:
    return get_setting(conn, "overtime_threshold",
                       default=DEFAULT_OVERTIME_THRESHOLD)
```

`src/core/overtime.py`:

```python
"""Overtime detection + monthly aggregation (v26). Pure, no Tk."""
import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date

from src.core.attendance_calc import to_minutes
from src.db.holidays import holiday_dates_in_month
from src.db.schedule import schedule_for
from src.db.settings import read_overtime_threshold


@dataclass(frozen=True)
class OvertimeRow:
    employee_id: int
    nama: str
    dept: str | None
    tanggal: str
    hari: str | None
    tipe: str | None
    masuk: str | None
    keluar: str | None
    minutes: int
    is_holiday: bool
    qualifies: bool
    status: str
    approved_minutes: int | None
    note: str | None
    submitted_at: str | None
    decided_at: str | None
    detected_at_decision: int | None

    @property
    def changed(self) -> bool:
        return (self.status != "open"
                and self.detected_at_decision is not None
                and self.detected_at_decision != self.minutes)


def threshold_minutes(conn) -> int:
    raw = read_overtime_threshold(conn)
    return to_minutes(raw) or 18 * 60


def detect_minutes(*, tipe, masuk, keluar, schedule, threshold_min, is_holiday):
    ms, ks = to_minutes(masuk), to_minutes(keluar)
    if ms is None or ks is None:
        return None
    if is_holiday:
        minutes = ks - ms
        return minutes if minutes > 0 else None
    if tipe != "Hari Kerja":
        return None
    end_m = to_minutes(schedule[1])
    if end_m is None:
        return None
    if ks <= threshold_min or ks <= end_m:
        return None
    return ks - end_m


def _month_bounds(year_month: str) -> tuple[str, str]:
    y, m = int(year_month[:4]), int(year_month[5:7])
    last = calendar.monthrange(y, m)[1]
    return f"{year_month}-01", f"{year_month}-{last:02d}"


def month_rows(conn, year_month: str) -> list[OvertimeRow]:
    start, end = _month_bounds(year_month)
    threshold = threshold_minutes(conn)
    holidays = holiday_dates_in_month(conn, year_month)
    raw = conn.execute(
        """
        SELECT ar.employee_id, e.nama, e.dept, ar.tanggal, ar.hari, ar.tipe,
               ar.masuk, ar.keluar,
               od.status, od.approved_minutes, od.note,
               od.submitted_at, od.decided_at, od.detected_minutes_at_decision
          FROM attendance_records ar
          JOIN employees e ON e.id = ar.employee_id
          LEFT JOIN overtime_decisions od
                 ON od.employee_id = ar.employee_id AND od.tanggal = ar.tanggal
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY ar.tanggal ASC, e.nama ASC
        """, (start, end)).fetchall()
    sched_cache: dict[str, tuple[str, str]] = {}
    out: list[OvertimeRow] = []
    for r in raw:
        tgl = r["tanggal"]
        if tgl not in sched_cache:
            sched_cache[tgl] = schedule_for(conn, tgl)
        d = date.fromisoformat(tgl)
        is_holiday = (d.weekday() >= 5 or tgl in holidays
                      or r["tipe"] == "Hari Libur")
        minutes = detect_minutes(
            tipe=r["tipe"], masuk=r["masuk"], keluar=r["keluar"],
            schedule=sched_cache[tgl], threshold_min=threshold,
            is_holiday=is_holiday)
        has_decision = r["status"] is not None
        if minutes is None and not has_decision:
            continue
        out.append(OvertimeRow(
            employee_id=r["employee_id"], nama=r["nama"], dept=r["dept"],
            tanggal=tgl, hari=r["hari"], tipe=r["tipe"],
            masuk=r["masuk"], keluar=r["keluar"],
            minutes=minutes or 0, is_holiday=is_holiday,
            qualifies=minutes is not None,
            status=r["status"] or "open",
            approved_minutes=r["approved_minutes"], note=r["note"],
            submitted_at=r["submitted_at"], decided_at=r["decided_at"],
            detected_at_decision=r["detected_minutes_at_decision"]))
    return out


def count_pending(conn, year_month: str) -> int:
    return sum(1 for r in month_rows(conn, year_month)
               if r.status in ("open", "diajukan"))


def summarize(rows: list[OvertimeRow]) -> list[dict]:
    agg: dict[int, dict] = {}
    for r in rows:
        a = agg.setdefault(r.employee_id, {
            "employee_id": r.employee_id, "nama": r.nama, "dept": r.dept,
            "days": 0, "detected": 0, "approved": 0})
        a["days"] += 1
        a["detected"] += r.minutes
        if r.status == "diterima":
            a["approved"] += r.approved_minutes or 0
    return sorted(agg.values(), key=lambda a: a["detected"], reverse=True)


def format_duration(minutes: int) -> str:
    h, m = divmod(max(0, int(minutes)), 60)
    if h and m:
        return f"{h}j {m}m"
    if h:
        return f"{h}j"
    return f"{m}m"
```

- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit** — `feat(v26): mesin deteksi lembur + agregasi bulanan`

---

### Task 5: Band "Pola Jam Masuk" ikut jadwal per tanggal

**Files:**
- Modify: `src/core/insights.py` (ganti `_POLA_JAM_BANDS`/`_classify_jam_masuk`/`pola_jam_masuk`)
- Modify: `src/reports/html_renderer.py` (pass `jam_threshold_label`)
- Modify: `src/reports/templates/dashboard.html.j2:204`
- Test: `tests/test_insights_pola_jam.py` (baru/update)

- [ ] **Step 1: Tes gagal**

```python
from src.core.insights import band_labels, pola_jam_masuk

def test_band_labels_shift_with_start():
    labels = band_labels(9 * 60)
    assert labels[0][0] == "<08:45"
    assert labels[2] == ("09:00", "ontime")
    assert labels[7][0] == ">10:00"
```

Plus: seed DB dengan periode lama (08.00) + baru (09.00); `pola_jam_masuk` untuk periode September menghitung baris 1–13 sebagai band relatif 08:00 dan baris 14+ relatif 09:00, dengan label dari jadwal akhir periode (09:00).

- [ ] **Step 2: Jalankan → gagal.**
- [ ] **Step 3: Implementasi** — `insights.py`:

```python
def band_labels(start_min: int) -> list[tuple[str, str]]:
    def f(m): return f"{m // 60:02d}:{m % 60:02d}"
    return [
        (f"<{f(start_min - 15)}", "early"),
        (f"{f(start_min - 15)}-{f(start_min - 1)}", "early"),
        (f(start_min), "ontime"),
        (f"{f(start_min + 1)}-{f(start_min + 5)}", "mild"),
        (f"{f(start_min + 6)}-{f(start_min + 15)}", "mild"),
        (f"{f(start_min + 16)}-{f(start_min + 30)}", "mod"),
        (f"{f(start_min + 31)}-{f(start_min + 60)}", "severe"),
        (f">{f(start_min + 60)}", "chronic"),
    ]


def _band_index(masuk_min: int, start_min: int) -> int:
    delta = masuk_min - start_min
    if delta < -15: return 0
    if delta < 0:   return 1
    if delta == 0:  return 2
    if delta <= 5:  return 3
    if delta <= 15: return 4
    if delta <= 30: return 5
    if delta <= 60: return 6
    return 7
```

`pola_jam_masuk` query `tanggal, masuk`; cache `schedule_for(conn, tanggal)` per tanggal; klasifikasi pakai `_band_index(masuk_min, to_minutes(start))`; label dari `band_labels(to_minutes(schedule_for(conn, period_end)[0]))`.

`html_renderer.py`:

```python
from src.core.attendance_calc import to_minutes
from src.core.insights import band_labels
...
schedule_start_label = band_labels(
    to_minutes(schedule_for(conn, period_end)[0]))[2][0]
...
html = tmpl.render(..., jam_threshold_label=schedule_start_label, ...)
```

`dashboard.html.j2:204` → `{% if b.band == jam_threshold_label %}`.

- [ ] **Step 4: PASS** (termasuk update tes lama yang mengasumsikan label 08:00 — semai periode 08.00 di fixture tes tersebut, atau ubah ekspektasi ke 09:00 bila tesnya netral).
- [ ] **Step 5: Commit** — `feat(v26): Pola Jam Masuk relatif jadwal tanggal`

---

### Task 6: Pulang cepat & weekly export ikut jadwal per tanggal

**Files:**
- Modify: `src/core/report_generator.py` (`compute_derived`, `generate_monthly_report`)
- Modify: `src/core/weekly_export.py`
- Test: `tests/test_report_generator.py`, `tests/test_weekly_export.py`

- [ ] **Step 1: Tes** — DB dengan periode `1970-01-01` 08.00–16.00 + `2026-09-14` 09.00–17.00; baris 10 Sep keluar 16:30 → pulang_cepat 0; baris 15 Sep keluar 16:30 → pulang_cepat 30. Weekly export: lupa absen datang 15 Sep memakai 09.00 (`09:15` untuk penalti 15).
- [ ] **Step 2: Implementasi** — `compute_derived(row, *, schedule_end_minutes: int)`; caller loop `schedule_end_minutes=to_minutes(schedule_for(conn, r["tanggal"])[1]) or 16*60`. Hapus `JADWAL_END_MINUTES` atau jadikan fallback dengan komentar. Weekly export: di loop, `sched = schedule_for(conn, r["tanggal"])[0]`; buang `get_setting`/`DEFAULT_SCHEDULE_START`.
- [ ] **Step 3: Update tes B1–B4** (nilai `"08:00"`→`"09:00"`, `"08:15"`→`"09:15"`) karena fallback config berubah.
- [ ] **Step 4: Jalankan kedua file tes → PASS.**
- [ ] **Step 5: Commit** — `feat(v26): laporan bulanan & weekly export pakai jadwal per tanggal`

---

### Task 7: Edit Data (Heatmap) pakai jadwal per tanggal

**Files:**
- Modify: `src/ui/components/attendance_edit_dialog.py:83-85`
- Test: `tests/test_attendance_edit_dialog.py`, `tests/test_attendance_edit_reason.py`

- [ ] **Step 1: Implementasi** — ganti dua `get_setting` dengan:

```python
from src.db.schedule import schedule_for
...
with get_connection(DB_PATH) as conn:
    self._sched_start, self._sched_end = schedule_for(conn, tanggal)
```

- [ ] **Step 2: Update tes A3/A4** yang bergantung default 08.00: semai periode 08.00 eksplisit di DB tes tersebut (via `add_period`) atau sesuaikan ekspektasi. Perbarui `tests/test_attendance_edit_dialog.py::test_preview_matches_recompute` (dialog kini membaca periode; tes menyemai 08.00/16.00 agar angka lama tetap valid).
- [ ] **Step 3: Jalankan tes terkait → PASS.**
- [ ] **Step 4: Commit** — `feat(v26): Edit Data memakai jadwal tanggal baris`

---

### Task 8: Settings — "Jam Kantor" + "Ambang Lembur"

**Files:**
- Modify: `src/ui/screens/settings.py`
- Create: `src/ui/components/schedule_change_dialog.py`
- Test: `tests/test_settings_schedule.py` (baru)

- [ ] **Step 1: Tes gagal** — layar memuat riwayat; menambah periode via dialog menyimpan baris + mirror settings; ambang invalid (≤ jam pulang) ditolak; entri masa depan bisa dihapus.
- [ ] **Step 2: Implementasi**
  - Ganti `row3` (label Jadwal Kerja) dengan panel "Jam Kantor": label jadwal berjalan + `CTkScrollableFrame`/Treeview kecil riwayat (kolom Berlaku Mulai / Masuk / Pulang / Aksi hapus untuk `is_future`), tombol "+ Tambah perubahan jadwal…".
  - `ScheduleChangeDialog(CTkToplevel)`: 3 entry (tanggal YYYY-MM-DD, masuk HH.MM, pulang HH.MM) + validasi `validate_period` + tanggal ≥ hari ini + unik; `on_saved` refresh.
  - Tambah row "Ambang Lembur (HH.MM)" dengan `self.overtime_var`; `_save` validasi via `to_minutes` dan `> jam pulang berjalan`, tulis `set_setting(conn, "overtime_threshold", ...)`.
  - `on_show` refresh jadwal berjalan + riwayat + ambang.
- [ ] **Step 3: Jalankan tes → PASS.**
- [ ] **Step 4: Commit** — `feat(v26): Settings Jam Kantor berjadwal + Ambang Lembur`

---

### Task 9: Cetak/PDF lembur

**Files:**
- Create: `src/reports/overtime_print.py`, `src/reports/templates/overtime.html.j2`
- Create: `src/ui/components/overtime_print_dialog.py`
- Test: `tests/test_overtime_print.py`

- [ ] **Step 1: Tes gagal** — render mode `all` memuat baris Open; mode `accepted` hanya Diterima dan memakai jam disetujui; total per karyawan; `hr_officer_name` ikut.
- [ ] **Step 2: Implementasi** — `render_overtime_print_html(conn, year_month, mode)` mengikuti pola `dinas_recap_print.py` (env dari `html_renderer._build_env`, template baru; kop "Josaphat Tech Solution · HR Absensi", periode, tabel, subtotal, tanda tangan). Dialog radio: "Semua status" / "Hanya Diterima" (pola `heatmap_print_dialog.py`).
- [ ] **Step 3: PASS.**
- [ ] **Step 4: Commit** — `feat(v26): cetak laporan lembur (semua status / hanya diterima)`

---

### Task 10: Layar Lembur + navigasi + ikon

**Files:**
- Create: `src/ui/screens/overtime.py`
- Modify: `src/ui/app.py` (nav_groups, `_create_screen`, badge), `src/ui/icons.py`
- Test: `tests/test_overtime_screen.py`, `tests/test_app_overtime_nav.py`

- [ ] **Step 1: Tes gagal** — screen konstruk; daftar terisi dari `month_rows`; filter tab; aksi `Ajukan` menulis keputusan; search menyaring; KPI menghitung.
- [ ] **Step 2: Implementasi** — `OvertimeScreen` mengikuti `dinas_recap.py` + `resolve_base.py`:
  - Header: judul "Lembur", `ActiveMonthBanner(variant="badge")`, `SearchBar(debounce_ms=200)` + `install_shortcuts`, tombol Cetak magenta.
  - KPI row 4 `KPICard` (Orang, Jam terdeteksi, Jam disetujui, Belum diproses).
  - `CTkSegmentedButton` filter status (label + jumlah) + bar aksi massal (muncul saat ada baris terpilih, `selectmode="extended"`).
  - Tabel `style_treeview("Overtime.Treeview")` + `apply_zebra_tags` + `RowHover`; kolom sesuai spec; klik baris → dialog detail (Task 11); aksi massal dengan kelayakan transisi + laporan baris dilewati; `notify_data_changed()` setelah aksi.
  - Panel kanan ringkasan per karyawan (Treeview kecil, sort total).
  - `on_show()` re-read bulan + reload tanpa rebuild chrome; motion `RenderSignature` + `flash_row`; `run_bg` untuk load bulan besar bila perlu.
  - Nav: `("🕒", "Lembur", "Overtime")` di WORKFLOW setelah Severe Lateness; branch `_create_screen`; ikon `"Overtime": "\ue823"` (jam — sama keluarga dengan SevereLateness; ganti codepoint bila bentrok visual).
- [ ] **Step 3: PASS.**
- [ ] **Step 4: Commit** — `feat(v26): layar Lembur + navigasi + aksi massal`

---

### Task 11: Dialog detail + verifikasi

**Files:**
- Create: `src/ui/components/overtime_detail_dialog.py`
- Test: `tests/test_overtime_detail_dialog.py`

- [ ] **Step 1: Tes gagal** — tombol sesuai status (Open→Ajukan; Diajukan→Terima/Tolak/Kembalikan; final→ubah + kembalikan); simpan jam disetujui (0..terdeteksi) + catatan; penanda "data berubah".
- [ ] **Step 2: Implementasi** — `OvertimeDetailDialog(CTkToplevel)` pola `attendance_edit_dialog.py`; entry jam & menit; `Textbox` catatan; `feedback.ask_yes_no` untuk transisi; `apply_status` + `set_note_approved`; `on_saved` callback; Esc tutup.
- [ ] **Step 3: PASS.**
- [ ] **Step 4: Commit** — `feat(v26): dialog detail + verifikasi lembur`

---

### Task 12: Badge Dashboard + sidebar

**Files:**
- Modify: `src/ui/screens/dashboard.py` (KPI ke-4 clickable), `src/ui/app.py` (badge nav)
- Test: `tests/test_dashboard_overtime_kpi.py`, `tests/test_app_overtime_badge.py`

- [ ] **Step 1: Tes gagal** — KPI "Lembur belum diproses" menampilkan `count_pending`; klik memanggil `_show("Overtime")`; badge sidebar menampilkan angka dan hilang saat 0.
- [ ] **Step 2: Implementasi** — dashboard: `for i in range(4)`, kartu ke-4, nilai dari `count_pending(conn, self._current_month)` (masukkan ke `_query` agar termemoisasi + ikut `data_version`); bind klik pada kartu + anak-anaknya ke `top._show("Overtime")`. App: `_build_nav_item` menyimpan `frame._badge` (CTkLabel kecil di kanan); `_refresh_active_month_label` (dipanggil tiap navigasi) memperbarui angka via `count_pending`; sembunyikan saat 0.
- [ ] **Step 3: PASS.**
- [ ] **Step 4: Commit** — `feat(v26): badge lembur di Dashboard + sidebar`

---

### Task 13: Versi, changelog, suite penuh

**Files:**
- Modify: `src/config.py` (`APP_VERSION` 26.0.0, `APP_BUILD_DATE`, `APP_CHANGELOG`)
- Test: seluruh suite

- [ ] **Step 1:** Prepend entri `26.0.0` (feat: jam kantor berjadwal + cutoff 14 Sep; menu Lembur + verifikasi Open/Diajukan/Diterima/Tidak Diterima + jam disetujui + catatan + cetak; badge; change: default jam kantor baru + Settings riwayat jadwal; fix: Pola Jam Masuk/pulang cepat/lupa absen kini ikut jadwal tanggal).
- [ ] **Step 2:** `.venv\Scripts\python.exe -m pytest -q` → semua hijau (perbaiki regresi bila ada).
- [ ] **Step 3: Commit** — `chore(v26): APP_VERSION 26.0.0 + changelog`

---

### Task 14: Bundle rilis

- [ ] **Step 1:** `tasklist | findstr /i HR-Absensi` → pastikan tidak berjalan.
- [ ] **Step 2:** `.venv\Scripts\python.exe -m tools.build_installer`
- [ ] **Step 3:** Rotasi `dist/HR-Absensi/` ke produksi (pola `.bak`/`.bak.old`), `data/` tidak ikut.
- [ ] **Step 4:** Copy installer ke `Installers/HR-Absensi-Setup-v26.0.0.exe`.
- [ ] **Step 5:** Smoke manual: buka exe, cek Dashboard (KPI lembur), Heatmap (edit data 14 Sep+), Settings (Jam Kantor + riwayat), Lembur (verifikasi + cetak).
- [ ] **Step 6:** Push **hanya setelah otorisasi user**; majukan `latest`; update `memory/version_state.md`.

---

## Self-Review

- **Spec coverage:** §3 aturan deteksi → T4; §4.1 skema → T1/T3; §4.2 migrasi → T1; §4.3 modul → T2/T3/T4/T10/T9; §4.4 titik hardcode → T5/T6/T7; §4.5 Settings → T8; §5 layar → T10/T11/T12; §6 cetak → T9; §7 kasus tepi → T3 (revert/hapus), T4 (`changed`, non-qualifying tampil, durasi ≤ 0), T10 (massal dilewati); §8 uji → tersebar; §9 batas lingkup → tidak ada task (benar).
- **Placeholder scan:** tidak ada TBD; langkah UI yang kompleks menunjuk file pola yang sudah dibaca (kode aktual ditulis saat eksekusi mengikuti pola tersebut).
- **Type consistency:** `schedule_for` → `(start, end)` string dot; `detect_minutes` mengembalikan `int | None`; `OvertimeRow.minutes: int`, `qualifies: bool`; `apply_status(..., detected_minutes, approved_minutes, note)` konsisten di T3/T10/T11.
