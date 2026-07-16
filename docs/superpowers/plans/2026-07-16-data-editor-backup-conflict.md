# Keamanan Data + Edit Manual — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambah editor baris absensi inline dari Heatmap (edit/tambah/hapus, recompute otomatis), Backup & Restore file DB penuh, dan jendela resolusi konflik import — dirilis sebagai v23.0.0 (built exe + push).

**Architecture:** Tiga komponen. Modul murni (`backup`, `attendance_calc`, `import_conflicts`) di-TDD penuh; lapisan DB menambah fungsi ke `attendance.py`; UI menambah 2 dialog + tab Settings + hook klik Heatmap + pra-scan konflik di alur import. Semua tulis memanggil `notify_data_changed()`. Urutan build **B→A→C**.

**Tech Stack:** Python 3.13, customtkinter, sqlite3, pytest, PyInstaller, Inno Setup.

**Spec:** `docs/superpowers/specs/2026-07-16-data-editor-backup-conflict-design.md`

---

## File structure

**Create:**
- `src/db/backup.py` — snapshot/list/prune/restore file DB
- `src/core/attendance_calc.py` — recompute murni + `_to_minutes`
- `src/core/import_conflicts.py` — `find_conflicts` murni
- `src/ui/components/attendance_edit_dialog.py` — dialog editor baris
- `src/ui/components/import_conflict_dialog.py` — jendela konflik import
- `tests/test_backup.py`, `tests/test_attendance_calc.py`, `tests/test_import_conflicts.py`, `tests/test_attendance_edit_db.py`, `tests/test_backup_retention.py`, `tests/test_changelog_v23_0_0.py`

**Modify:**
- `src/db/schema.py` — kolom `manual_edited_at` + migrasi
- `src/db/attendance.py` — `get_attendance`, `save_manual_attendance`, `delete_attendance`, `manual_rows_for_import`; `upsert_attendance` clear flag on update
- `src/core/week_utils.py` — `HARI_NAMES_ID` + `hari_name`
- `src/ui/screens/settings.py` — tab "Backup & Restore"
- `src/ui/screens/heatmap.py` — klik sel → dialog; peta `_edit_by_item`
- `src/ui/screens/import_screen.py` — pra-scan konflik + backup + resolution
- `src/config.py` — `APP_VERSION="23.0.0"`, `APP_BUILD_DATE="2026-07-16"`, changelog
- `.gitignore` — `data/backups/`

---

## Phase B — Backup & Restore (jaring pengaman, dibangun pertama)

### Task 1: Modul backup — create/list

**Files:** Create `src/db/backup.py`; Test `tests/test_backup.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_backup.py
from datetime import datetime
from pathlib import Path
from src.db import backup

def _mkdb(tmp_path, content=b"DBDATA"):
    p = tmp_path / "hr.db"; p.write_bytes(content); return p

def test_create_backup_copies_file_with_reason_slug(tmp_path):
    db = _mkdb(tmp_path)
    now = datetime(2026, 7, 16, 14, 20, 5)
    dest = backup.create_backup(db, reason="import", now=now)
    assert dest.name == "hr-20260716-142005-sebelum-import.db"
    assert dest.read_bytes() == b"DBDATA"
    assert dest.parent == tmp_path / "backups"

def test_list_backups_newest_first(tmp_path):
    db = _mkdb(tmp_path)
    backup.create_backup(db, reason="manual", now=datetime(2026,7,15,9,0,0))
    backup.create_backup(db, reason="import", now=datetime(2026,7,16,9,0,0))
    rows = backup.list_backups(db)
    assert [r["reason"] for r in rows] == ["sebelum-import", "manual"]
    assert rows[0]["created_at"] == datetime(2026,7,16,9,0,0)
    assert rows[0]["size_bytes"] == len(b"DBDATA")
```

- [ ] **Step 2: Run — expect fail** `../../../.venv/Scripts/python.exe -m pytest tests/test_backup.py -x -q`

- [ ] **Step 3: Implement**

