"""Pure presentation logic for the attendance heatmap. cell_status() maps one
(employee, date) to a status key; the dicts give colour/code/label. Independent
of effective_attendance() (which is for export number adjustment) — the
reason-over-lateness precedence reproduces the same justified-late behaviour."""
import calendar
from datetime import date

from src.config import HEATMAP_DINAS_REASONS
from src.core.reason_mapper import render_alasan_ijin
from src.db.settings import read_late_tolerance, read_severe_lateness_threshold
from src.db.employees import list_employees
from src.db.attendance import list_attendance_matrix
from src.db.holidays import holiday_dates_in_month
from src.db.outlier import excluded_employee_ids

# status_key -> hex / code / human label
STATUS_COLORS = {
    "hadir": "#10B981", "dinas": "#0D9488", "sedang": "#FBBF24",
    "parah": "#F97316", "sakit": "#22D3EE", "cuti": "#A855F7",
    "lupa": "#94A3B8", "mangkir": "#EF4444", "na": "#737373",
    "libur": "#39414F", "nodata": "#3A3F4A",
}
# HK (hari kerja dihadiri) is an aggregate, not a status — give it a colour that
# no status uses and that isn't the brand magenta: a confident "working-day total"
# blue. Black text fails the luminance test on it, so cells get near-white ink.
HK_COLOR = "#2563EB"
STATUS_CODES = {
    "hadir": "H", "dinas": "D", "sedang": "TR", "parah": "TB", "sakit": "S",
    "cuti": "C", "lupa": "LA", "mangkir": "X", "na": "NA", "libur": "·",
    "nodata": "–",
}
STATUS_LABELS = {
    "hadir": "Hadir tepat waktu",
    "dinas": "Dinas (lapangan/paparan/belajar/terlambat dengan alasan)",
    "sedang": "Terlambat Ringan", "parah": "Terlambat Berat",
    "sakit": "Izin Sakit", "cuti": "Cuti", "lupa": "Lupa absen",
    "mangkir": "Absen Tanpa Alasan", "na": "NA / belum ada kabar",
    "libur": "Libur / weekend", "nodata": "Belum ada data",
}
# statuses that count toward HK (hari kerja dihadiri)
HK_STATUSES = ("hadir", "sedang", "parah", "dinas", "lupa")
# leave reasons whose colour overrides lateness (justified-late reasons are
# caught above via HEATMAP_DINAS_REASONS, so they are intentionally NOT here)
_LEAVE_REASON_STATUS = {
    "izin_sakit": "sakit", "cuti": "cuti",
    "lupa_absen_datang": "lupa", "lupa_absen_pulang": "lupa",
    "na": "na", "libur": "libur",
}


def cell_status(row, *, tolerance, severe, is_weekend, is_holiday):
    """row is a dict-like attendance record or None. Returns a status key."""
    # 1. Libur
    if is_weekend or is_holiday or (row is not None and row["tipe"] == "Hari Libur"):
        return "libur"
    # 2. No data
    if row is None:
        return "nodata"
    reason = row["reason_category"]
    # 3. Leave/justified reason colour wins
    if reason in HEATMAP_DINAS_REASONS:
        return "dinas"
    if reason in _LEAVE_REASON_STATUS:
        return _LEAVE_REASON_STATUS[reason]
    # (justified-late terlambat_kerja/terlambat_lain already returned "dinas" above)
    # 4. Present + lateness tiers
    if row["masuk"]:
        late = row["terlambat_menit"] or 0
        if late <= tolerance:
            return "hadir"
        if late < severe:
            return "sedang"
        return "parah"
    # 5. Hari Kerja, no punch, no reason
    return "mangkir"


_INDO_MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
                "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
# status -> summary column code (na folds into X)
_SUMMARY_OF = {"hadir": "H", "dinas": "D", "sedang": "TR", "parah": "TB",
               "sakit": "S", "cuti": "C", "lupa": "LA", "mangkir": "X", "na": "X"}
