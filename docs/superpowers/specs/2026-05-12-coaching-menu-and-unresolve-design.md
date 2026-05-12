# Coaching Menu + Issues Unresolve — Design Spec

**Tanggal:** 2026-05-12
**Status:** Draft (menunggu approval user)
**Author:** Brainstorming session

---

## 1. Konteks & Problem

Dua workflow gap yang belum ter-cover di app:

**Gap 1: Coaching tracking.** Dashboard punya panel "Butuh Coaching" yang nampilin
list pegawai yang lewat threshold (75 mnt/minggu late). Tapi tidak ada cara untuk
mark "sudah di-coaching", jadi info-nya repetitif tiap kali user buka Dashboard.
User butuh menu khusus untuk track WHO has been coached this week.

**Gap 2: Mistaken resolve di Issues.** Saat resolve issue, kalau user salah pilih
kategori atau salah baris, tidak ada undo. Mereka harus manual hapus dari DB
(impossible) atau hidup dengan kesalahan. User butuh tombol "Batalkan Resolve"
untuk safety net.

---

## 2. Goals & Non-Goals

### Goals
- Menu baru **🎯 Coaching** (sidebar item ke-7, antara Riwayat Bulan dan Settings)
- Tracking per `(employee, week)` siapa sudah di-coaching
- One-click toggle status (Belum ↔ Sudah)
- Optional notes per coaching session
- Tombol **"Batalkan Resolve"** di Issues right panel untuk unresolve

### Non-Goals
- Tidak ada Bulanan view di Coaching screen (mingguan saja — user request)
- Tidak ada cross-month coaching aggregate (untuk lihat bulan lalu, switch via Riwayat Bulan)
- Tidak ada notification / reminder untuk coaching pending
- Tidak ada export Coaching status ke Excel (Dashboard sudah ada Coaching panel di print PDF)
- Notes tidak mandatory, tidak ada validation rules
- Tidak ada unresolve di Coaching (toggle Sudah→Belum sudah cover ini)
- Tidak ada bulk-unresolve di Issues (one-by-one cukup)

---

## 3. UI/UX Design — Coaching Screen

### 3.1 Sidebar position
```
1. Dashboard
2. Import
3. Issues
4. Summary
5. Export
6. Riwayat Bulan
7. 🎯 Coaching       ← BARU
8. Settings
```

### 3.2 Screen layout (mirror Issues pattern)

```
┌─ Coaching ────────────────────────────────────────────────────────┐
│ [M1] [M2] [M3] [M4] [M5]                                          │
│                                                                   │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │
│ │ TOTAL      │ │ SUDAH      │ │ BELUM      │ │ COVERAGE   │       │
│ │   5        │ │   2        │ │   3        │ │   40%      │       │
│ │ butuh coach│ │ tercoach   │ │ pending    │ │            │       │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘       │
│                                                                   │
│ ┌─ Table (2/3) ───────────────────────────┐ ┌─ Notes panel (1/3)─┐│
│ │ NAMA │ DEPT │ TERLAMBAT │ STATUS  │ AKSI│ │ (kosong, pilih row)││
│ │ ──── ┼ ──── ┼ ────────── ┼ ─────── ┼─────│ │                    ││
│ │ AND  │ A    │ 87 mnt    │ ○ Belum │ ⊕ Tandai │ │              ││
│ │ YAS  │ B    │ 92 mnt    │ ✓ Sudah │ ⊖ Batalkan │ │            ││
│ └─────────────────────────────────────────┘ └────────────────────┘│
└───────────────────────────────────────────────────────────────────┘
```

### 3.3 WeekNavBar
- **Pills**: M1, M2, M3, M4, M5 (dynamic per `weeks_in_month`)
- **No "Semua"** — coaching is weekly-meaningful only
- **Default selected**: minggu paling akhir yang punya data attendance (fallback M1)
- Component: reuse existing `WeekNavBar` dengan parameter baru `include_all=False`

### 3.4 KPI cards (4 cards, all per-week)

| Card | Value | Subtitle |
|---|---|---|
| **TOTAL** | count pegawai over threshold di minggu ini | "butuh coach" |
| **SUDAH** | count yang ada coaching_sessions row | "tercoach" |
| **BELUM** | TOTAL − SUDAH | "pending" |
| **COVERAGE** | round(SUDAH / TOTAL × 100) % | "" |

If TOTAL=0: COVERAGE = "—".

### 3.5 Table (ttk.Treeview)

**Columns:**
| Col | Width | Content |
|---|---|---|
| Nama | 130 | `employees.nama` |
| Dept | 100 | `employees.dept` |
| Terlambat | 90 | "87 mnt" — total terlambat minggu ini, excluding work-justified |
| Status | 100 | "○ Belum" (warn color) atau "✓ Sudah" (ok color) |
| Aksi | 110 | "⊕ Tandai" atau "⊖ Batalkan" — clickable trigger |