```python
# src/db/backup.py
"""Full-file SQLite snapshots — backup/list/prune/restore. No Tk, no sqlite.
Snapshots live in <db_path>.parent/backups/ named hr-YYYYMMDD-HHMMSS-<slug>.db."""
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

BACKUP_DIRNAME = "backups"
REASON_SLUGS = {"import": "sebelum-import", "manual": "manual",
                "hapus": "sebelum-hapus", "restore": "sebelum-restore"}
_FNAME_RE = re.compile(r"^hr-(\d{8})-(\d{6})-(.+)\.db$")

def backup_dir(db_path) -> Path:
    return Path(db_path).parent / BACKUP_DIRNAME

def create_backup(db_path, *, reason, now=None) -> Path:
    db_path = Path(db_path)
    d = backup_dir(db_path); d.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    slug = REASON_SLUGS.get(reason, "manual")
    dest = d / f"hr-{now:%Y%m%d}-{now:%H%M%S}-{slug}.db"
    shutil.copy2(db_path, dest)
    prune_backups(db_path, now=now)
    return dest

def list_backups(db_path) -> list:
    d = backup_dir(db_path)
    if not d.exists():
        return []
    out = []
    for p in d.glob("hr-*.db"):
        m = _FNAME_RE.match(p.name)
        if m:
            created = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            reason = m.group(3)
        else:
            created = datetime.fromtimestamp(p.stat().st_mtime); reason = "?"
        out.append({"path": p, "filename": p.name, "created_at": created,
                    "size_bytes": p.stat().st_size, "reason": reason})
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out
```

(Note: `prune_backups` added in Task 2; define a temporary no-op stub now so imports work, replaced in Task 2.)

```python
def prune_backups(db_path, *, max_age_days=365, max_total_bytes=1_000_000_000,
                  keep_min=5, now=None):
    return []  # replaced in Task 2
```

- [ ] **Step 4: Run — expect pass**
- [ ] **Step 5: Commit** `git add src/db/backup.py tests/test_backup.py && git commit -m "feat(v23): backup module — create + list snapshots"`

### Task 2: Retensi — prune (1 thn / ~1 GB / floor 5)

**Files:** Modify `src/db/backup.py`; Test `tests/test_backup_retention.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_backup_retention.py
from datetime import datetime, timedelta
from src.db import backup

def _seed(tmp_path, specs):
    """specs: list of (datetime, size_bytes). Writes snapshot files directly."""
    d = tmp_path / "backups"; d.mkdir(parents=True, exist_ok=True)
    for dt, size in specs:
        (d / f"hr-{dt:%Y%m%d}-{dt:%H%M%S}-manual.db").write_bytes(b"x" * size)
    (tmp_path / "hr.db").write_bytes(b"x")

def test_prune_removes_older_than_one_year_but_keeps_floor(tmp_path):
    now = datetime(2026, 7, 16, 12, 0, 0)
    # 3 recent + 4 very old (>365d). floor=5 protects 5 newest regardless of age.
    specs = [(now - timedelta(days=k), 10) for k in (1, 2, 3)]
    specs += [(now - timedelta(days=400 + k), 10) for k in range(4)]
    _seed(tmp_path, specs)
    backup.prune_backups(tmp_path / "hr.db", now=now)
    remaining = backup.list_backups(tmp_path / "hr.db")
    # 7 total, floor keeps 5 newest; of the 2 unprotected both are >365d → removed → 5 left
    assert len(remaining) == 5

def test_prune_enforces_size_budget_oldest_first(tmp_path):
    now = datetime(2026, 7, 16, 12, 0, 0)
    specs = [(now - timedelta(hours=k), 100) for k in range(10)]  # all recent
    _seed(tmp_path, specs)
    backup.prune_backups(tmp_path / "hr.db", now=now,
                         max_total_bytes=650, keep_min=5)
    remaining = backup.list_backups(tmp_path / "hr.db")
    # floor 5 protected (500B); budget 650 allows 1 more survivor (600B) → 6 files
    assert len(remaining) == 6
```

- [ ] **Step 2: Run — expect fail**
- [ ] **Step 3: Replace `prune_backups`**

```python
def prune_backups(db_path, *, max_age_days=365, max_total_bytes=1_000_000_000,
                  keep_min=5, now=None):
    now = now or datetime.now()
    items = list_backups(db_path)          # newest first
    protected, candidates = items[:keep_min], items[keep_min:]
    removed = []
    cutoff = now - timedelta(days=max_age_days)
    survivors = []
    for it in candidates:
        if it["created_at"] < cutoff:
            it["path"].unlink(missing_ok=True); removed.append(it["path"])
        else:
            survivors.append(it)
    total = sum(i["size_bytes"] for i in protected) + sum(i["size_bytes"] for i in survivors)
    for it in reversed(survivors):         # oldest survivor first
        if total <= max_total_bytes:
            break
        it["path"].unlink(missing_ok=True); removed.append(it["path"]); total -= it["size_bytes"]
    return removed
```

- [ ] **Step 4: Run — expect pass**
- [ ] **Step 5: Commit** `git commit -am "feat(v23): backup retention — 1yr age + size budget + floor"`

### Task 3: Restore (backup dulu, lalu timpa)