_SUMMARY_KEYS = ["H", "D", "TR", "TB", "S", "C", "LA", "X"]
_SUMMARY_STATUS = {"H": "hadir", "D": "dinas", "TR": "sedang", "TB": "parah",
                   "S": "sakit", "C": "cuti", "LA": "lupa", "X": "mangkir"}
_LEGEND_ORDER = ["hadir", "dinas", "sedang", "parah", "sakit", "cuti",
                 "lupa", "mangkir", "na", "libur", "nodata"]


def _text_color(hexstr):
    """Black on light fills, near-white on dark fills (luminance)."""
    h = hexstr.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#0a0a0a" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#e8e8e8"


def _prev_next_month(year_month):
    y, m = int(year_month[:4]), int(year_month[5:7])
    pm = (y - 1, 12) if m == 1 else (y, m - 1)
    nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{pm[0]:04d}-{pm[1]:02d}", f"{nm[0]:04d}-{nm[1]:02d}"


def build_heatmap_context(conn, year_month, *, exclude_outliers, today=None):
    """Full render context for the heatmap templates: active employees × every
    date in `year_month` ('YYYY-MM'), each cell coloured via cell_status()."""
    y, m = int(year_month[:4]), int(year_month[5:7])
    n_days = calendar.monthrange(y, m)[1]
    weekday_of = {d: date(y, m, d).weekday() for d in range(1, n_days + 1)}
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(y, m)
    tol = read_late_tolerance(conn)
    sev = read_severe_lateness_threshold(conn)
    holidays = holiday_dates_in_month(conn, year_month)

    emps = [dict(e) for e in list_employees(conn, include_inactive=False)]
    if exclude_outliers:
        excl = excluded_employee_ids(conn, year_month)
        emps = [e for e in emps if e["id"] not in excl]

    start, end = f"{year_month}-01", f"{year_month}-{n_days:02d}"
    rows = list_attendance_matrix(conn, start, end)
    by_key = {(r["employee_id"], r["tanggal"]): r for r in rows}

    eff_hk = sum(1 for d in range(1, n_days + 1)
                 if weekday_of[d] < 5 and f"{year_month}-{d:02d}" not in holidays)

    out_emps = []
    for e in emps:
        eid = e["id"]
        cells = {}
        summary = {k: 0 for k in _SUMMARY_KEYS}
        hk = 0
        telat_total = 0
        worst_min = 0
        worst_day = None
        fh_late = sh_late = 0          # late minutes in the 1st / 2nd half of month
        mid = n_days // 2
        for d in range(1, n_days + 1):
            tgl = f"{year_month}-{d:02d}"
            row = by_key.get((eid, tgl))
            status = cell_status(
                row, tolerance=tol, severe=sev,
                is_weekend=weekday_of[d] >= 5, is_holiday=tgl in holidays)
            if status in ("sedang", "parah"):
                tm = row["terlambat_menit"] or 0
                telat_total += tm
                if tm > worst_min:
                    worst_min, worst_day = tm, d
                if d <= mid:
                    fh_late += tm
                else:
                    sh_late += tm
            color = STATUS_COLORS[status]
            if row is not None and row["reason_category"]:
                try:
                    alasan = render_alasan_ijin(
                        row["reason_category"], row["reason_detail"])
                except ValueError:
                    alasan = row["reason_category"]
            else:
                alasan = "—"
            cells[d] = {
                "status": status, "code": STATUS_CODES[status],
                "label": STATUS_LABELS[status],
                "color": color, "text_color": _text_color(color), "date": d,
                "masuk": (row["masuk"] if row and row["masuk"] else "—"),
                "keluar": (row["keluar"] if row and row["keluar"] else "—"),
                "telat": (row["terlambat_menit"]
                          if row and row["terlambat_menit"] is not None else "—"),
                "alasan": alasan,
            }
            if status in _SUMMARY_OF:
                summary[_SUMMARY_OF[status]] += 1
            if status in HK_STATUSES:
                hk += 1
        sorotan = {
            "hk": hk,
            "work_days": eff_hk,
            "pct_hadir": round(hk / eff_hk * 100) if eff_hk else 0,
            "ontime_days": summary["H"],
            "telat_total": telat_total,
            "telat_days": summary["TR"] + summary["TB"],
            "dinas": summary["D"],
            "sakit": summary["S"],
        }
        sorotan["pct_color"] = pct_band_color(sorotan["pct_hadir"])
        late_days = summary["TR"] + summary["TB"]
        lateness = {
            "worst_min": worst_min,
            "worst_day": worst_day,
            "avg_min": round(telat_total / late_days) if late_days else 0,
            "trend": ("up" if sh_late > fh_late
                      else "down" if sh_late < fh_late else "flat"),
        }
        out_emps.append({
            "employee_id": eid, "nama": e["nama"], "dept": e.get("dept") or "",
            "hk": hk, "summary": summary, "cells": cells,
            "sorotan": sorotan, "lateness": lateness,
            "needs_attention": needs_attention(summary),
        })

    # Week segments for the print matrix header (M1, M2, ...) + separators.
    print_weeks = []
    for d in range(1, n_days + 1):
        if d == 1 or weekday_of[d] == 0:
            print_weeks.append({"label": f"M{len(print_weeks) + 1}", "days": []})
        print_weeks[-1]["days"].append(d)
    wsep_days = [seg["days"][0] for seg in print_weeks[1:]]

    prev_m, next_m = _prev_next_month(year_month)
    today = today or date.today()
    today_day = today.day if (today.year == y and today.month == m) else None
    legend = [{"code": STATUS_CODES[s], "color": STATUS_COLORS[s],
               "text_color": _text_color(STATUS_COLORS[s]),
               "label": STATUS_LABELS[s]} for s in _LEGEND_ORDER]
    return {
        "year_month": year_month,
        "today_day": today_day,
        "month_label": f"{_INDO_MONTHS[m]} {y}",
        "prev_month": prev_m, "next_month": next_m,
        "days": list(range(1, n_days + 1)),
        "weekday_of": weekday_of,
        "weekday_labels": ["Sn", "Sl", "Rb", "Km", "Jm", "Sb", "Mg"],
        "weeks": weeks,
        "eff_hari_kerja": eff_hk,
        "late_tolerance": tol,
        "severe_threshold": sev,
        "is_empty": not rows,
        "legend": legend,
        "summary_keys": _SUMMARY_KEYS,
        "summary_meta": [{"code": k,
                          "color": STATUS_COLORS[_SUMMARY_STATUS[k]],
                          "text_color": _text_color(STATUS_COLORS[_SUMMARY_STATUS[k]])}
                         for k in _SUMMARY_KEYS],
        "hk_color": HK_COLOR,
        "hk_text_color": _text_color(HK_COLOR),
        "print_weeks": print_weeks,
        "wsep_days": wsep_days,
        "employees": out_emps,
    }