**Row tinting via Treeview tags:**
- `tag="belum"` → fieldbackground tint `#3F2A2C` (subtle warm) + foreground `COLOR_TEXT`
- `tag="sudah"` → fieldbackground tint `#2A3F30` (subtle cool) + foreground `COLOR_TEXT`

**Sort:** Terlambat DESC, then Nama ASC.

### 3.6 Interactions

**A) Click on AKSI column:** Toggle status (one-click, no panel needed)
- Belum → Sudah: INSERT coaching_sessions(employee_id, week_start, coached_at=now, notes=NULL)
- Sudah → Belum: DELETE coaching_sessions row
- Refresh table + KPI
- No confirmation dialog (user explicitly requested one-click; toggle is reversible)

**B) Click on any other column / row body:** Open right panel for notes
- Right panel content:
  ```
  ANDIKA (A)
  Minggu 1 (1–5 April 2026)
  Total terlambat: 87 mnt
  Status: ✓ Sudah Coaching (15 April 2026 14:32)

  Catatan (opsional):
  ┌─────────────────────────────────┐
  │ Diskusi sudah dilakukan,        │
  │ pegawai paham target jam datang │
  │                                 │
  └─────────────────────────────────┘
  [Simpan Catatan]
  ```
- For "Belum" rows: panel shows status info BUT note field is grayed out with hint
  "Tandai Sudah Coaching dulu untuk simpan catatan."
- Notes only persisted on coaching_sessions row, so Belum rows can't have notes
- Right panel shows when row selected, hides when no row selected (default state)

### 3.7 Empty state

If no pegawai over threshold this week:
```
┌─────────────────────────────────────────────┐
│ ✓ Tidak ada yang butuh coaching minggu ini. │
│ Threshold: 75 mnt/minggu                    │
└─────────────────────────────────────────────┘
```

### 3.8 Click handler implementation

`tree.bind("<Button-1>", _on_click)`:
```python
def _on_click(self, event):
    region = self.tree.identify_region(event.x, event.y)
    if region != "cell":
        return
    column = self.tree.identify_column(event.x)
    row_iid = self.tree.identify_row(event.y)
    if not row_iid:
        return
    if column == "#5":  # AKSI column
        self._toggle_status(row_iid)
        return "break"   # prevent selection event
    # else: let default selection happen, _on_select will fire
```

`tree.bind("<<TreeviewSelect>>", _on_select)` handles right panel population.

---

## 4. UI/UX Design — Issues Unresolve

### 4.1 Right panel addition

When a row from **Resolved** Treeview is selected, right panel renders the existing
form (kategori + detail + Save) PLUS a new button below:

```
ANDIKA (A)
Senin, 13 April 2026
Masuk: 08.06   Keluar: 16.41

Kategori alasan:
[Izin Sakit ▼]

Detail:
[                    ]

[Simpan]                ← existing
[↶ Batalkan Resolve]    ← BARU, fg_color=COLOR_ERR, secondary visual
```

For rows from **Open** table: button NOT shown (only Save).

### 4.2 Behavior

**Click "Batalkan Resolve":**
1. Confirm dialog:
   ```
   Konfirmasi: Batalkan resolve?
   Kategori dan detail alasan akan dihapus.
   Issue akan kembali ke status Open.
   [Batal] [Ya, Batalkan]
   ```
2. On confirm: `UPDATE attendance_records SET reason_category=NULL, reason_detail=NULL, resolved_at=NULL WHERE id=?`
3. Reload Issues table → row pindah dari Resolved ke Open
4. Right panel kembali ke empty state
5. No toast (visual reload sudah cukup feedback)

---

## 5. Data Model

### 5.1 New table

```sql
CREATE TABLE coaching_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    week_start  TEXT    NOT NULL,         -- ISO date of Monday (e.g., "2026-04-06")
    coached_at  DATETIME NOT NULL,        -- when user clicked Tandai
    notes       TEXT,                     -- optional, NULL by default
    UNIQUE (employee_id, week_start)
);
```

Migration: add `CREATE TABLE IF NOT EXISTS coaching_sessions ...` to `src/db/schema.py:DDL`.
Existing DBs auto-create on first run via `init_db`. No data migration needed
(empty table on fresh install).

### 5.2 No schema change for Issues unresolve

Uses existing `reason_category`, `reason_detail`, `resolved_at` fields — just `UPDATE ... SET ... = NULL`.

---

## 6. Core Logic

### 6.1 `src/db/coaching.py` (new module)