**Files:** Modify `src/db/backup.py`; Test append to `tests/test_backup.py`

- [ ] **Step 1: Failing test**

```python
def test_restore_backs_up_current_then_overwrites(tmp_path):
    from src.db import backup
    db = tmp_path / "hr.db"; db.write_bytes(b"CURRENT")
    snap = backup.create_backup(db, reason="manual", now=__import__("datetime").datetime(2026,7,1,8,0,0))
    db.write_bytes(b"CHANGED")                       # simulate later edits
    now = __import__("datetime").datetime(2026,7,16,10,0,0)
    pre = backup.restore_backup(db, snap, now=now)
    assert db.read_bytes() == b"CURRENT"             # restored
    assert pre.name == "hr-20260716-100000-sebelum-restore.db"
    assert pre.read_bytes() == b"CHANGED"            # pre-restore safety snapshot
```

- [ ] **Step 2: Run — expect fail**
- [ ] **Step 3: Implement**

```python
def restore_backup(db_path, snapshot_path, *, now=None) -> Path:
    db_path = Path(db_path)
    pre = create_backup(db_path, reason="restore", now=now)
    shutil.copy2(Path(snapshot_path), db_path)
    return pre
```

- [ ] **Step 4: Run — expect pass** — [ ] **Step 5: Commit** `git commit -am "feat(v23): backup restore with pre-restore safety snapshot"`

### Task 4: Tab "Backup & Restore" di Settings + gitignore

**Files:** Modify `src/ui/screens/settings.py`, `.gitignore`

- [ ] **Step 1:** Add `data/backups/` line to `.gitignore` under the brainstorm block.
- [ ] **Step 2:** In `SettingsScreen._build()` add tab + builder:

```python
self.tabs.add("Backup & Restore")
self._build_backup(self.tabs.tab("Backup & Restore"))
```

- [ ] **Step 3:** Implement `_build_backup(self, parent)` — imports `from src.config import DB_PATH`; `from src.db import backup as backup_mod`; `from src.ui import feedback`; theme tokens. Layout:
  - Toolbar row: `CTkButton("＋ Backup sekarang", command=self._do_manual_backup, fg_color=COLOR_ACCENT, text_color=COLOR_BG)` + `CTkButton("📂 Buka folder", command=self._open_backup_folder, ...ghost)` + info label.
  - Retensi label (muted): `"data/backups/ · retensi 1 tahun · auto-hapus lama (batas ~1 GB, min. 5 terbaru)"`.
  - `self._backup_list = ctk.CTkScrollableFrame(parent, fg_color="transparent")`; `self._render_backups()`.
  - `_render_backups()`: clear children; `for it in backup_mod.list_backups(DB_PATH):` build a row frame (surface bg, border) with filename (mono), `it["created_at"].strftime("%d %b %Y · %H:%M")` + size KB/MB, a colored reason badge, and buttons `Restore`/`Hapus`.
  - `_do_manual_backup`: `backup_mod.create_backup(DB_PATH, reason="manual")` → toast/`feedback.show_info` → `_render_backups()`.
  - `_open_backup_folder`: `os.startfile(str(backup_mod.backup_dir(DB_PATH)))` guarded (create dir first).
  - `_restore(path)`: `feedback.ask_yes_no(...)` → `backup_mod.restore_backup(DB_PATH, path)` → `notify_data_changed()` → `feedback.show_info("Restore selesai","Disarankan restart aplikasi.")` → `_render_backups()`.
  - `_delete_backup(path)`: `feedback.ask_yes_no` → `Path(path).unlink(missing_ok=True)` → `_render_backups()`.

- [ ] **Step 4: Smoke** — headless: construct `SettingsScreen` under a hidden root, switch to the tab, assert `_render_backups` runs without error on an empty backups dir.

```python
# tests/test_settings_backup_tab.py  (skip if no display)
import os, pytest
pytestmark = pytest.mark.skipif(os.environ.get("CI_NO_TK") == "1", reason="no Tk")

def test_backup_tab_builds(tmp_path, monkeypatch):
    import customtkinter as ctk
    from src.ui.screens import settings as S
    monkeypatch.setattr(S, "DB_PATH", tmp_path / "hr.db")
    (tmp_path / "hr.db").write_bytes(b"x")
    root = ctk.CTk(); root.withdraw()
    try:
        scr = S.SettingsScreen(root)
        scr._render_backups()          # must not raise on empty dir
    finally:
        root.destroy()
```

