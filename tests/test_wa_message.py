from src.core.wa_message import (
    build_wa_message, normalize_phone_id, wa_me_url, greeting_for_hour,
    kind_phrase, format_issue,
)

ISSUES = [
    {"hari": "Senin",  "tanggal": "2026-05-05", "masuk": None,    "keluar": "16:30"},
    {"hari": "Kamis",  "tanggal": "2026-05-15", "masuk": None,    "keluar": None},
    {"hari": "Selasa", "tanggal": "2026-05-20", "masuk": "08:30", "keluar": None},
]


def test_kind_phrase():
    assert kind_phrase(None, None) == "tidak tercatat hadir"
    assert kind_phrase(None, "16:30") == "belum ada absen masuk"
    assert kind_phrase("08:00", None) == "belum ada absen pulang"
    assert kind_phrase("08:00", "16:30") == "absensi perlu dicek"


def test_format_issue():
    assert format_issue("Senin", "2026-05-05", None, "16:30", "2026-05") == \
        "Sen, 5 Mei — belum ada absen masuk"


def test_greeting_for_hour():
    assert greeting_for_hour(8) == "pagi"
    assert greeting_for_hour(13) == "siang"
    assert greeting_for_hour(16) == "sore"
    assert greeting_for_hour(20) == "malam"


def test_formal_message_scaffold():
    msg = build_wa_message("RIZKY PRATAMA", "2026-05", ISSUES,
                           "Rahmadani Yulianti", tone="formal", hour=8)
    assert msg.startswith("Selamat pagi, Sdr. Rizky Pratama.")
    assert "Dari rekap absensi Mei 2026, ada 3 catatan" in msg
    assert "• Sen, 5 Mei — belum ada absen masuk" in msg
    assert "• Kam, 15 Mei — tidak tercatat hadir" in msg
    assert "• Sel, 20 Mei — belum ada absen pulang" in msg
    assert "Mohon konfirmasi atau alasannya" in msg
    assert msg.rstrip().endswith("— Rahmadani Yulianti, HR")


def test_ramah_message_scaffold():
    msg = build_wa_message("RIZKY PRATAMA", "2026-05", ISSUES,
                           "Rahmadani Yulianti", tone="ramah")
    assert msg.startswith("Halo Rizky 👋")
    assert "Ada 3 catatan absensi bulan Mei yang belum terisi" in msg
    assert msg.rstrip().endswith("— Rahmadani Yulianti (HR)")


def test_note_inserted_before_ask():
    msg = build_wa_message("RIZKY PRATAMA", "2026-05", ISSUES, "X",
                           tone="formal", note="Mohon jawab hari ini.", hour=8)
    assert "Mohon jawab hari ini." in msg
    assert msg.index("Mohon jawab hari ini.") < msg.index("Mohon konfirmasi")


def test_blank_officer_signoff():
    msg = build_wa_message("RIZKY PRATAMA", "2026-05", ISSUES, "", hour=8)
    assert msg.rstrip().endswith("— HR")


def test_normalize_phone_id():
    assert normalize_phone_id("0812-3456-7890") == "6281234567890"
    assert normalize_phone_id("+62 812 3456 7890") == "6281234567890"
    assert normalize_phone_id("6281234567890") == "6281234567890"
    assert normalize_phone_id("123") is None
    assert normalize_phone_id("") is None


def test_wa_me_url_prefilled():
    assert wa_me_url("081234567890", "Halo dunia") == \
        "https://wa.me/6281234567890?text=Halo%20dunia"
    assert wa_me_url("081234567890") == "https://wa.me/6281234567890"
    assert wa_me_url("123", "x") is None
