# Print Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 5 broken print themes with 1 working "Light" theme, refresh panel composition (Pola Jam Masuk replaces Hari Rawan + Ranking Departemen, KPI strip becomes 4-card with Rata-rata Min/Kejadian + Teladan), and fix print dialog overflow (compact 560×440 centered on screen).

**Architecture:** Single Jinja template `dashboard.html.j2` rewritten for 2-page A4 print on white paper with JTS palette (magenta/cyan/violet/emerald). Renderer simplified to drop `template_name` and removed-panel computations; adds 2 new insight functions (`avg_minutes_per_late_event`, `pola_jam_masuk`) and extends `terlambat_ranking` with `absent_count` per emp. Dialog refactored to remove theme picker, resized to fit small laptops, centered on screen with max-height clamp.

**Tech Stack:** Python 3.13 · SQLite · Jinja2 · CustomTkinter · pytest

**Spec:** [2026-05-13-print-dashboard-redesign-design.md](../specs/2026-05-13-print-dashboard-redesign-design.md)

---

## Phase 0 — Worktree Setup

Bring this v1-era worktree up to v6 codebase before any changes. The spec commit lives on this branch and must be replayed on top of v6.

### Task 0.1: Fetch and rebase onto v6

**Files:** working tree only

- [ ] **Step 1: Fetch latest origin refs**

Run: `git fetch origin`
Expected: refs updated, no error.

- [ ] **Step 2: Verify current branch state**

Run: `git status && git log --oneline -3`
Expected: clean working tree, HEAD is the spec commit (`2428b01 docs(spec): print dashboard redesign — Light theme + compact dialog`) on top of v1-era commits.

- [ ] **Step 3: Rebase onto origin/v6**

Run: `git rebase origin/v6`
Expected: spec commit replays cleanly on v6 (the spec is a new file in `docs/superpowers/specs/`, no conflict possible). If conflict appears, abort with `git rebase --abort` and investigate.

- [ ] **Step 4: Verify v6 file structure is now present**

Run: `git ls-files src/core/ src/db/ src/reports/templates/ | head -25`
Expected: see `src/core/coaching.py`, `src/core/filename_parser.py`, `src/db/coaching.py`, `src/db/export_history.py`, `src/reports/templates/dashboard.html.j2`, `dashboard_v1_editorial.html.j2`, etc. (v6 files, not just v1 stub).

- [ ] **Step 5: Install dev deps fresh (in case new deps from v6)**

Run: `../../../.venv/Scripts/pip.exe install -r requirements-dev.txt`
Expected: all installs succeed including `windnd>=1.0.7` added in v6.

### Task 0.2: Baseline test run

**Files:** none

- [ ] **Step 1: Run full test suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: 120 passed (v6 baseline).
If count differs from 120, STOP and investigate before continuing — the plan assumes v6 baseline.

- [ ] **Step 2: Note baseline**

Record the exact count (should be 120) as the starting point. New target after this plan: ~124 passing.

---

## Phase 1 — Insights Layer

Three insight functions in [src/core/insights.py](src/core/insights.py): one new average, one new distribution, one extension to existing ranking.

### Task 1.1: Add `avg_minutes_per_late_event`