- [ ] **Step 5: Run** screen test separately: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_backup_tab.py -q`
- [ ] **Step 6: Commit** `git add -A && git commit -m "feat(v23): Backup & Restore tab in Settings + gitignore"`

---

## Phase A — Editor baris absensi

### Task 5: Mesin recompute + hari-name

**Files:** Create `src/core/attendance_calc.py`; Modify `src/core/week_utils.py`; Test `tests/test_attendance_calc.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_attendance_calc.py
from src.core.attendance_calc import recompute, to_minutes
from src.core.week_utils import hari_name

def R(**kw):
    base = dict(tipe="Hari Kerja", masuk=None, keluar=None,
                schedule_start="08.00", schedule_end="16.00")
    base.update(kw); return recompute(**base)

def test_to_minutes_accepts_colon_and_dot():
    assert to_minutes("08:15") == 495
    assert to_minutes("08.00") == 480
    assert to_minutes("") is None and to_minutes("xx") is None

def test_missing_keluar_is_issue():
    r = R(masuk="08:00", keluar=None)
    assert r["has_issue"] == 1

def test_full_day_no_issue_late_zero_work_eight():
    r = R(masuk="08:00", keluar="16:00")
    assert r == {"has_issue": 0, "terlambat_menit": 0, "kerja_jam": 8.0, "lembur_jam": 0.0}

def test_late_and_overtime():
    r = R(masuk="08:20", keluar="16:30")
    assert r["terlambat_menit"] == 20
    assert r["lembur_jam"] == 0.5
    assert r["kerja_jam"] == 8.2

def test_libur_type_never_issue_or_late():
    r = R(tipe="Hari Libur", masuk=None, keluar=None)
    assert r["has_issue"] == 0 and r["terlambat_menit"] == 0

def test_overnight_clamped_to_zero():
    assert R(masuk="16:00", keluar="08:00")["kerja_jam"] == 0.0

def test_hari_name_indonesia():
    assert hari_name("2026-05-06") == "Rabu"   # Wed
```

- [ ] **Step 2: Run — expect fail**
- [ ] **Step 3: Implement** `src/core/attendance_calc.py`:

```python
"""Pure recompute of derived attendance fields from raw punches + schedule.
No I/O. Mirrors the machine's semantics closely enough; see spec D8/D9."""
import re

_TIME_RE = re.compile(r"^(\d{1,2})[:.](\d{2})$")

def to_minutes(s):
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
    ms, ks = to_minutes(masuk), to_minutes(keluar)
    start = to_minutes(schedule_start) or 0
    end = to_minutes(schedule_end) or 0
    is_kerja = tipe == "Hari Kerja"
    has_issue = 1 if (is_kerja and (ms is None or ks is None)) else 0
    terlambat = max(0, ms - start) if (is_kerja and ms is not None) else 0
    kerja = round(max(0, ks - ms) / 60, 1) if (ms is not None and ks is not None) else 0.0
    lembur = round(max(0, ks - end) / 60, 1) if ks is not None else 0.0
    return {"has_issue": has_issue, "terlambat_menit": terlambat,
            "kerja_jam": kerja, "lembur_jam": lembur}
```

Add to `src/core/week_utils.py`:

```python
HARI_NAMES_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

def hari_name(date_iso: str) -> str:
    """ISO 'YYYY-MM-DD' → Indonesian day name (Senin..Minggu)."""
    from datetime import date
    return HARI_NAMES_ID[date.fromisoformat(date_iso).weekday()]
```

- [ ] **Step 4: Run — expect pass** — [ ] **Step 5: Commit** `git add -A && git commit -m "feat(v23): attendance recompute engine + hari_name"`

### Task 6: Migrasi `manual_edited_at`

**Files:** Modify `src/db/schema.py`; Test `tests/test_backup.py` (append) or new `tests/test_schema_manual_col.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_schema_manual_col.py
import sqlite3
from src.db.schema import init_db, DDL

def test_manual_edited_at_added_to_legacy_db(tmp_path):
    db = tmp_path / "hr.db"
    # Simulate a pre-existing DB WITHOUT the column: create minimal old table
    conn = sqlite3.connect(db)
    conn.executescript("""CREATE TABLE employees(id INTEGER PRIMARY KEY, no_staff TEXT UNIQUE, nama TEXT);
        CREATE TABLE attendance_records(id INTEGER PRIMARY KEY, employee_id INTEGER, tanggal TEXT,
        masuk TEXT, keluar TEXT, has_issue INTEGER, UNIQUE(employee_id, tanggal));""")
    conn.commit(); conn.close()
    init_db(db)   # must ALTER-add the column idempotently
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(attendance_records)")}
    conn.close()
    assert "manual_edited_at" in cols
