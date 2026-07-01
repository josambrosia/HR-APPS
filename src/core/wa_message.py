"""Pure WhatsApp-message helpers for the WhatsApp Assistant screen.

No I/O: builds the human-facing message text from structured issue rows and
normalizes Indonesian phone numbers into wa.me links. Isolated from Tk/sqlite so
it is unit-tested directly.
"""
from datetime import datetime
from urllib.parse import quote

_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

# attendance 'hari' is a full Indonesian day name; shorten to 3 letters.
_HARI3 = {
    "Senin": "Sen", "Selasa": "Sel", "Rabu": "Rab", "Kamis": "Kam",
    "Jumat": "Jum", "Jum'at": "Jum", "Sabtu": "Sab", "Minggu": "Min",
}


def greeting_for_hour(hour: int) -> str:
    """Indonesian time-of-day greeting word (no 'Selamat' prefix)."""
    if hour < 11:
        return "pagi"
    if hour < 15:
        return "siang"
    if hour < 18:
        return "sore"
    return "malam"


def _month_year(year_month: str) -> tuple[str, str]:
    """('Mei', '2026') from 'YYYY-MM'."""
    y, m = year_month.split("-")[:2]
    return _MONTH_ID[int(m)], y


def kind_phrase(masuk, keluar) -> str:
    """Human phrase for an open-issue punch state."""
    if masuk is None and keluar is None:
        return "tidak tercatat hadir"
    if masuk is None:
        return "belum ada absen masuk"
    if keluar is None:
        return "belum ada absen pulang"
    return "absensi perlu dicek"


def format_issue(hari, tanggal, masuk, keluar, year_month) -> str:
    """'Sen, 5 Mei — belum ada absen masuk' (no bullet)."""
    h3 = _HARI3.get((hari or "").strip(), (hari or "?")[:3])
    day = datetime.strptime(tanggal, "%Y-%m-%d").day
    bln3 = _month_year(year_month)[0][:3]
    return f"{h3}, {day} {bln3} — {kind_phrase(masuk, keluar)}"


def build_wa_message(nama, year_month, issues, hr_officer_name="", *,
                     tone="formal", note="", hour=None) -> str:
    """Build the WA-ready message for one employee's open issues.

    issues: sequence of mappings/rows with 'hari','tanggal','masuk','keluar'.
    """
    bulan, tahun = _month_year(year_month)
    n = len(issues)
    lines = "\n".join(
        "• " + format_issue(r["hari"], r["tanggal"], r["masuk"], r["keluar"], year_month)
        for r in issues
    )
    officer = (hr_officer_name or "").strip()
    note = (note or "").strip()

    if tone == "ramah":
        first = nama.split()[0].title() if nama.split() else nama.title()
        sign = f"— {officer} (HR)" if officer else "— HR"
        body = [f"Halo {first} 👋", "",
                f"Ada {n} catatan absensi bulan {bulan} yang belum terisi:", lines]
        if note:
            body += ["", note]
        body += ["", "Boleh dibantu konfirmasi ya biar bisa kami update 🙏 Makasih!",
                 "", sign]
        return "\n".join(body)

    # formal (default)
    h = greeting_for_hour(hour if hour is not None else datetime.now().hour)
    sign = f"— {officer}, HR" if officer else "— HR"
    body = [f"Selamat {h}, Sdr. {nama.title()}.", "",
            f"Dari rekap absensi {bulan} {tahun}, ada {n} catatan yang belum terkonfirmasi:",
            lines]
    if note:
        body += ["", note]
    body += ["", "Mohon konfirmasi atau alasannya agar data dapat kami perbarui. Terima kasih.",
             "", sign]
    return "\n".join(body)


def normalize_phone_id(phone) -> str | None:
    """Indonesian phone → digit string with 62 country code, or None if invalid.

    '0812...' → '62812...'; '+62'/'62' kept; validates 10-15 digits.
    """
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits


def wa_me_url(phone, text="") -> str | None:
    """https://wa.me/<digits>?text=<urlencoded>, or None when phone invalid."""
    digits = normalize_phone_id(phone)
    if digits is None:
        return None
    return f"https://wa.me/{digits}?text={quote(text)}" if text else f"https://wa.me/{digits}"
