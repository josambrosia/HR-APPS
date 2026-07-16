"""Full-file SQLite snapshots — backup / list / prune / restore.

No Tk, no sqlite. Snapshots live in ``<db_path>.parent/backups/`` named
``hr-YYYYMMDD-HHMMSS-<slug>.db``. Pure file I/O so the whole module is
unit-testable against a temp dir (never the production DB).

Retensi (prune): buang snapshot > 1 tahun DAN jaga total folder di bawah
~1 GB, tapi SELALU simpan minimal 5 snapshot terbaru (floor) supaya user
tak pernah kehabisan titik pulang. Lihat spec §5.1 (D7).
"""
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

BACKUP_DIRNAME = "backups"

# reason kunci internal -> slug nama file (Indonesian, muncul di UI badge)
REASON_SLUGS = {
    "import": "sebelum-import",
    "manual": "manual",
    "hapus": "sebelum-hapus",
    "restore": "sebelum-restore",
}

_FNAME_RE = re.compile(r"^hr-(\d{8})-(\d{6})-(.+)\.db$")


def backup_dir(db_path) -> Path:
    """Folder tempat snapshot disimpan (dibuat on-demand oleh create_backup)."""
    return Path(db_path).parent / BACKUP_DIRNAME


def create_backup(db_path, *, reason, now=None) -> Path:
    """Salin seluruh file DB ke backups/hr-YYYYMMDD-HHMMSS-<slug>.db, lalu prune.

    `reason` salah satu dari REASON_SLUGS ('import'/'manual'/'hapus'/'restore');
    nilai lain jatuh ke slug 'manual'. `now` di-inject untuk test deterministik.
    """
    db_path = Path(db_path)
    d = backup_dir(db_path)
    d.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    slug = REASON_SLUGS.get(reason, "manual")
    dest = d / f"hr-{now:%Y%m%d}-{now:%H%M%S}-{slug}.db"
    shutil.copy2(db_path, dest)
    prune_backups(db_path, now=now)
    return dest


def list_backups(db_path) -> list:
    """Semua snapshot, terbaru dulu. Tiap item:
    {path, filename, created_at (datetime), size_bytes, reason (slug)}."""
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
            created = datetime.fromtimestamp(p.stat().st_mtime)
            reason = "?"
        out.append({
            "path": p, "filename": p.name, "created_at": created,
            "size_bytes": p.stat().st_size, "reason": reason,
        })
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out


def prune_backups(db_path, *, max_age_days=365, max_total_bytes=1_000_000_000,
                  keep_min=5, now=None) -> list:
    """Buang snapshot lama. Return daftar Path yang dihapus.

    Aturan (urut): (1) `keep_min` terbaru SELALU aman (floor). (2) dari sisanya,
    hapus yang lebih tua dari `max_age_days`. (3) jika total folder masih di atas
    `max_total_bytes`, hapus survivor tertua sampai di bawah batas.
    """
    now = now or datetime.now()
    items = list_backups(db_path)               # terbaru dulu
    protected, candidates = items[:keep_min], items[keep_min:]
    removed = []

    cutoff = now - timedelta(days=max_age_days)
    survivors = []
    for it in candidates:
        if it["created_at"] < cutoff:
            it["path"].unlink(missing_ok=True)
            removed.append(it["path"])
        else:
            survivors.append(it)

    total = (sum(i["size_bytes"] for i in protected)
             + sum(i["size_bytes"] for i in survivors))
    for it in reversed(survivors):              # survivor tertua duluan
        if total <= max_total_bytes:
            break
        it["path"].unlink(missing_ok=True)
        removed.append(it["path"])
        total -= it["size_bytes"]
    return removed


def restore_backup(db_path, snapshot_path, *, now=None) -> Path:
    """Amankan DB saat ini (snapshot 'sebelum-restore'), lalu timpa DB dengan
    `snapshot_path`. Return path snapshot pengaman (agar restore bisa dibatalkan
    dengan me-restore file itu)."""
    db_path = Path(db_path)
    pre = create_backup(db_path, reason="restore", now=now)
    shutil.copy2(Path(snapshot_path), db_path)
    return pre