```

- [ ] **Step 2: Run — expect fail**
- [ ] **Step 3: Implement** — add to `DDL` the column in the `attendance_records` CREATE (`manual_edited_at TEXT`) AND in `_migrate()`:

```python
    acols = {row[1] for row in conn.execute("PRAGMA table_info(attendance_records)")}
    if "manual_edited_at" not in acols:
        conn.execute("ALTER TABLE attendance_records ADD COLUMN manual_edited_at TEXT")
```

- [ ] **Step 4: Run — expect pass** (+ run full suite to confirm no regression) — [ ] **Step 5: Commit** `git commit -am "feat(v23): manual_edited_at column + migration"`

### Task 7: DB layer editor + upsert clears flag

**Files:** Modify `src/db/attendance.py`; Test `tests/test_attendance_edit_db.py`

- [ ] **Step 1: Failing tests** — using a real temp DB via `init_db` + `get_connection`:

```python
# tests/test_attendance_edit_db.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (upsert_attendance, get_attendance,
    save_manual_attendance, delete_attendance, manual_rows_for_import)

def _emp(conn): return upsert_employee(conn, no_staff="S1", nama="Budi", dept="Prod")

def test_save_manual_sets_flag_and_preserves_reason(tmp_path):
    db = tmp_path/"hr.db"; init_db(db)
    with get_connection(db) as c:
        eid = _emp(c)
        # seed an imported row w/ a reason already set
        upsert_attendance(c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar=None,
            kerja_jam=0.0, lembur_jam=0.0, terlambat_menit=0, has_issue=1,
            imported_from="f.xls")
        c.execute("UPDATE attendance_records SET reason_category='izin_sakit' WHERE employee_id=? AND tanggal=?",(eid,"2026-05-06"))
    with get_connection(db) as c:
        eid = _emp(c)
        save_manual_attendance(c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
            kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0, has_issue=0,
            now="2026-07-16T10:00:00")
    with get_connection(db) as c:
        row = get_attendance(c, employee_id=_emp(c), tanggal="2026-05-06")
    assert row["keluar"] == "16:05" and row["has_issue"] == 0
    assert row["manual_edited_at"] == "2026-07-16T10:00:00"
    assert row["reason_category"] == "izin_sakit"   # preserved

def test_import_upsert_clears_manual_flag(tmp_path):
    db = tmp_path/"hr.db"; init_db(db)
    with get_connection(db) as c:
        eid=_emp(c)
        save_manual_attendance(c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
            kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0, has_issue=0,
            now="2026-07-16T10:00:00")
    with get_connection(db) as c:
        eid=_emp(c)
        upsert_attendance(c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar=None,
            kerja_jam=0.0, lembur_jam=0.0, terlambat_menit=0, has_issue=1,
            imported_from="f2.xls")
    with get_connection(db) as c:
        row = get_attendance(c, employee_id=_emp(c), tanggal="2026-05-06")
    assert row["manual_edited_at"] is None      # import overwrite → flag cleared

def test_delete_attendance(tmp_path):
    db=tmp_path/"hr.db"; init_db(db)
    with get_connection(db) as c:
        eid=_emp(c)
        save_manual_attendance(c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0)
        delete_attendance(c, employee_id=eid, tanggal="2026-05-06")
        assert get_attendance(c, employee_id=eid, tanggal="2026-05-06") is None