**Files:**
- Modify: `src/core/insights.py` (append new function)
- Test: `tests/test_insights.py` (append new tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_insights.py`:

```python
def test_avg_minutes_per_late_event_empty(empty_conn):
    """No late events → returns 0.0"""
    from src.core.insights import avg_minutes_per_late_event
    result = avg_minutes_per_late_event(empty_conn, '2026-04-01', '2026-04-30')
    assert result == 0.0


def test_avg_minutes_per_late_event_single(conn_with_attendance):
    """One late event of 10 min → returns 10.0"""
    from src.core.insights import avg_minutes_per_late_event
    conn = conn_with_attendance(rows=[
        {'nama': 'A', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:10', 'keluar': '17:00', 'terlambat_menit': 10},
    ])
    result = avg_minutes_per_late_event(conn, '2026-04-01', '2026-04-30')
    assert result == 10.0


def test_avg_minutes_per_late_event_multi(conn_with_attendance):
    """Three events 10+20+30 across 2 emp → avg 20.0"""
    from src.core.insights import avg_minutes_per_late_event
    conn = conn_with_attendance(rows=[
        {'nama': 'A', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:10', 'keluar': '17:00', 'terlambat_menit': 10},
        {'nama': 'A', 'tanggal': '2026-04-14', 'tipe': 'Hari Kerja',
         'masuk': '08:20', 'keluar': '17:00', 'terlambat_menit': 20},
        {'nama': 'B', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:30', 'keluar': '17:00', 'terlambat_menit': 30},
    ])
    result = avg_minutes_per_late_event(conn, '2026-04-01', '2026-04-30')
    assert result == 20.0


def test_avg_minutes_per_late_event_zero_excluded(conn_with_attendance):
    """terlambat_menit=0 (on time) not counted as an event"""
    from src.core.insights import avg_minutes_per_late_event
    conn = conn_with_attendance(rows=[
        {'nama': 'A', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:10', 'keluar': '17:00', 'terlambat_menit': 10},
        {'nama': 'B', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:00', 'keluar': '17:00', 'terlambat_menit': 0},
    ])
    result = avg_minutes_per_late_event(conn, '2026-04-01', '2026-04-30')
    assert result == 10.0
```

Note: `empty_conn` and `conn_with_attendance` are existing fixtures in `tests/conftest.py`. If signatures differ from what's shown, adapt to local conventions (e.g., use SQL helpers directly).

- [ ] **Step 2: Run failing test**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py::test_avg_minutes_per_late_event_empty -v`
Expected: FAIL — `ImportError: cannot import name 'avg_minutes_per_late_event'`.

- [ ] **Step 3: Implement the function**

Append to `src/core/insights.py`:

```python
def avg_minutes_per_late_event(conn, period_start: str, period_end: str) -> float:
    """Rata-rata menit terlambat per kejadian (total_min / count of late events).

    Returns 0.0 jika tidak ada late events di periode tersebut.
    Rows dengan terlambat_menit=0 atau NULL (= on time) tidak dihitung sebagai event.
    """
    row = conn.execute(
        """
        SELECT COALESCE(SUM(terlambat_menit), 0) AS total,
               COUNT(*) AS cnt
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND terlambat_menit IS NOT NULL
           AND terlambat_menit > 0
        """,
        (period_start, period_end),
    ).fetchone()
    total, cnt = row[0], row[1]
    return float(total) / cnt if cnt else 0.0
```

- [ ] **Step 4: Run tests pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -k avg_minutes -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): add avg_minutes_per_late_event"
```

### Task 1.2: Add `pola_jam_masuk`

**Files:**
- Modify: `src/core/insights.py`
- Test: `tests/test_insights.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_insights.py`:

```python
POLA_JAM_BANDS = ['<07:45', '07:45-07:59', '08:00', '08:01-08:05',
                  '08:06-08:15', '08:16-08:30', '08:31-09:00', '>09:00']


def test_pola_jam_masuk_8_bands_zero_fill(empty_conn):
    """Even with no data, returns all 8 bands with count=0, chronological order"""
    from src.core.insights import pola_jam_masuk
    result = pola_jam_masuk(empty_conn, '2026-04-01', '2026-04-30')
    assert len(result) == 8
    assert [r['band'] for r in result] == POLA_JAM_BANDS
    assert all(r['count'] == 0 for r in result)


def test_pola_jam_masuk_boundaries(conn_with_attendance):
    """Boundary times go to correct band"""
    from src.core.insights import pola_jam_masuk
    cases = [
        ('A', '07:44', '<07:45'),
        ('B', '07:45', '07:45-07:59'),
        ('C', '07:59', '07:45-07:59'),
        ('D', '08:00', '08:00'),
        ('E', '08:01', '08:01-08:05'),
        ('F', '08:05', '08:01-08:05'),
        ('G', '08:06', '08:06-08:15'),
        ('H', '08:15', '08:06-08:15'),
        ('I', '08:16', '08:16-08:30'),
        ('J', '08:30', '08:16-08:30'),
        ('K', '08:31', '08:31-09:00'),
        ('L', '09:00', '08:31-09:00'),
        ('M', '09:01', '>09:00'),
    ]
    rows = [
        {'nama': nama, 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': t, 'keluar': '17:00', 'terlambat_menit': max(0, _delta(t))}
        for nama, t, _ in cases
    ]
    conn = conn_with_attendance(rows=rows)
    result = pola_jam_masuk(conn, '2026-04-01', '2026-04-30')
    counts = {r['band']: r['count'] for r in result}
    expected_counts = {b: sum(1 for _, _, exp in cases if exp == b) for b in POLA_JAM_BANDS}
    assert counts == expected_counts


def _delta(t):
    """Helper: minutes after 08:00 (negative if before)."""
    h, m = int(t[:2]), int(t[3:])
    return (h - 8) * 60 + m


def test_pola_jam_masuk_absent_excluded(conn_with_attendance):
    """Sesi absent (masuk IS NULL) tidak dihitung di distribusi"""
    from src.core.insights import pola_jam_masuk
    conn = conn_with_attendance(rows=[
        {'nama': 'A', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
        {'nama': 'B', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:00', 'keluar': '17:00', 'terlambat_menit': 0},
    ])
    result = pola_jam_masuk(conn, '2026-04-01', '2026-04-30')
    counts = {r['band']: r['count'] for r in result}
    assert sum(counts.values()) == 1
    assert counts['08:00'] == 1


def test_pola_jam_masuk_severity_labels(empty_conn):
    """Each band has a severity tag for renderer/template"""
    from src.core.insights import pola_jam_masuk
    result = pola_jam_masuk(empty_conn, '2026-04-01', '2026-04-30')
    severity = {r['band']: r['severity'] for r in result}
    assert severity['<07:45'] == 'early'
    assert severity['07:45-07:59'] == 'early'
    assert severity['08:00'] == 'ontime'
    assert severity['08:01-08:05'] == 'mild'
    assert severity['08:06-08:15'] == 'mild'
    assert severity['08:16-08:30'] == 'mod'
    assert severity['08:31-09:00'] == 'severe'
    assert severity['>09:00'] == 'chronic'
```

- [ ] **Step 2: Run failing test**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py::test_pola_jam_masuk_8_bands_zero_fill -v`
Expected: FAIL — `ImportError: cannot import name 'pola_jam_masuk'`.

- [ ] **Step 3: Implement the function**

Append to `src/core/insights.py`:

```python
_POLA_JAM_BANDS = [
    ('<07:45',      'early'),
    ('07:45-07:59', 'early'),
    ('08:00',       'ontime'),
    ('08:01-08:05', 'mild'),
    ('08:06-08:15', 'mild'),
    ('08:16-08:30', 'mod'),
    ('08:31-09:00', 'severe'),
    ('>09:00',      'chronic'),
]


def _classify_jam_masuk(masuk: str) -> str:
    """Map HH:MM string to band label. Caller already filters masuk IS NOT NULL."""
    if masuk < '07:45':    return '<07:45'
    if masuk < '08:00':    return '07:45-07:59'
    if masuk == '08:00':   return '08:00'
    if masuk <= '08:05':   return '08:01-08:05'
    if masuk <= '08:15':   return '08:06-08:15'
    if masuk <= '08:30':   return '08:16-08:30'
    if masuk <= '09:00':   return '08:31-09:00'
    return '>09:00'


def pola_jam_masuk(conn, period_start: str, period_end: str) -> list[dict]:
    """Distribusi 8-band waktu kedatangan untuk sesi present (masuk IS NOT NULL).

    Returns: list of 8 dicts (chronological), even bands dengan count=0.
        [{'band': '<07:45', 'count': int, 'severity': 'early'}, ...]

    Severity mapping:
        early   — datang sebelum 08:00 (termasuk pas 08:00? lihat ontime)
        ontime  — 08:00 pas
        mild    — 1-15 min terlambat
        mod     — 16-30 min terlambat
        severe  — 31-60 min terlambat
        chronic — > 60 min terlambat
    """
    rows = conn.execute(
        """
        SELECT masuk
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND masuk IS NOT NULL
        """,
        (period_start, period_end),
    ).fetchall()

    counts = {band: 0 for band, _ in _POLA_JAM_BANDS}
    for (masuk,) in rows:
        counts[_classify_jam_masuk(masuk)] += 1

    return [
        {'band': band, 'count': counts[band], 'severity': severity}
        for band, severity in _POLA_JAM_BANDS
    ]
```

- [ ] **Step 4: Run tests pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -k pola_jam -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): add pola_jam_masuk 8-band distribution"
```

### Task 1.3: Extend `terlambat_ranking` with `absent_count`

**Files:**
- Modify: `src/core/insights.py` (existing `terlambat_ranking`)
- Test: `tests/test_insights.py`

- [ ] **Step 1: Read existing `terlambat_ranking` to confirm shape**

Run: `grep -n "def terlambat_ranking" src/core/insights.py`
Note: read the existing function (~30 lines) to understand the current SQL/row shape. The extension is additive — every existing returned key must remain.

- [ ] **Step 2: Write failing test**

Append to `tests/test_insights.py`:

```python
def test_terlambat_ranking_includes_absent_count(conn_with_attendance):
    """terlambat_ranking output dict includes 'absent_count' per emp"""
    from src.core.insights import terlambat_ranking
    conn = conn_with_attendance(rows=[
        # A: 1 late (10 min) + 1 absent
        {'nama': 'A', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:10', 'keluar': '17:00', 'terlambat_menit': 10},
        {'nama': 'A', 'tanggal': '2026-04-14', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
        # B: on time, no absent
        {'nama': 'B', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:00', 'keluar': '17:00', 'terlambat_menit': 0},
        # C: only absent (no late events)
        {'nama': 'C', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
        {'nama': 'C', 'tanggal': '2026-04-14', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
    ])
    result = terlambat_ranking(conn, '2026-04-01', '2026-04-30')
    by_nama = {r['nama']: r for r in result}
    # A has terlambat → in result with absent_count=1
    assert by_nama['A']['absent_count'] == 1
    # C has no terlambat but only absent → must appear (so ranking lengkap shows all emp)
    assert 'C' in by_nama
    assert by_nama['C']['absent_count'] == 2
    assert by_nama['C']['total_terlambat'] == 0


def test_terlambat_ranking_sort_order(conn_with_attendance):
    """Sort: total_terlambat DESC, absent_count DESC, kejadian DESC, nama ASC"""
    from src.core.insights import terlambat_ranking
    conn = conn_with_attendance(rows=[
        # A: 100 min late
        {'nama': 'A', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '09:40', 'keluar': '17:00', 'terlambat_menit': 100},
        # B: 50 min late, 1 absent
        {'nama': 'B', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:50', 'keluar': '17:00', 'terlambat_menit': 50},
        {'nama': 'B', 'tanggal': '2026-04-14', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
        # C: 50 min late, 0 absent
        {'nama': 'C', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:50', 'keluar': '17:00', 'terlambat_menit': 50},
        # D: 0 late, 2 absent
        {'nama': 'D', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
        {'nama': 'D', 'tanggal': '2026-04-14', 'tipe': 'Hari Kerja',
         'masuk': None, 'keluar': None, 'terlambat_menit': None},
        # E: 0 late, 0 absent (teladan)
        {'nama': 'E', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:00', 'keluar': '17:00', 'terlambat_menit': 0},
    ])
    result = terlambat_ranking(conn, '2026-04-01', '2026-04-30')
    names_in_order = [r['nama'] for r in result]
    # Expected order: A (100) → B (50+absent) → C (50) → D (0,2 absent) → E (0,0)
    assert names_in_order == ['A', 'B', 'C', 'D', 'E']
```

- [ ] **Step 3: Run failing test**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py::test_terlambat_ranking_includes_absent_count -v`
Expected: FAIL — `KeyError: 'absent_count'` (or similar).

- [ ] **Step 4: Extend `terlambat_ranking`**

The strategy: keep the existing late aggregation SQL, then merge per-emp absent counts in Python. Also include emp who only have absences (no late) so ranking lengkap shows all employees in the period.

Find existing function in `src/core/insights.py` and replace its body with:

```python
def terlambat_ranking(conn, period_start: str, period_end: str) -> list[dict]:
    """Ranking lengkap karyawan untuk periode tertentu, urut by severity.

    Each row dict:
        nama, no_staff, dept, total_terlambat (sum of terlambat_menit > 0),
        kejadian (count of late events), absent_count (Hari Kerja absent days)

    Sort: total_terlambat DESC, absent_count DESC, kejadian DESC, nama ASC.
    Includes employees who only have absences (no late events) so the
    "Ranking Lengkap" print panel shows ALL active employees of the period.
    """
    # Late aggregation per emp
    late_rows = conn.execute(
        """
        SELECT nama,
               COALESCE(no_staff, '') AS no_staff,
               COALESCE(dept, '') AS dept,
               COALESCE(SUM(CASE WHEN terlambat_menit > 0 THEN terlambat_menit ELSE 0 END), 0) AS total_terlambat,
               COALESCE(SUM(CASE WHEN terlambat_menit > 0 THEN 1 ELSE 0 END), 0) AS kejadian
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
         GROUP BY nama, no_staff, dept
        """,
        (period_start, period_end),
    ).fetchall()

    # Absent per emp
    absent_rows = conn.execute(
        """
        SELECT nama, COUNT(*) AS absent_count
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND masuk IS NULL AND keluar IS NULL
         GROUP BY nama
        """,
        (period_start, period_end),
    ).fetchall()

    absent_by_nama = {r[0]: r[1] for r in absent_rows}

    result = []
    seen = set()
    for nama, no_staff, dept, total, count in late_rows:
        seen.add(nama)
        result.append({
            'nama': nama,
            'no_staff': no_staff,
            'dept': dept,
            'total_terlambat': total,
            'kejadian': count,
            'absent_count': absent_by_nama.get(nama, 0),
        })

    # Emp who only have absences (not in late_rows): include with zero late stats
    for nama, ab_count in absent_by_nama.items():
        if nama in seen:
            continue
        meta = conn.execute(
            """
            SELECT COALESCE(no_staff, ''), COALESCE(dept, '')
              FROM attendance_records
             WHERE nama = ? AND tanggal BETWEEN ? AND ?
             LIMIT 1
            """,
            (nama, period_start, period_end),
        ).fetchone() or ('', '')
        result.append({
            'nama': nama,
            'no_staff': meta[0],
            'dept': meta[1],
            'total_terlambat': 0,
            'kejadian': 0,
            'absent_count': ab_count,
        })

    result.sort(key=lambda r: (-r['total_terlambat'], -r['absent_count'], -r['kejadian'], r['nama']))
    return result
```

- [ ] **Step 5: Run all insight tests**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -v`
Expected: All previously-passing tests still pass + 2 new ones pass. If any existing test fails due to the new `absent_count` key, that's an expected break — update the failing test to either ignore the new key or assert it explicitly.

- [ ] **Step 6: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): extend terlambat_ranking with absent_count + include absent-only emp"
```

---

## Phase 2 — Renderer Refactor

[src/reports/html_renderer.py](src/reports/html_renderer.py) — drop theme machinery, drop removed-panel computations, add new ones.

### Task 2.1: Refactor renderer signature and computations

**Files:**
- Modify: `src/reports/html_renderer.py`
- Test: `tests/test_html_renderer.py`

- [ ] **Step 1: Read existing renderer + tests**

Run: `cat src/reports/html_renderer.py; echo '---'; cat tests/test_html_renderer.py`
Note the existing test structure — list parametrized themes, asserted heading strings, etc. These tests will need updating in Task 6.1.

- [ ] **Step 2: Replace renderer body**

Replace the entire content of `src/reports/html_renderer.py` with:

```python
"""Render dashboard HTML print output.

Produces a 2-page A4 HTML using the single "Light" theme template.
Page 1: Executive summary (KPI strip + Top 5 + Teladan + Coaching + Pola Jam Masuk).
Page 2: Ranking Lengkap (all employees with menit + kejadian + tidak hadir).
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import DEFAULT_COACHING_THRESHOLD_MINUTES
from src.core.insights import (
    terlambat_ranking, top_n_terlambat, coaching_flag,
    karyawan_teladan_top_n,
    avg_minutes_per_late_event, pola_jam_masuk,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_FILE = "dashboard.html.j2"

DEFAULT_SECTIONS = {
    "kpi": True,
    "top5_late": True,
    "top5_teladan": True,
    "coaching": True,
    "pola_jam_masuk": True,
    "ranking": True,  # mandatory — always rendered regardless of toggle
}


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_dashboard_html(
    conn: sqlite3.Connection,
    *,
    period_start: str,
    period_end: str,
    period_label: str,
    out_dir: Path,
    threshold: int = DEFAULT_COACHING_THRESHOLD_MINUTES,
    sections: Optional[dict] = None,
) -> Path:
    """Render the dashboard HTML print output and return its path.

    `sections` is a dict of booleans keyed by section name (see DEFAULT_SECTIONS).
    Missing keys default to True. The "ranking" section is always rendered even
    if set to False — it's mandatory per design spec.
    """
    if sections is None:
        sections = DEFAULT_SECTIONS.copy()
    else:
        sections = {**DEFAULT_SECTIONS, **sections}
    sections["ranking"] = True  # enforce mandatory

    ranking = terlambat_ranking(conn, period_start, period_end)
    top5_late = top_n_terlambat(conn, period_start, period_end, n=5)
    coaching = coaching_flag(conn, period_start, period_end, threshold=threshold)
    teladan = karyawan_teladan_top_n(conn, period_start, period_end, n=None)
    avg_min = avg_minutes_per_late_event(conn, period_start, period_end)
    jam_masuk = pola_jam_masuk(conn, period_start, period_end)

    # KPI tallies (derived from above)
    total_terlambat = sum(r['kejadian'] for r in ranking)
    total_min = sum(r['total_terlambat'] for r in ranking)
    teladan_count = sum(
        1 for r in ranking
        if r['total_terlambat'] == 0 and r['kejadian'] == 0 and r['absent_count'] == 0
    )

    env = _build_env()
    tmpl = env.get_template(TEMPLATE_FILE)
    html = tmpl.render(
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        kpi={
            "total_terlambat": total_terlambat,
            "total_min": total_min,
            "avg_min": avg_min,
            "coaching_count": len(coaching),
            "teladan_count": teladan_count,
        },
        top5_late=top5_late,
        teladan=teladan,
        coaching=coaching,
        coaching_threshold=threshold,
        jam_masuk=jam_masuk,
        ranking=ranking,
        sections=sections,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"hr-dashboard-{ts}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
```

Note the changes vs old version:
- `template_name` param removed
- `TEMPLATE_NAMES` dict removed (single `TEMPLATE_FILE`)
- `ranking_departemen` + `hari_paling_rawan` imports removed
- `avg_minutes_per_late_event` + `pola_jam_masuk` imports added
- `karyawan_teladan_top_n` called with `n=None` (all teladan, not just top 5)
- `total_absen` query removed (replaced by per-emp absent_count in ranking)
- KPI dict reshaped: drop `total_absen`, add `avg_min`, add `teladan_count`
- `top5_teladan` renamed to `teladan` (consistent with template var)

- [ ] **Step 3: Sanity check imports load**

Run: `../../../.venv/Scripts/python.exe -c "from src.reports.html_renderer import render_dashboard_html, DEFAULT_SECTIONS; print(list(DEFAULT_SECTIONS.keys()))"`
Expected: `['kpi', 'top5_late', 'top5_teladan', 'coaching', 'pola_jam_masuk', 'ranking']`

- [ ] **Step 4: Check `karyawan_teladan_top_n` accepts `n=None`**

Run: `grep -A 5 "def karyawan_teladan_top_n" src/core/insights.py`
If the function does not accept `n=None`, add support (either treat None as "no limit", or change the call to pass a large number like `n=999`). The renderer must show ALL teladan, not just top 5.

If signature change needed:

```python
def karyawan_teladan_top_n(conn, period_start, period_end, n: Optional[int] = 5):
    ...
    if n is not None:
        ranking = ranking[:n]
    return ranking
```

If you change the signature, run `pytest tests/test_insights.py -k teladan -v` to confirm existing tests still pass (default n=5 stays compatible).

- [ ] **Step 5: Commit**

```bash
git add src/reports/html_renderer.py src/core/insights.py
git commit -m "refactor(reports): drop theme dispatch + add new computations to renderer"
```

---

## Phase 3 — Template Rewrite

Rewrite [src/reports/templates/dashboard.html.j2](src/reports/templates/dashboard.html.j2) using the locked Tema B Light design. Delete the 4 broken templates.

### Task 3.1: Delete broken theme templates

**Files:**
- Delete: `src/reports/templates/dashboard_v1_editorial.html.j2`
- Delete: `src/reports/templates/dashboard_v2_dark_glass.html.j2`
- Delete: `src/reports/templates/dashboard_v3_infographic.html.j2`
- Delete: `src/reports/templates/dashboard_v4_corporate.html.j2`

- [ ] **Step 1: Confirm files exist**

Run: `ls src/reports/templates/dashboard_v*.html.j2`
Expected: 4 files listed.

- [ ] **Step 2: Delete them**

Run: `rm src/reports/templates/dashboard_v1_editorial.html.j2 src/reports/templates/dashboard_v2_dark_glass.html.j2 src/reports/templates/dashboard_v3_infographic.html.j2 src/reports/templates/dashboard_v4_corporate.html.j2`

- [ ] **Step 3: Verify only `dashboard.html.j2` remains**

Run: `ls src/reports/templates/`
Expected: just `dashboard.html.j2`.

- [ ] **Step 4: Commit deletion**

```bash
git add -u src/reports/templates/
git commit -m "chore(reports): remove 4 broken theme templates"
```

### Task 3.2: Rewrite `dashboard.html.j2` for Light theme

**Files:**
- Replace: `src/reports/templates/dashboard.html.j2`

**Reference mockup** (study CSS + structure): `.superpowers/brainstorm/669-1778670666/content/05-tema-b-final.html` — port the styles and layout into Jinja, replace sample data with `{{ ... }}` template variables. The mockup uses the same variable shapes that the renderer now passes.

- [ ] **Step 1: Replace template content**

Replace `src/reports/templates/dashboard.html.j2` with the following. The CSS is ported from the mockup; structure uses Jinja conditionals on `sections`.

```jinja
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>HR Dashboard · {{ period_label }}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  @page{size:A4;margin:14mm}
  body{font-family:'Segoe UI','Inter',sans-serif;background:#fff;color:#171717;font-size:11px;line-height:1.45}
  .doc{padding:8px 12px}

  /* Header */
  .b-head{display:flex;justify-content:space-between;align-items:flex-end;padding-bottom:16px;border-bottom:2px solid #ec4899;margin-bottom:22px;position:relative}
  .b-head::after{content:"";position:absolute;left:0;bottom:-5px;width:60px;height:8px;background:#22d3ee}
  .b-head .badge{display:inline-block;background:#ec4899;color:#fff;font-size:9px;font-weight:700;padding:3px 10px;border-radius:3px;letter-spacing:1.5px;margin-bottom:8px}
  .b-head h1{font-size:26px;font-weight:700;color:#171717;letter-spacing:-.5px}
  .b-head .meta{text-align:right;font-family:Consolas,monospace;font-size:10px;color:#737373}
  .b-head .meta .lg{color:#22d3ee;font-size:14px;font-weight:700;letter-spacing:.5px;margin-bottom:2px;font-family:'Segoe UI'}

  /* KPI strip */
  .b-kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px}
  .b-kpi .k{background:#fafafa;border:1px solid #e5e5e5;padding:14px 16px;border-radius:6px;position:relative;overflow:hidden}
  .b-kpi .k::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:#ec4899}
  .b-kpi .k.cyan::before{background:#22d3ee}
  .b-kpi .k.violet::before{background:#a855f7}
  .b-kpi .k.emerald::before{background:#10b981}
  .b-kpi .k .l{font-size:9.5px;color:#737373;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600}
  .b-kpi .k .n{font-family:Consolas,monospace;font-size:28px;color:#171717;font-weight:700;line-height:1}
  .b-kpi .k .n .u{font-size:14px;color:#737373;font-weight:500;margin-left:3px}
  .b-kpi .k .delta{font-size:10px;color:#525252;margin-top:4px}

  /* Sections */
  .b-section{margin-bottom:22px;break-inside:avoid}
  .b-section h2{font-size:11px;color:#171717;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #e5e5e5;font-weight:700}
  .b-section h2::before{content:"// ";color:#ec4899}
  .b-twocol{display:grid;grid-template-columns:1fr 1fr;gap:18px}

  /* Tables */
  .b-table{width:100%;border-collapse:collapse;font-size:11px}
  .b-table th{text-align:left;font-size:9.5px;color:#737373;text-transform:uppercase;letter-spacing:.8px;padding:7px 6px;background:#fafafa;border-bottom:1px solid #ec4899}
  .b-table td{padding:7px 6px;border-bottom:1px solid #f5f5f5}
  .b-table .num{font-family:Consolas,monospace;text-align:right;color:#ec4899;font-weight:600}
  .b-table .cyan{color:#22d3ee;font-size:10px;text-transform:uppercase;letter-spacing:.5px}
  .b-table .rank{font-family:Consolas,monospace;color:#737373;width:30px}

  /* Pills */
  .b-pill{display:inline-block;background:#fdf2f8;color:#ec4899;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:600;margin:2px}
  .b-pill.violet{background:#f5f3ff;color:#7c3aed}

  /* Pola Jam Masuk */
  .b-jam{background:#fafafa;border-radius:8px;padding:14px 16px}
  .b-jam .jh{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}
  .b-jam .jh .total{font-family:Consolas;font-size:10px;color:#737373}
  .b-jam .jh .total b{color:#ec4899}
  .b-bar-row{display:grid;grid-template-columns:100px 1fr 50px;gap:10px;align-items:center;font-size:10.5px;padding:3px 0}
  .b-bar-row .lbl{font-family:Consolas;color:#525252;font-size:10px}
  .b-bar-row .lbl.early,.b-bar-row .lbl.ontime{color:#10b981}
  .b-bar-row .lbl.mod{color:#a855f7}
  .b-bar-row .lbl.severe,.b-bar-row .lbl.chronic{color:#ec4899}
  .b-bar-track{height:14px;background:#fff;border:1px solid #e5e5e5;border-radius:7px;overflow:hidden}
  .b-bar-fill{height:100%;border-radius:7px;display:flex;align-items:center;padding:0 8px;color:#fff;font-size:9.5px;font-weight:600;white-space:nowrap;overflow:hidden}
  .b-bar-fill.early,.b-bar-fill.ontime{background:linear-gradient(90deg,#10b981,#34d399)}
  .b-bar-fill.mild{background:linear-gradient(90deg,#f59e0b,#fbbf24);color:#171717}
  .b-bar-fill.mod{background:linear-gradient(90deg,#a855f7,#c084fc)}
  .b-bar-fill.severe{background:linear-gradient(90deg,#ec4899,#f472b6)}
  .b-bar-fill.chronic{background:linear-gradient(90deg,#be123c,#e11d48)}
  .b-bar-row .v{font-family:Consolas;font-weight:700;text-align:right;color:#171717}
  .b-jam-divider{border-top:1px dashed #e5e5e5;margin:8px 0;text-align:center;font-size:9px;color:#a3a3a3;text-transform:uppercase;letter-spacing:1px;padding-top:6px}
  .b-jam-insight{margin-top:12px;padding:10px 12px;background:#fff;border-left:3px solid #ec4899;border-radius:0 6px 6px 0;font-size:11px;color:#525252}
  .b-jam-insight b{color:#171717}

  /* Footer */
  .b-footer{margin-top:22px;padding-top:12px;border-top:1px solid #e5e5e5;display:flex;justify-content:space-between;font-size:9.5px;color:#737373;font-family:Consolas,monospace}
  .b-footer .jts{color:#ec4899;letter-spacing:1.5px;text-transform:uppercase;font-weight:700}

  /* Page 2 header */
  .b-rank-head{padding-bottom:10px;border-bottom:2px solid #ec4899;margin-bottom:14px;position:relative}
  .b-rank-head::after{content:"";position:absolute;left:0;bottom:-5px;width:40px;height:8px;background:#22d3ee}
  .b-rank-head h2{font-size:18px;color:#171717}
  .b-rank-head .sub{font-size:10px;color:#737373;text-transform:uppercase;letter-spacing:1.5px;margin-top:6px;font-family:Consolas}

  /* Print */
  .page-break{break-before:page;page-break-before:always}
  .empty-state{padding:14px;background:#fafafa;border:1px dashed #e5e5e5;border-radius:6px;text-align:center;color:#737373;font-size:11px}
</style>
</head>
<body>

<div class="doc">
  {# === HEADER === #}
  <div class="b-head">
    <div>
      <div class="badge">WEEKLY REPORT</div>
      <h1>HR Absensi Dashboard</h1>
      <div style="font-size:11px;color:#737373;margin-top:4px">{{ ranking|length }} karyawan</div>
    </div>
    <div class="meta">
      <div class="lg">{{ period_label }}</div>
      <div>{{ period_start }} — {{ period_end }}</div>
      <div>Gen: {{ generated_at }}</div>
    </div>
  </div>

  {# === KPI === #}
  {% if sections.kpi %}
  <div class="b-kpi">
    <div class="k"><div class="l">Total Terlambat</div><div class="n">{{ kpi.total_terlambat }}</div><div class="delta">kejadian</div></div>
    <div class="k cyan"><div class="l">Rata-rata / Kejadian</div><div class="n">{{ '%.0f' % kpi.avg_min }}<span class="u">min</span></div><div class="delta">{{ kpi.total_min }} menit ÷ {{ kpi.total_terlambat }}</div></div>
    <div class="k violet"><div class="l">Coaching</div><div class="n">{{ kpi.coaching_count }}</div><div class="delta">≥ {{ coaching_threshold }} min</div></div>
    <div class="k emerald"><div class="l">Teladan</div><div class="n">{{ kpi.teladan_count }}</div><div class="delta">hadir penuh</div></div>
  </div>
  {% endif %}

  {# === TOP 5 === #}
  {% if sections.top5_late %}
  <div class="b-section">
    <h2>Top 5 Paling Terlambat</h2>
    {% if top5_late %}
    <table class="b-table">
      <thead><tr><th>#</th><th>Nama</th><th>Dept</th><th style="text-align:right">Menit</th><th style="text-align:right">Kejadian</th></tr></thead>
      <tbody>
        {% for r in top5_late %}
        <tr><td class="rank">{{ '%02d' % loop.index }}</td><td>{{ r.nama }}</td><td class="cyan">{{ r.dept }}</td><td class="num">{{ r.total_terlambat }}</td><td class="num">{{ r.kejadian }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}<div class="empty-state">Tidak ada keterlambatan di periode ini.</div>{% endif %}
  </div>
  {% endif %}

  {# === TELADAN + COACHING === #}
  <div class="b-twocol">
    {% if sections.top5_teladan %}
    <div class="b-section">
      <h2>Karyawan Teladan</h2>
      {% if teladan %}
        {% for r in teladan %}<span class="b-pill violet">{{ r.nama }} · {{ r.dept }}</span>{% endfor %}
        <div style="font-size:10px;color:#737373;margin-top:8px">Hadir penuh tanpa terlambat</div>
      {% else %}<div class="empty-state">Belum ada teladan periode ini.</div>{% endif %}
    </div>
    {% endif %}

    {% if sections.coaching %}
    <div class="b-section">
      <h2>Butuh Coaching</h2>
      {% if coaching %}
        {% for r in coaching %}<span class="b-pill">{{ r.nama }} · {{ r.total_terlambat }}m</span>{% endfor %}
        <div style="font-size:10px;color:#737373;margin-top:8px">Threshold ≥ {{ coaching_threshold }} menit / periode</div>
      {% else %}<div class="empty-state">Tidak ada kandidat coaching.</div>{% endif %}
    </div>
    {% endif %}
  </div>

  {# === POLA JAM MASUK === #}
  {% if sections.pola_jam_masuk %}
  <div class="b-section">
    <h2>Pola Jam Masuk</h2>
    {% set jam_total = jam_masuk|sum(attribute='count') %}
    {% set jam_max = jam_masuk|map(attribute='count')|max if jam_masuk else 0 %}
    <div class="b-jam">
      <div class="jh">
        <div style="font-weight:600;color:#171717;font-size:11px">Distribusi waktu kedatangan · {{ jam_total }} sesi present</div>
        <div class="total">absen tidak termasuk</div>
      </div>
      {% if jam_total == 0 %}<div class="empty-state">Tidak ada data jam masuk.</div>{% else %}
        {% for b in jam_masuk %}
          {% if b.band == '08:00' %}<div class="b-jam-divider">— ambang tepat waktu —</div>{% endif %}
          <div class="b-bar-row">
            <span class="lbl {{ b.severity }}">{{ b.band }}</span>
            <div class="b-bar-track"><div class="b-bar-fill {{ b.severity }}" style="width:{{ (b.count * 100 / jam_max)|round(0)|int if jam_max > 0 else 0 }}%">{% if b.count > 0 %}{{ b.count }}{% endif %}</div></div>
            <span class="v">{{ b.count }}</span>
          </div>
        {% endfor %}
      {% endif %}
    </div>
  </div>
  {% endif %}

  <div class="b-footer">
    <span>// page 1/2 · confidential</span>
    <span class="jts">[jts] josaphat tech solution</span>
  </div>

  {# === PAGE BREAK === #}
  <div class="page-break"></div>

  {# === RANKING LENGKAP (mandatory) === #}
  <div class="b-rank-head">
    <h2>Ranking Lengkap · {{ ranking|length }} Karyawan</h2>
    <div class="sub">// {{ period_label }} · sort by total menit terlambat</div>
  </div>
  {% if ranking %}
  <table class="b-table">
    <thead><tr><th>#</th><th>Nama</th><th>Dept</th><th style="text-align:right">Menit</th><th style="text-align:right">Kejadian</th><th style="text-align:right">Tidak Hadir</th></tr></thead>
    <tbody>
      {% for r in ranking %}
        {% set is_teladan = r.total_terlambat == 0 and r.kejadian == 0 and r.absent_count == 0 %}
        <tr {% if is_teladan %}style="background:#f0fdf4"{% endif %}>
          <td class="rank">{{ '%02d' % loop.index }}</td>
          <td {% if is_teladan %}style="color:#10b981;font-weight:700"{% endif %}>{{ r.nama }}</td>
          <td class="cyan">{{ r.dept }}</td>
          <td class="num" {% if is_teladan %}style="color:#10b981"{% endif %}>{{ r.total_terlambat }}</td>
          <td class="num" {% if is_teladan %}style="color:#10b981"{% endif %}>{{ r.kejadian }}</td>
          <td class="num" {% if r.absent_count >= 1 and not is_teladan %}style="color:#a855f7"{% elif is_teladan %}style="color:#10b981"{% endif %}>{{ r.absent_count }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
  <div style="font-size:10px;color:#737373;margin-top:8px">Highlight emerald = karyawan teladan · Highlight violet pada kolom absen = perlu perhatian khusus (≥1 hari tidak hadir).</div>
  {% else %}<div class="empty-state">Tidak ada data karyawan di periode ini.</div>{% endif %}

  <div class="b-footer">
    <span>// page 2/2 · confidential</span>
    <span class="jts">[jts] josaphat tech solution</span>
  </div>
</div>

</body>
</html>
```

- [ ] **Step 2: Render with sample data manually**

Run:

```bash
../../../.venv/Scripts/python.exe -c "
import sys, sqlite3
from pathlib import Path
sys.path.insert(0, '.')
from src.db.schema import create_schema
from src.parsers.fingerprint import parse_fingerprint_file
from src.db.attendance import insert_attendance_rows
from src.reports.html_renderer import render_dashboard_html

conn = sqlite3.connect(':memory:')
conn.row_factory = sqlite3.Row
create_schema(conn)
rows = parse_fingerprint_file(Path(r'D:/Gawe/Project X/HR App/Data Absensi/APRIL/April 13-17.xlsx'))
insert_attendance_rows(conn, rows)

out = render_dashboard_html(
    conn,
    period_start='2026-04-13',
    period_end='2026-04-17',
    period_label='W3 APRIL 2026',
    out_dir=Path('/tmp/hr-print-test'),
)
print('Rendered:', out)
"
```

Expected: prints path to rendered HTML, no exception.

- [ ] **Step 3: Open in browser, visually inspect**

Open the rendered file in a browser. Compare side-by-side with `.superpowers/brainstorm/669-1778670666/content/05-tema-b-final.html`. Look for:
- KPI strip shows 55 / 42min / 3 / 4
- Top 5 lists SATRIO/TOMBAK/RYAN/SELVI/ADI
- Teladan pills show 4 names
- Coaching pills show 3 names
- Pola Jam Masuk bar chart renders all 8 bands
- Page 2 ranking lengkap has 27 rows, teladan rows have emerald background
- Print preview (Ctrl+P) shows clean 2-page A4

If anything mismatches, edit template and re-render.

- [ ] **Step 4: Commit template**

```bash
git add src/reports/templates/dashboard.html.j2
git commit -m "feat(reports): rewrite dashboard.html.j2 with Light theme (2-page A4)"
```

---

## Phase 4 — Dialog Refactor

[src/ui/components/print_dialog.py](src/ui/components/print_dialog.py) — drop theme picker, resize, center on screen.

### Task 4.1: Refactor `PrintOptionsDialog`

**Files:**
- Modify: `src/ui/components/print_dialog.py`

- [ ] **Step 1: Replace dialog content**

Replace the entire content of `src/ui/components/print_dialog.py` with:

```python
"""Modal dialog to customize dashboard print: pick which sections to include.

Theme picker removed — there's only one theme now ("Light"). Dialog size and
position fixed for laptop screens: 560×440 centered on screen with max-height
clamp.
"""
from typing import Callable, Optional

import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_LG, RADIUS_MD,
)


SECTION_DEFS = [
    ("kpi",            "KPI Cards (4 metrik utama)"),
    ("top5_late",      "Top 5 Paling Terlambat"),
    ("top5_teladan",   "Karyawan Teladan"),
    ("coaching",       "Butuh Coaching"),
    ("pola_jam_masuk", "Pola Jam Masuk"),
    ("ranking",        "Ranking Lengkap Karyawan (wajib)"),
]


DIALOG_W = 560
DIALOG_H = 440
_SCREEN_BUFFER = 100  # taskbar + title bar buffer


class PrintOptionsDialog(ctk.CTkToplevel):
    """Modal options dialog. Calls on_submit(sections_dict) when user clicks Cetak.

    Closes on Batal, Escape, or window close. The "ranking" section is always
    True regardless of checkbox state (rendered as checked + disabled).
    """

    def __init__(
        self,
        parent,
        on_submit: Callable[[dict], None],
        initial_sections: Optional[dict] = None,
    ):
        super().__init__(parent)
        self.title("Pilih Opsi Cetak")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)

        # Size with screen-height clamp
        sh = self.winfo_screenheight()
        sw = self.winfo_screenwidth()
        h = min(DIALOG_H, sh - _SCREEN_BUFFER)
        w = DIALOG_W
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._on_submit = on_submit
        self._sections_state = {k: True for k, _ in SECTION_DEFS}
        if initial_sections:
            self._sections_state.update(initial_sections)
        self._sections_state["ranking"] = True  # enforce mandatory

        self._build()

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build(self):
        # Header
        ctk.CTkLabel(
            self, text="Opsi Cetak Dashboard",
            font=FONT_HEADING, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_XL, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            self, text="Pilih bagian yang akan dicetak.",
            font=FONT_BODY, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_XL, pady=(0, SPACE_MD))

        # Sections
        ctk.CTkLabel(
            self, text="BAGIAN", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XL, pady=(SPACE_XS, SPACE_XS))
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        for key, label in SECTION_DEFS:
            var = ctk.BooleanVar(value=self._sections_state[key])
            self._check_vars[key] = var
            is_mandatory = (key == "ranking")
            cb = ctk.CTkCheckBox(
                self, text=label, variable=var,
                font=FONT_BODY,
                text_color=COLOR_TEXT,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                border_color=COLOR_BORDER,
                checkbox_width=18, checkbox_height=18,
                state="disabled" if is_mandatory else "normal",
            )
            cb.pack(anchor="w", padx=SPACE_XL + SPACE_SM, pady=2)

        # Buttons (sticky at bottom via side="bottom")
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_LG), side="bottom")
        ctk.CTkButton(
            btn_row, text="Batal", command=self._on_cancel,
            fg_color="transparent",
            hover_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_INFO,
            text_color=COLOR_INFO,
            width=160, height=40,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(SPACE_MD, 0))
        ctk.CTkButton(
            btn_row, text="📄 Cetak", command=self._on_ok,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            width=180, height=40,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(side="right")

    def _on_ok(self):
        sections = {k: v.get() for k, v in self._check_vars.items()}
        sections["ranking"] = True  # belt-and-suspenders for disabled checkbox
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_submit(sections)

    def _on_cancel(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
```

Changes vs old version:
- `THEME_DEFS` constant removed
- `initial_theme` parameter removed
- `_theme_state` / `_theme_var` removed
- Geometry: `620x680` → `560x440`, centered on **screen** not parent
- `_SCREEN_BUFFER = 100` clamp on height for tiny screens
- `SECTION_DEFS` updated: drop `departemen` + `hari_rawan`, add `pola_jam_masuk`
- `ranking` checkbox `state="disabled"` (mandatory)
- Theme radio block removed entirely
- `on_submit` callback signature changed: `(sections)` only, no theme arg
- Belt-and-suspenders: enforce `sections["ranking"] = True` in `_on_ok`

- [ ] **Step 2: Smoke-test dialog instantiates (without main app)**

Run:

```bash
../../../.venv/Scripts/python.exe -c "
import customtkinter as ctk
from src.ui.components.print_dialog import PrintOptionsDialog

def submit_cb(sections):
    print('Submitted:', sections)
    root.quit()

root = ctk.CTk()
root.geometry('800x600')
PrintOptionsDialog(root, on_submit=submit_cb)
root.mainloop()
"
```

Expected: dialog appears centered on screen, 6 checkboxes shown (last one disabled and checked), Cetak and Batal buttons visible at bottom. Close it. No errors.

- [ ] **Step 3: Visual checks on smallest target screen**

If you have a 1366×768 display (or scaled equivalent), launch the above again and verify the dialog fits within the visible viewport and the Cetak button is reachable without dragging.

On larger screens this is trivially correct.

- [ ] **Step 4: Commit dialog**

```bash
git add src/ui/components/print_dialog.py
git commit -m "refactor(ui): print dialog 560x440 centered on screen, drop theme picker"
```

---

## Phase 5 — Wire Up Call Sites

[src/ui/screens/dashboard.py](src/ui/screens/dashboard.py) — drop the `theme` argument when calling `PrintOptionsDialog` and `render_dashboard_html`.

### Task 5.1: Update dashboard.py print flow

**Files:**
- Modify: `src/ui/screens/dashboard.py`

- [ ] **Step 1: Find print invocation sites**

Run: `grep -n "PrintOptionsDialog\|render_dashboard_html\|template_name\|initial_theme" src/ui/screens/dashboard.py`
Expected: a few matches showing where the dialog is opened and where the renderer is called.

- [ ] **Step 2: Update the dialog open**

Find the call to `PrintOptionsDialog(...)`. The old call passes `on_submit`, `initial_sections`, and `initial_theme`. The new dialog signature is `(parent, on_submit, initial_sections=None)`.

- Remove `initial_theme=...` argument from the constructor call.
- Update the `on_submit` callback signature: `def _on_print_submit(sections, theme):` → `def _on_print_submit(sections):`.

- [ ] **Step 3: Update the renderer call**

Find the call to `render_dashboard_html(...)`. The old call passes `template_name=theme` (or similar). Remove that argument.

- [ ] **Step 4: Remove any theme-related state in dashboard.py**

Search for `theme` references in the dashboard module that relate to print (not UI theme tokens, which are different). Remove `_last_print_theme`, theme-related settings reads, or similar. If a setting key like `last_print_theme` exists in `src/db/settings.py` usage, it's safe to leave the DB key untouched but stop reading/writing it from this screen.

- [ ] **Step 5: Smoke-test the app runs**

Run: `../../../.venv/Scripts/python.exe -m src.main`
Expected: app launches without exception. Navigate to Dashboard, click the Cetak button. Confirm:
- Dialog shows 6 sections (last disabled).
- Click Cetak → HTML opens in browser, content matches mockup.
- No console errors.

Close app.

- [ ] **Step 6: Commit**

```bash
git add src/ui/screens/dashboard.py
git commit -m "refactor(dashboard): drop theme arg from print flow"
```

---

## Phase 6 — Test Suite Updates

[tests/test_html_renderer.py](tests/test_html_renderer.py) needs updates: the parametrized theme tests no longer apply, and assertions for removed panels (Ranking Departemen, Hari Paling Rawan) must be replaced with assertions for new panel (Pola Jam Masuk).

### Task 6.1: Update `test_html_renderer.py`

**Files:**
- Modify: `tests/test_html_renderer.py`

- [ ] **Step 1: Read existing tests**

Run: `cat tests/test_html_renderer.py`
Identify:
- Any `@pytest.mark.parametrize("template_name", [...])` decorators
- Any assertions matching strings like `"Hari Paling Rawan"`, `"Ranking Departemen"`
- Any usage of `template_name=` argument

- [ ] **Step 2: Strip theme parametrize**

- Remove all `@pytest.mark.parametrize("template_name", ...)` decorators.
- Remove the corresponding parameter from test functions (`template_name` → drop).
- Remove `template_name=template_name` from `render_dashboard_html(...)` calls.

If a test was previously named `test_render_each_theme` (or similar), keep just one happy-path version.

- [ ] **Step 3: Update assertions for new content**

Replace:
- `assert "Ranking Departemen" in html` → remove (panel deleted)
- `assert "Hari Paling Rawan" in html` → remove (panel deleted)

Add:
- `assert "Pola Jam Masuk" in html`
- `assert "Rata-rata / Kejadian" in html` (KPI label)
- `assert "Teladan" in html` (KPI label, with capital T)
- `assert "Tidak Hadir" in html` (ranking lengkap new column)
- `assert "[jts] josaphat tech solution" in html` (soft-sell footer)

- [ ] **Step 4: Add explicit test that ranking is always rendered**

Add a test:

```python
def test_ranking_is_mandatory_even_if_section_false(conn_with_attendance, tmp_path):
    """Ranking Lengkap renders even if sections.ranking=False (mandatory per spec)."""
    from src.reports.html_renderer import render_dashboard_html
    conn = conn_with_attendance(rows=[
        {'nama': 'X', 'tanggal': '2026-04-13', 'tipe': 'Hari Kerja',
         'masuk': '08:00', 'keluar': '17:00', 'terlambat_menit': 0},
    ])
    out = render_dashboard_html(
        conn,
        period_start='2026-04-01', period_end='2026-04-30',
        period_label='APR 2026', out_dir=tmp_path,
        sections={'kpi': False, 'top5_late': False, 'top5_teladan': False,
                  'coaching': False, 'pola_jam_masuk': False, 'ranking': False},
    )
    html = out.read_text(encoding='utf-8')
    assert "Ranking Lengkap" in html
    assert ">X<" in html  # the employee name should appear
```

- [ ] **Step 5: Run all renderer tests**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -v`
Expected: all PASSED. If any test fails, fix it. The renderer code is fixed at this point — tests adapt to it.

- [ ] **Step 6: Commit**

```bash
git add tests/test_html_renderer.py
git commit -m "test(reports): update renderer tests for single theme + new panels"
```

---

## Phase 7 — Full Verification

### Task 7.1: Full suite must pass

- [ ] **Step 1: Run full pytest**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASSED. Count should be **~124** (120 baseline − some removed theme parametrize subtests + 4-5 new insight tests + 1 mandatory-ranking test).

If any test fails, investigate and fix. Do NOT mark this complete with red tests.

- [ ] **Step 2: Final lint / smoke run**

Run: `../../../.venv/Scripts/python.exe -m src.main`
Expected: app launches, dashboard loads, Cetak button works, HTML output opens in browser and matches mockup.

Close app cleanly.

### Task 7.2: Manual end-to-end print check

- [ ] **Step 1: Print preview the rendered HTML**

In the browser, open the latest rendered HTML and hit Ctrl+P. Confirm:
- 2 pages (page 1 = summary, page 2 = ranking lengkap)
- No content cut off mid-element
- Borders, colors, and tables print cleanly (Background colors visible if "Background graphics" is enabled in print dialog)
- Footer "page 1/2" and "page 2/2" appear on correct pages

If 3+ pages, investigate page-break-inside on large sections.

### Task 7.3: Final commit + summary

- [ ] **Step 1: Confirm clean working tree**

Run: `git status`
Expected: nothing to commit.

- [ ] **Step 2: Show commit chain**

Run: `git log --oneline origin/v6..HEAD`
Expected: chronological commits from the rebase + each phase. Roughly:
- `docs(spec): print dashboard redesign ...`
- `feat(insights): add avg_minutes_per_late_event`
- `feat(insights): add pola_jam_masuk 8-band distribution`
- `feat(insights): extend terlambat_ranking with absent_count ...`
- `refactor(reports): drop theme dispatch + add new computations`
- `chore(reports): remove 4 broken theme templates`
- `feat(reports): rewrite dashboard.html.j2 with Light theme`
- `refactor(ui): print dialog 560x440 centered on screen ...`
- `refactor(dashboard): drop theme arg from print flow`
- `test(reports): update renderer tests for single theme + new panels`

- [ ] **Step 3: Hand off**

Implementation done. Inform user. Do NOT push, do NOT build .exe, do NOT create v7 branch — these are user-authorized actions per workflow rules.

Suggested message to user:
> Implementation complete on `claude/optimistic-cohen-7d9c88` (10 commits on top of v6). All tests pass (~124). Ready for: (1) smoke test the .exe build if you want, (2) merge to local v7 branch + push to origin/v7, (3) deploy via .exe rotation.

---

## Out of Scope (reaffirmed from spec)

- Light mode for UI app (separate effort)
- About dialog
- Export PDF directly (HTML only; user uses browser's Print to PDF)
- Multiple themes — YAGNI (bring back when actually needed)
- Conflict resolution toggle (R3)
- Cross-screen helper extraction

---

## Reference

- **Spec:** [2026-05-13-print-dashboard-redesign-design.md](../specs/2026-05-13-print-dashboard-redesign-design.md)
- **Mockup (final):** `.superpowers/brainstorm/669-1778670666/content/05-tema-b-final.html`
- **Dialog comparison:** `.superpowers/brainstorm/669-1778670666/content/06-dialog-options.html`
- **Sample data:** `Data Absensi/APRIL/April 13-17.xlsx` (W3 April 2026 · 27 emp · 4 dept)