```python
import sqlite3
from datetime import datetime, UTC
from typing import Optional


def mark_coached(conn, *, employee_id: int, week_start: str,
                 notes: Optional[str] = None) -> None:
    """Insert or update coaching session (idempotent — UPSERT)."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO coaching_sessions (employee_id, week_start, coached_at, notes)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (employee_id, week_start) DO UPDATE SET
            notes = excluded.notes
        """,
        (employee_id, week_start, now, notes),
    )


def unmark_coached(conn, *, employee_id: int, week_start: str) -> None:
    """Delete coaching session — toggles Sudah back to Belum."""
    conn.execute(
        "DELETE FROM coaching_sessions WHERE employee_id = ? AND week_start = ?",
        (employee_id, week_start),
    )


def get_coaching_notes(conn, *, employee_id: int, week_start: str) -> Optional[str]:
    """Return notes for a session, or None if no session exists."""
    row = conn.execute(
        "SELECT notes FROM coaching_sessions WHERE employee_id = ? AND week_start = ?",
        (employee_id, week_start),
    ).fetchone()
    return row["notes"] if row else None


def update_notes(conn, *, employee_id: int, week_start: str, notes: Optional[str]) -> None:
    """Update notes of an existing session (must exist — Sudah status)."""
    conn.execute(
        """
        UPDATE coaching_sessions
           SET notes = ?
         WHERE employee_id = ? AND week_start = ?
        """,
        (notes, employee_id, week_start),
    )
```

### 6.2 Coaching query — `src/db/coaching.py` continued

```python
def list_coaching_for_week(conn, *, week_start: str, week_end: str,
                           threshold_minutes: int = 75):
    """Return rows for pegawai over threshold in given week, with coaching status.

    Uses existing terlambat aggregation logic (excludes work-justified categories).
    Joins with coaching_sessions to determine status.

    Returns sqlite3.Row with columns:
      - employee_id, nama, dept, no_staff
      - total_terlambat (int, minutes)
      - week_start (echo)
      - coached_at (DATETIME or NULL)
      - is_coached (1 or 0)
    """
    return conn.execute(
        """
        WITH terlambat AS (
            SELECT
                ar.employee_id,
                SUM(CASE
                    WHEN ar.reason_category IN ('tugas_lapangan', 'tugas_paparan', 'terlambat_kerja')
                        THEN 0
                    WHEN ar.masuk IS NULL THEN 0
                    ELSE COALESCE(ar.terlambat_menit, 0)
                END) AS total_terlambat
              FROM attendance_records ar
             WHERE ar.tanggal BETWEEN ? AND ?
             GROUP BY ar.employee_id
        )
        SELECT
            t.employee_id,
            e.nama,
            e.dept,
            e.no_staff,
            t.total_terlambat,
            ? AS week_start,
            cs.coached_at,
            CASE WHEN cs.id IS NOT NULL THEN 1 ELSE 0 END AS is_coached
          FROM terlambat t
          JOIN employees e ON t.employee_id = e.id
          LEFT JOIN coaching_sessions cs
                 ON cs.employee_id = t.employee_id
                AND cs.week_start = ?
         WHERE t.total_terlambat > ?
         ORDER BY t.total_terlambat DESC, e.nama ASC
        """,
        (week_start, week_end, week_start, week_start, threshold_minutes),
    ).fetchall()
```

### 6.3 Unresolve function — `src/db/attendance.py` (append)

```python
def unresolve_issue(conn: sqlite3.Connection, *, attendance_id: int) -> None:
    """Clear resolve state for an attendance row.

    Sets reason_category, reason_detail, resolved_at all to NULL. Used by the
    Issues 'Batalkan Resolve' button.
    """
    conn.execute(
        """
        UPDATE attendance_records
           SET reason_category = NULL,
               reason_detail = NULL,
               resolved_at = NULL
         WHERE id = ?
        """,
        (attendance_id,),
    )
```

---

## 7. UI Components

### 7.1 WeekNavBar parameter

Existing `src/ui/components/week_nav.py` adds `include_all: bool = True` parameter.
- `WeekNavBar(parent, current_month=..., on_change=..., initial="semua")` — unchanged for Dashboard/Issues
- `WeekNavBar(parent, current_month=..., on_change=..., initial="w_1", include_all=False)` — new for Coaching

When `include_all=False`: "Semua" pill not rendered, initial selection must be a week key.

### 7.2 Coaching Treeview style

Add to `src/ui/screens/coaching.py` `_setup_treeview_style()`:
```python
style.configure(
    "Coaching.Treeview",
    background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
    foreground=COLOR_TEXT, rowheight=28, borderwidth=0,
)
style.configure(
    "Coaching.Treeview.Heading",
    background="#2C1B47", foreground=COLOR_TEXT_DIM,
    relief="flat", font=(FONT_FAMILY, 10, "bold"),
)
# Tag-based row tinting
self.tree.tag_configure("belum", background="#3F2A2C", foreground=COLOR_TEXT)
self.tree.tag_configure("sudah", background="#2A3F30", foreground=COLOR_TEXT)
```