def pct_band_color(pct):
    """Colour band for the % Kehadiran bar/number (>=90 green, 75-89 amber, <75 orange)."""
    if pct >= 90:
        return "#10B981"
    if pct >= 75:
        return "#FBBF24"
    return "#F97316"


# Severity ramp for the lateness ridge: on-time green → mild amber → orange → severe red.
SEVERITY_COLORS = {"ok": "#10B981", "mild": "#FBBF24", "mid": "#FB923C", "severe": "#EF4444"}


def severity_color(minutes, tolerance, severe):
    """Colour a lateness value by how severe it is (drives the ridge contour). Shared
    by the in-app heatmap and the printed report so the ramp can't drift apart."""
    if minutes <= tolerance:
        return SEVERITY_COLORS["ok"]
    if minutes < severe * 0.5:
        return SEVERITY_COLORS["mild"]
    if minutes < severe:
        return SEVERITY_COLORS["mid"]
    return SEVERITY_COLORS["severe"]


def build_lateness_ridge(cells, days, tolerance, severe, *,
                         width=560, height=82, pad_top=12, pad_bottom=15, pad_x=8):
    """Pre-compute SVG geometry for the per-day lateness ridge embedded in the
    printed report: a flat fill polygon under a severity-coloured contour, peak
    markers (late days) with their minutes, dinas baseline dots, the tolerance
    line, and day-axis ticks — all in a fixed viewBox that scales to fit. Built
    server-side (not JS) so it always prints."""
    n = max(len(days), 1)
    scale_max = max(severe * 1.33, 80.0)
    base_y = height - pad_bottom
    top_y = pad_top
    usable = base_y - top_y
    left = float(pad_x)
    right = float(width - pad_x)
    span = max(right - left, 1.0)

    def late(d):
        cell = cells.get(d)
        if cell and cell.get("status") in ("sedang", "parah") and isinstance(cell.get("telat"), int):
            return cell["telat"]
        return 0

    def y_of(m):
        return base_y - min(m / scale_max, 1.0) * usable

    coords = [(left + (i + 0.5) / n * span, y_of(late(d)), late(d))
              for i, d in enumerate(days)]
    fill = (f"{left:.1f},{base_y:.1f} "
            + " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in coords)
            + f" {right:.1f},{base_y:.1f}")
    segments = [{"x1": round(coords[i][0], 1), "y1": round(coords[i][1], 1),
                 "x2": round(coords[i + 1][0], 1), "y2": round(coords[i + 1][1], 1),
                 "color": severity_color(max(coords[i][2], coords[i + 1][2]), tolerance, severe)}
                for i in range(len(coords) - 1)]
    peaks, dinas = [], []
    for i, d in enumerate(days):
        cell = cells.get(d)
        if not cell:
            continue
        x = left + (i + 0.5) / n * span
        st = cell.get("status")
        if st in ("sedang", "parah") and isinstance(cell.get("telat"), int):
            m = cell["telat"]
            y = y_of(m)
            peaks.append({"x": round(x, 1), "y": round(y, 1), "m": m,
                          "ly": round(max(y - 4, top_y - 1), 1),
                          "color": severity_color(m, tolerance, severe)})
        elif st == "dinas":
            dinas.append({"x": round(x, 1)})
    axis = [{"x": round(left + (d - 0.5) / n * span, 1), "d": d}
            for d in sorted({1, 8, 15, 22, n}) if 1 <= d <= n]
    return {"w": width, "h": height, "left": round(left, 1), "right": round(right, 1),
            "base_y": round(base_y, 1), "fill": fill, "segments": segments,
            "peaks": peaks, "dinas": dinas, "axis": axis,
            "tol": tolerance, "tol_y": round(y_of(tolerance), 1) if tolerance > 0 else None}


def needs_attention(summary):
    """True when the employee has an unexcused absence (X) or severe lateness (TB)."""
    return summary.get("X", 0) > 0 or summary.get("TB", 0) > 0


def sort_employees(employees, key):
    """Stable sort of heatmap employee dicts, tiebreak by nama (case-insensitive).
    key in {"nama","kehadiran","telat","absen"}; unknown -> nama A-Z."""
    if key == "kehadiran":
        return sorted(employees, key=lambda e: (e["sorotan"]["pct_hadir"], e["nama"].lower()))
    if key == "telat":
        return sorted(employees, key=lambda e: (-e["sorotan"]["telat_days"],
                                                -e["sorotan"]["telat_total"], e["nama"].lower()))
    if key == "absen":
        return sorted(employees, key=lambda e: (-e["summary"]["X"], e["nama"].lower()))
    return sorted(employees, key=lambda e: e["nama"].lower())
