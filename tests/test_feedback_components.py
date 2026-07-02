"""Smoke tests for the shared v22 UI pieces — ActiveMonthBanner (both
variants), EmptyStateCard, FileChip, HistoryList, MessageDialog and the
src.ui.feedback wrappers. Construct + destroy level, matching the
existing screen-test style."""
import pytest

from src.ui.theme import (
    COLOR_INFO_TINT_BG, COLOR_WARN_TINT_BG,
    COLOR_SUCCESS_TINT_BG, COLOR_WARN_TINT_BADGE_BG,
    COLOR_SUCCESS, COLOR_WARN,
)


def _all_text(widget):
    """Recursively gather every text fragment in the widget tree."""
    out = []
    try:
        text = widget.cget("text")
        if text:
            out.append(str(text))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(_all_text(child))
    return out


# -- ActiveMonthBanner --

def test_active_month_banner_banner_variant_states(tk_root):
    from src.ui.components.active_month_banner import ActiveMonthBanner
    banner = ActiveMonthBanner(
        tk_root, variant="banner",
        text="Bulan aktif saat ini: April 2026.",
    )
    tk_root.update_idletasks()
    assert banner.cget("fg_color") == COLOR_INFO_TINT_BG
    assert "April 2026" in " ".join(_all_text(banner))

    banner.set_warn("Bulan aktif akan diubah: April → Mei setelah konfirmasi impor.")
    assert banner.cget("fg_color") == COLOR_WARN_TINT_BG
    assert banner.icon_label.cget("text") == "⚠"

    banner.set_info("Bulan aktif saat ini: Mei 2026.")
    assert banner.cget("fg_color") == COLOR_INFO_TINT_BG
    assert banner.icon_label.cget("text") == "📆"
    banner.destroy()


def test_active_month_banner_badge_variant(tk_root):
    from src.ui.components.active_month_banner import ActiveMonthBanner
    badge = ActiveMonthBanner(tk_root, variant="badge", value="April 2026")
    tk_root.update_idletasks()
    texts = " ".join(_all_text(badge))
    assert "BULAN AKTIF" in texts
    assert "April 2026" in texts
    badge.set_value("Mei 2026")
    assert "Mei 2026" in " ".join(_all_text(badge))
    badge.destroy()


def test_active_month_banner_rejects_unknown_variant(tk_root):
    from src.ui.components.active_month_banner import ActiveMonthBanner
    with pytest.raises(ValueError):
        ActiveMonthBanner(tk_root, variant="chip")


# -- EmptyStateCard --

def test_empty_state_card_renders_title_and_hint(tk_root):
    from src.ui.components.empty_state import EmptyStateCard
    card = EmptyStateCard(
        tk_root,
        "Belum ada bulan aktif.",
        "Pilih bulan di menu Active Month dulu.",
    )
    tk_root.update_idletasks()
    texts = " ".join(_all_text(card))
    assert "Belum ada bulan aktif." in texts
    assert "Pilih bulan di menu Active Month dulu." in texts
    card.destroy()


# -- FileChip --

def test_file_chip_renders_and_wires_actions(tk_root):
    from src.ui.components.file_chip import FileChip, FileChipAction
    clicked = []
    chip = FileChip(
        tk_root,
        label="FILE TERPILIH",
        filename="fingerprint_w1.xls",
        meta="120 KB · diparsing dalam 45 ms",
        actions=(
            FileChipAction("↻ Ganti", lambda: clicked.append("ganti")),
            FileChipAction("✕ Batal", lambda: clicked.append("batal")),
            FileChipAction("✓ Konfirmasi", lambda: clicked.append("ok"),
                           kind="primary", width=120),
        ),
    )
    tk_root.update_idletasks()
    texts = " ".join(_all_text(chip))
    assert "fingerprint_w1.xls" in texts
    assert "FILE TERPILIH" in texts
    assert len(chip.action_buttons) == 3
    chip.action_buttons[2].invoke()
    assert clicked == ["ok"]
    chip.destroy()