(Tag configure is called on the Treeview instance, not via Style.)

---

## 8. Testing

### 8.1 Unit tests (TDD)

| Test file | Coverage |
|---|---|
| `tests/test_coaching_db.py` | (1) `mark_coached` inserts row. (2) `mark_coached` is idempotent (UPSERT — second call updates notes). (3) `unmark_coached` deletes row. (4) `get_coaching_notes` returns None for nonexistent. (5) `update_notes` updates only notes. (6) `list_coaching_for_week` returns over-threshold pegawai with correct is_coached flag (mix of Belum + Sudah). (7) `list_coaching_for_week` respects work-justified exclusion (tugas_lapangan etc.). (8) `list_coaching_for_week` requires masuk IS NOT NULL. |
| `tests/test_unresolve_issue.py` | (1) `unresolve_issue` clears 3 fields. (2) Unresolve doesn't touch other rows. (3) Unresolve idempotent (calling on already-NULL is no-op). |

Target: ~11 new tests.

### 8.2 Manual smoke test

1. Launch new .exe
2. Sidebar shows 8 items including 🎯 Coaching
3. Click Coaching → table shows pegawai over threshold for current week
4. Click "Tandai" on a "Belum" row → status flips to "✓ Sudah", row re-tinted green
5. Click "Batalkan" on a "Sudah" row → status flips back to "○ Belum"
6. Click row body (not AKSI col) → right panel shows status + notes field
7. For "Sudah" row: type note, click "Simpan Catatan" → persists, re-show panel shows note
8. For "Belum" row: notes field grayed out with hint
9. Switch weeks via WeekNavBar — coaching list updates
10. Go to Riwayat Bulan, switch to past month → Coaching screen for that month
11. Issues → click resolved row → right panel shows "Batalkan Resolve" button
12. Click button → confirm dialog → row moves to Open table

---

## 9. Risks & Edge Cases

| Risk | Mitigation |
|---|---|
| Pegawai over threshold this week, get coached, then re-import fingerprint changes masuk times → total_terlambat drops below threshold | Coaching record persists. Query filters by `total_terlambat > threshold`, so they fall out of list. Notes preserved in DB. If user re-toggles threshold, they re-appear. No data loss. |
| User clicks AKSI rapidly (double-click) | First click toggles, second click toggles back. Net effect: same as before. No transaction issues. |
| Notes textarea long content | TEXT column has no length limit. Treeview row not affected (notes shown in right panel only). |
| Week_start ISO date — what format exactly? | `weeks_in_month` returns ISO date strings already. Match that. |
| Empty current_month setting | Coaching screen shows empty state ("Tidak ada bulan aktif. Import fingerprint dulu.") |
| `Bulan Aktif` setting changes mid-session | Screen re-instantiation on nav reads fresh value. Consistent with Dashboard/Issues. |
| Unresolve removes user's typed notes accidentally | reason_category/detail are different from coaching notes. Unresolve only affects Issues' reason fields. Coaching notes safe. |
| Click AKSI column but slightly off → row selected instead | UX: minor. Right panel pops up. User clicks AKSI again. No data risk. |

---

## 10. Definition of Done

- [ ] `coaching_sessions` table created via `init_db` (idempotent CREATE TABLE IF NOT EXISTS)
- [ ] `src/db/coaching.py` module with all 5 functions (`mark_coached`, `unmark_coached`, `get_coaching_notes`, `update_notes`, `list_coaching_for_week`)
- [ ] `src/db/attendance.py` adds `unresolve_issue` function
- [ ] `src/ui/screens/coaching.py` — CoachingScreen with all behaviors (WeekNavBar, KPI, Treeview + tags, click handlers, right panel notes)
- [ ] `src/ui/components/week_nav.py` — `include_all` parameter added
- [ ] `src/ui/screens/issues.py` — "Batalkan Resolve" button in right panel (conditional on resolved row selected)
- [ ] `src/ui/app.py` — Coaching menu item registered between Riwayat Bulan and Settings (sidebar has 8 items)
- [ ] ~11 new tests passing, 86 existing tests still passing
- [ ] Manual smoke test pass (all 12 steps in Section 8.2)
- [ ] No visual regression in other screens (Dashboard/Issues/etc.)

---

## 11. Out of Scope (future ideas)

- Bulk coaching mark (e.g., "Mark all this week as coached")
- Export coaching status to CSV/PDF
- Coaching history page (cross-month view of who's been coached when)
- Reminder/notification for pending coaching at end of week
- Coaching templates (pre-filled notes)
- Bulk unresolve di Issues
- Audit log untuk unresolve actions

---

*End of spec.*
