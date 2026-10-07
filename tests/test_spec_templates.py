"""Regresi: SEMUA template Jinja di src/reports/templates harus terdaftar di
HR-Absensi.spec datas. v26.0.0 sempat lolos tanpa overtime.html.j2 sehingga
cetak lembur gagal di bundle exe ("not found in search path")."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "src" / "reports" / "templates"
SPEC = ROOT / "HR-Absensi.spec"


def test_every_template_is_bundled_in_spec():
    spec_text = SPEC.read_text(encoding="utf-8")
    missing = [
        p.name for p in TEMPLATES.glob("*.j2")
        if f"templates/{p.name}" not in spec_text
    ]
    assert missing == [], (
        f"Template belum terdaftar di HR-Absensi.spec datas: {missing}"
    )