def test_file_chip_set_content_rebuilds(tk_root):
    from src.ui.components.file_chip import FileChip, FileChipAction
    chip = FileChip(
        tk_root, label="TEMPLATE LAPORAN BULANAN",
        filename="Laporan April.xlsx", meta="C:/Users · 88 KB",
        extra="→ Akan menyimpan sebagai: Laporan April [Auto Filled].xlsx",
        actions=(FileChipAction("👁 Preview", lambda: None, kind="info", width=100),),
    )
    tk_root.update_idletasks()
    assert "Laporan April.xlsx" in " ".join(_all_text(chip))
    chip.set_content(
        label="TEMPLATE LAPORAN BULANAN",
        filename="Laporan Mei.xlsx", meta="C:/Users · 90 KB",
    )
    texts = " ".join(_all_text(chip))
    assert "Laporan Mei.xlsx" in texts
    assert "Laporan April.xlsx" not in texts
    assert chip.action_buttons == []  # actions omitted on rebuild
    chip.destroy()


# -- HistoryList --

def test_history_list_empty_then_rows(tk_root):
    from src.ui.components.history_list import HistoryList, HistoryRow
    hist = HistoryList(
        tk_root,
        header="RIWAYAT EXPORT TERAKHIR",
        empty_text="(belum ada riwayat export)",
    )
    tk_root.update_idletasks()
    assert "(belum ada riwayat export)" in " ".join(_all_text(hist))

    hist.set_rows([
        HistoryRow(   # Export-style row: tag + result badge
            time="Hari ini 08:19", title="Laporan April.xlsx",
            tag="Isi Template", badge_text="✓ 12/12",
            badge_color=COLOR_SUCCESS, badge_bg=COLOR_SUCCESS_TINT_BG,
            badge_width=80,
        ),
        HistoryRow(
            time="Kemarin 16:40", title="Laporan Maret.xlsx",
            tag="Generate Bulanan", badge_text="9/12",
            badge_color=COLOR_WARN, badge_bg=COLOR_WARN_TINT_BADGE_BG,
            badge_width=80,
        ),
        HistoryRow(   # Import-style row: no tag
            time="Mei 2 09:12", title="fingerprint_w1.xls",
            badge_text="✓ 15 emp",
        ),
    ])
    texts = " ".join(_all_text(hist))
    assert "(belum ada riwayat export)" not in texts
    assert "Laporan April.xlsx" in texts
    assert "Isi Template" in texts
    assert "✓ 15 emp" in texts
    hist.destroy()


# -- MessageDialog + feedback --

def test_message_dialog_constructs_and_binds_keys(tk_root):
    from src.ui.components.message_dialog import MessageDialog
    dlg = MessageDialog(
        tk_root, "Error export", "Tidak bisa generate file:\ndisk penuh.",
        kind="error",
    )
    tk_root.update_idletasks()
    assert dlg.bind("<Escape>") != ""
    assert dlg.bind("<Return>") != ""
    texts = " ".join(_all_text(dlg))
    assert "Tidak bisa generate file" in texts
    assert dlg.secondary_button is None  # 1-button dialog
    dlg.destroy()
    tk_root.update()  # flush the 50ms deferred-grab timer harmlessly


def test_message_dialog_primary_sets_result_true(tk_root):
    from src.ui.components.message_dialog import MessageDialog
    dlg = MessageDialog(
        tk_root, "Konfirmasi", "Lanjutkan impor?",
        kind="question", primary_text="Ya", secondary_text="Batal",
    )
    tk_root.update_idletasks()
    assert dlg.secondary_button is not None
    dlg._on_primary()
    assert dlg.result is True
    assert not dlg.winfo_exists()
    tk_root.update()


def test_message_dialog_cancel_sets_result_false(tk_root):
    from src.ui.components.message_dialog import MessageDialog
    dlg = MessageDialog(
        tk_root, "Konfirmasi", "Hapus data?",
        kind="warning", primary_text="Ya", secondary_text="Batal",
    )
    tk_root.update_idletasks()
    dlg._on_cancel()
    assert dlg.result is False
    assert not dlg.winfo_exists()
    tk_root.update()


def test_ask_yes_no_blocks_and_returns_true_on_primary(tk_root):
    from src.ui import feedback
    from src.ui.components.message_dialog import MessageDialog
    attempts = {"n": 0}

    def auto_click():
        attempts["n"] += 1
        for w in tk_root.winfo_children():
            if isinstance(w, MessageDialog) and w.winfo_exists():
                w._on_primary()
                return
        if attempts["n"] < 200:               # bounded — never hang the suite
            tk_root.after(10, auto_click)
        else:                                  # failsafe: unblock wait_window
            for w in tk_root.winfo_children():
                if isinstance(w, MessageDialog):
                    w.destroy()

    tk_root.after(50, auto_click)
    result = feedback.ask_yes_no(tk_root, "Konfirmasi", "Timpa file yang ada?")
    assert result is True
    tk_root.update()