```

- [ ] **Step 2: Run — expect fail**
- [ ] **Step 3: Implement** in `src/db/attendance.py`:
  - Add `manual_edited_at = NULL` to the `ON CONFLICT ... DO UPDATE SET` of `upsert_attendance` (import overwrite → row becomes import-owned).
  - Add:

```python
def get_attendance(conn, *, employee_id, tanggal):
    row = conn.execute(
        "SELECT * FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (employee_id, tanggal)).fetchone()
    return dict(row) if row else None

def save_manual_attendance(conn, *, employee_id, tanggal, hari, tipe, jadwal,
                           masuk, keluar, kerja_jam, lembur_jam, terlambat_menit,
                           has_issue, now=None):
    ts = now or datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute("""
        INSERT INTO attendance_records (employee_id, tanggal, hari, tipe, jadwal,
            masuk, keluar, kerja_jam, lembur_jam, terlambat_menit, has_issue,
            manual_edited_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(employee_id, tanggal) DO UPDATE SET
            hari=excluded.hari, tipe=excluded.tipe, jadwal=excluded.jadwal,
            masuk=excluded.masuk, keluar=excluded.keluar, kerja_jam=excluded.kerja_jam,
            lembur_jam=excluded.lembur_jam, terlambat_menit=excluded.terlambat_menit,
            has_issue=excluded.has_issue, manual_edited_at=excluded.manual_edited_at
        """, (employee_id, tanggal, hari, tipe, jadwal, masuk, keluar,
              kerja_jam, lembur_jam, terlambat_menit, has_issue, ts))

def delete_attendance(conn, *, employee_id, tanggal):
    conn.execute("DELETE FROM attendance_records WHERE employee_id=? AND tanggal=?",
                 (employee_id, tanggal))

def manual_rows_for_import(conn, no_staff_list, start, end):
    """{(no_staff, tanggal): {nama, tipe, jadwal, masuk, keluar, kerja_jam,
    lembur_jam, terlambat_menit}} for manual-edited rows in range for these staff."""
    if not no_staff_list:
        return {}
    qs = ",".join("?" * len(no_staff_list))
    rows = conn.execute(f"""
        SELECT e.no_staff, e.nama, ar.tanggal, ar.tipe, ar.jadwal, ar.masuk, ar.keluar,
               ar.kerja_jam, ar.lembur_jam, ar.terlambat_menit
          FROM attendance_records ar JOIN employees e ON ar.employee_id=e.id
         WHERE ar.manual_edited_at IS NOT NULL AND ar.tanggal BETWEEN ? AND ?
           AND e.no_staff IN ({qs})""",
        [start, end, *no_staff_list]).fetchall()
    return {(r["no_staff"], r["tanggal"]): dict(r) for r in rows}
```

- [ ] **Step 4: Run — expect pass** (+ full suite) — [ ] **Step 5: Commit** `git commit -am "feat(v23): editor DB layer + upsert clears manual flag"`

### Task 8: Dialog editor + hook Heatmap

**Files:** Create `src/ui/components/attendance_edit_dialog.py`; Modify `src/ui/screens/heatmap.py`

- [ ] **Step 1:** Implement `AttendanceEditDialog(CTkToplevel)` following the `BatchResolveDialog` pattern (transient, `after(50, grab_set+focus)`, Escape/Return, `WM_DELETE_WINDOW`, `_regrab` after nested feedback dialogs). Constructor: `(parent, *, employee_id, nama, tanggal, on_saved, on_deleted)`.
  - Read setting `schedule_start/end` once (`get_setting`), load existing row via `get_attendance`.
  - Fields: `tipe` (`CTkOptionMenu` ["Hari Kerja","Hari Libur","Istirahat"]), `masuk`, `keluar` (`CTkEntry`), `jadwal` (`CTkEntry`, hint label).
  - Auto box: labels for Status/Telat/Kerja/Lembur; `_recompute_preview()` binds to field changes (OptionMenu `command`, entries `<KeyRelease>`), calls `attendance_calc.recompute(...)` and updates labels + pill.
  - Override section (collapsible frame; a toggle label flips visibility); 3 entries pre-filled from computed values.
  - Footer: `Hapus baris` (only if row exists) · `Batal` · `Simpan`.
  - `_save()`: validate `masuk`/`keluar` (`to_minutes` not None when non-empty) else `feedback.show_warning` + `_regrab`; compute derived (override values win if override open + non-empty); `with get_connection(DB_PATH) as c: save_manual_attendance(...)`; `notify_data_changed()`; `self.destroy()`; `on_saved()`.
  - `_delete()`: `feedback.ask_yes_no` → `backup.create_backup(DB_PATH, reason="hapus")` → `delete_attendance` → `notify_data_changed()` → destroy → `on_deleted()`.
- [ ] **Step 2:** In `heatmap.py._paint_grid`, when mapping each cell also record edit target:

```python
tgl = f"{self._month}-{day:02d}"
self._edit_by_item[rid] = self._edit_by_item[tid] = {
    "employee_id": e["employee_id"], "tanggal": tgl, "nama": e["nama"]}
```
  Init `self._edit_by_item = {}` in `__init__` and reset it in `_repaint` (next to `_cell_by_item`).
- [ ] **Step 3:** Change `_on_cell_click` to open the dialog:

```python
def _on_cell_click(self, _event):
    item = self._canvas.find_withtag("current")
    target = self._edit_by_item.get(item[0]) if item else None
    cell = self._current_cell()
    if cell:
        self._show_detail(cell)          # keep strip update
    if target:
        from src.ui.components.attendance_edit_dialog import AttendanceEditDialog
        AttendanceEditDialog(self.winfo_toplevel(),
            employee_id=target["employee_id"], nama=target["nama"],
            tanggal=target["tanggal"], on_saved=self._load, on_deleted=self._load)
```

- [ ] **Step 4: Smoke** — `tests/test_attendance_edit_dialog.py` (skip if no Tk): build a temp DB with one employee, open dialog headless, call `_recompute_preview` with masuk/keluar set, assert the preview dict equals `recompute(...)`; do NOT enter mainloop.
- [ ] **Step 5: Run** screen tests separately — [ ] **Step 6: Commit** `git add -A && git commit -m "feat(v23): attendance edit dialog + Heatmap click-to-edit"`

---

## Phase C — Resolusi konflik import

### Task 9: Deteksi konflik (murni)

**Files:** Create `src/core/import_conflicts.py`; Test `tests/test_import_conflicts.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_import_conflicts.py
from types import SimpleNamespace
from src.core.import_conflicts import find_conflicts

def _row(**kw):
    base = dict(no_staff="S1", tanggal="2026-05-06", hari="Rabu", tipe="Hari Kerja",
                jadwal="", masuk="08:00", keluar=None, kerja_jam=0.0, lembur_jam=0.0,
                terlambat_menit=0)
    base.update(kw); return SimpleNamespace(**base)

def test_conflict_when_manual_row_differs():
    pending = [_row(keluar=None)]
    existing = {("S1","2026-05-06"): {"nama":"Budi","tipe":"Hari Kerja","jadwal":"",
        "masuk":"08:00","keluar":"16:05","kerja_jam":8.1,"lembur_jam":0.1,"terlambat_menit":0}}
    c = find_conflicts(pending, existing)
    assert len(c) == 1 and "keluar" in c[0]["changed"] and c[0]["nama"] == "Budi"

def test_no_conflict_when_identical():
    pending = [_row(keluar="16:05", kerja_jam=8.1, lembur_jam=0.1)]
    existing = {("S1","2026-05-06"): {"nama":"Budi","tipe":"Hari Kerja","jadwal":"",
        "masuk":"08:00","keluar":"16:05","kerja_jam":8.1,"lembur_jam":0.1,"terlambat_menit":0}}
    assert find_conflicts(pending, existing) == []

def test_no_conflict_when_not_manual():
    assert find_conflicts([_row()], {}) == []   # nothing marked manual → no prompt
```

- [ ] **Step 2: Run — expect fail**
- [ ] **Step 3: Implement**

```python
# src/core/import_conflicts.py
"""Pure detection of import-vs-manual conflicts. A conflict = an incoming row
whose (no_staff, tanggal) matches a manual-edited existing row AND any watched
field differs. Rows without a manual match never conflict (imported silently)."""
CONFLICT_FIELDS = ("tipe", "jadwal", "masuk", "keluar",
                   "kerja_jam", "lembur_jam", "terlambat_menit")

def _differ(a, b):
    if a is None and b is None:
        return False
    try:
        if a is not None and b is not None and float(a) == float(b):
            return False
    except (TypeError, ValueError):
        pass
    return (a or None) != (b or None)

def find_conflicts(pending_rows, existing_manual):
    out = []
    for r in pending_rows:
        ex = existing_manual.get((r.no_staff, r.tanggal))
        if not ex:
            continue
        changed = [f for f in CONFLICT_FIELDS if _differ(getattr(r, f, None), ex.get(f))]
        if changed:
            out.append({
                "key": (r.no_staff, r.tanggal), "no_staff": r.no_staff,
                "nama": ex.get("nama"), "tanggal": r.tanggal, "hari": getattr(r, "hari", None),
                "manual": {f: ex.get(f) for f in CONFLICT_FIELDS},
                "incoming": {f: getattr(r, f, None) for f in CONFLICT_FIELDS},
                "changed": changed})
    return out
```

- [ ] **Step 4: Run — expect pass** — [ ] **Step 5: Commit** `git add -A && git commit -m "feat(v23): import conflict detection (pure)"`

### Task 10: Jendela konflik + alur import

**Files:** Create `src/ui/components/import_conflict_dialog.py`; Modify `src/ui/screens/import_screen.py`

- [ ] **Step 1:** Implement `ImportConflictDialog(CTkToplevel)` (BatchResolveDialog pattern, header/scroll-content/footer). Constructor `(parent, *, conflicts, file_label, non_conflict_count, on_resolved)`.
  - Per conflict → card: header `{nama} · {hari}, {format tanggal}`; 2-col diff (Manual cyan / Import amber), changed fields highlighted; a per-row toggle stored in `self._choice[key]` (`ctk.StringVar` "keep"/"take", default "keep") rendered as two clickable option labels.
  - Bulk buttons set all vars to keep/take.
  - Footer: `Batal impor` (→ `on_resolved(None)`) · `Terapkan & lanjut import` (→ `on_resolved({key: var.get()})`).
- [ ] **Step 2:** In `import_screen.py`, extend the confirm path:
  - `run_import_confirm(db_path, rows, resolution=None, progress=None)`: at start `backup.create_backup(db_path, reason="import")`. In the loop, `key=(r.no_staff, r.tanggal)`; if `resolution and resolution.get(key)=="keep"`: `continue` (skip attendance upsert; still safe). Else upsert as today.
  - `_on_confirm`: before dispatching, build conflicts:

```python
with get_connection(DB_PATH) as conn:
    no_staff = list({r.no_staff for r in rows})
    dates = sorted({r.tanggal for r in rows})
    existing = manual_rows_for_import(conn, no_staff, dates[0], dates[-1])
conflicts = find_conflicts(rows, existing)
if conflicts:
    ImportConflictDialog(self.winfo_toplevel(), conflicts=conflicts,
        file_label=..., non_conflict_count=len(rows)-len(conflicts),
        on_resolved=lambda res: self._proceed_confirm(rows, res))
    return
self._proceed_confirm(rows, {})
```
  - `_proceed_confirm(rows, resolution)`: if `resolution is None` → release guard, abort. Else run the existing `run_bg(... run_import_confirm(DB_PATH, rows, resolution, progress) ...)`.
- [ ] **Step 3: Test** — extend `tests/test_import_confirm*.py` (or new) to call `run_import_confirm` with a `resolution={("S1","2026-05-06"):"keep"}` and assert the manual row is untouched while a non-conflict row is written; assert a backup file appears in `data/backups` (temp DB).
- [ ] **Step 4: Run** (+ full suite) — [ ] **Step 5: Commit** `git add -A && git commit -m "feat(v23): import conflict dialog + resolution-aware confirm + pre-import backup"`

---

## Release

### Task 11: Version bump + changelog

**Files:** Modify `src/config.py`; Test `tests/test_changelog_v23_0_0.py`

- [ ] **Step 1: Failing test** — retention-style: assert an entry with version "23.0.0", date "2026-07-16", kinds include "feat", blob contains "Edit Data"/"Backup"/"konflik".
- [ ] **Step 2:** Set `APP_VERSION="23.0.0"`, `APP_BUILD_DATE="2026-07-16"`, prepend `APP_CHANGELOG` entry (Indonesian, action-oriented):
  - feat: Menu Edit Data — klik sel Heatmap untuk edit/tambah/hapus absensi; jam telat, status, jam kerja & lembur dihitung otomatis.
  - feat: Backup & Restore di Settings — snapshot otomatis sebelum import & hapus, plus backup manual; simpan 1 tahun terakhir.
  - feat: Saat import menimpa data yang pernah disunting manual, muncul jendela konfirmasi per-baris (pertahankan vs pakai import).
- [ ] **Step 3: Run** changelog test + `test_config`/`test_about` if any — [ ] **Step 4: Commit** `git commit -am "chore(release): APP_VERSION 23.0.0 + changelog"`

### Task 12: Full suite green → build → rotate → Installers → smoke → push

- [ ] **Step 1:** Full suite: `../../../.venv/Scripts/python.exe -m pytest -q --ignore-glob='*screen*'` then screen tests separately. All green.
- [ ] **Step 2:** Verify prod DB md5 baseline; ensure `HR-Absensi.exe` not running (`tasklist | grep -i HR-Absensi`).
- [ ] **Step 3:** Build per workflow_rules Rule 2 (main-repo, prodhold pattern): `Move-Item dist/HR-Absensi dist/HR-Absensi.prodhold` → `python -m tools.build_installer` → rotate `.exe`+`_internal` 2-level inside prodhold → drop fresh build dir → `Move-Item prodhold → dist/HR-Absensi`. **`data/` never leaves its folder.**
- [ ] **Step 4:** Copy installer → `D:\Gawe\Project X\HR App\Installers\HR-Absensi-Setup-v23.0.0.exe`.
- [ ] **Step 5:** Data-safe launch smoke (move prod DB aside), verify md5 unchanged after.
- [ ] **Step 6:** Commit any release artifacts note; push: `GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe" git push origin v23.0.0` then advance `latest`: `... git push origin v23.0.0:latest`.
- [ ] **Step 7:** Update `memory/version_state.md`.

---

## Self-review notes
- Spec coverage: B (Tasks 1–4), A (5–8), C (9–10), release (11–12) — all §-mapped.
- `manual_edited_at` cleared on import overwrite (Task 7) is what makes "take" work without extra code in the confirm loop; "keep" = skip.
- Data safety: every DB test uses `tmp_path`; build uses prodhold; smoke moves prod DB aside; md5 verified. Prod `hr.db` never written without explicit action.
