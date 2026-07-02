"""WhatsApp Assistant screen — v22 consistency tests.

Covers: shared SearchBar adoption (debounce + Ctrl+F shortcuts wired via
install_shortcuts), the on_show() shell contract (fresh data, preserved
search query + selection, re-read contact mark), and the toast-based
copy confirmation replacing messagebox.
"""
import customtkinter as ctk

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.db.settings import set_setting
from src.db.wa_contacts import mark_contacted
from src.ui.components.search_bar import SearchBar

import src.ui.screens.whatsapp_assistant as mod


def _seed(conn):
    """BUDI: 2 open issues (with phone); ANI: 1 open issue (no phone).
    Active month 2026-05."""
    budi = upsert_employee(conn, no_staff="1", nama="BUDI", dept="X",
                           phone="081234567890")
    ani = upsert_employee(conn, no_staff="2", nama="ANI", dept="Y")
    for tanggal in ("2026-05-04", "2026-05-05"):
        upsert_attendance(
            conn, employee_id=budi, tanggal=tanggal, hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls",
        )
    upsert_attendance(
        conn, employee_id=ani, tanggal="2026-05-04", hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08.10", keluar=None, kerja_jam=None,
        lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="W1.xls",
    )
    set_setting(conn, "current_month", "2026-05")
    return budi, ani


def _resolve(db_path, emp_id, tanggal):
    """Resolve one issue OUTSIDE the screen (simulates the Issues screen)."""
    with get_connection(db_path) as conn:
        rid = conn.execute(
            "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
            (emp_id, tanggal),
        ).fetchone()["id"]
        set_reason(conn, attendance_id=rid, category="lupa_absen_pulang",
                   detail=None)


def _make_screen(temp_db_path, monkeypatch, tk_root, seed=True):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    ids = (None, None)
    if seed:
        with get_connection(temp_db_path) as conn:
            ids = _seed(conn)
    screen = mod.WhatsAppAssistantScreen(tk_root)
    tk_root.update_idletasks()
    return screen, ids


def _list_row_frames(screen):
    """Employee rows currently rendered in the left list (CTkFrame each)."""
    return [w for w in screen.list_frame.winfo_children()
            if isinstance(w, ctk.CTkFrame)]


# ---- SearchBar adoption ---------------------------------------------------

def test_screen_uses_shared_searchbar_with_shortcuts(temp_db_path, monkeypatch, tk_root):
    screen, _ = _make_screen(temp_db_path, monkeypatch, tk_root)
    assert isinstance(screen._search, SearchBar)
    assert screen._search._debounce_ms == mod.SEARCH_DEBOUNCE_MS == 200
    # install_shortcuts wired: Ctrl+F on the screen + click-outside handler
    assert screen.bind("<Control-f>") != ""
    assert getattr(screen._search, "_click_bind_id", None) is not None
    # the pre-v22 hand-rolled StringVar trace is gone
    assert not hasattr(screen, "_search_var")
    screen.destroy()


def test_filter_matches_nama_case_insensitive(temp_db_path, monkeypatch, tk_root):
    screen, _ = _make_screen(temp_db_path, monkeypatch, tk_root)
    assert len(_list_row_frames(screen)) == 2
    screen._apply_filter("bud")
    tk_root.update_idletasks()
    assert len(_list_row_frames(screen)) == 1
    assert screen._search._counter_label.cget("text") == "1 dari 2"
    screen._apply_filter("")
    tk_root.update_idletasks()
    assert len(_list_row_frames(screen)) == 2
    screen.destroy()


def test_filter_no_match_shows_no_match_message(temp_db_path, monkeypatch, tk_root):
    screen, _ = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._apply_filter("zzz")
    tk_root.update_idletasks()
    assert len(_list_row_frames(screen)) == 0
    labels = [w for w in screen.list_frame.winfo_children()
              if isinstance(w, ctk.CTkLabel)]
    assert any("tak ada nama yang cocok" in lbl.cget("text") for lbl in labels)
    screen.destroy()


# ---- on_show() shell contract ----------------------------------------------

def test_on_show_refreshes_counts_and_preserves_selection(temp_db_path, monkeypatch, tk_root):
    screen, (budi, _ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._show_for(budi)
    tk_root.update_idletasks()
    assert screen._current_employee_id == budi
    assert len(screen._issues) == 2

    # One of BUDI's issues is resolved on another screen…
    _resolve(temp_db_path, budi, "2026-05-05")
    screen.on_show()
    tk_root.update_idletasks()

    # …selection survives and the compose panel shows fresh data.
    assert screen._current_employee_id == budi
    assert len(screen._issues) == 1
    assert [r["open_cnt"] for r in screen._rows_cache if r["id"] == budi] == [1]
    assert screen._preview is not None
    assert "1 catatan" in screen._preview.get("1.0", "end")
    screen.destroy()


def test_on_show_preserves_search_query(temp_db_path, monkeypatch, tk_root):
    screen, (budi, _ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._search.set("bud")
    tk_root.update_idletasks()
    assert screen._search_query == "bud"
    assert len(_list_row_frames(screen)) == 1

    _resolve(temp_db_path, budi, "2026-05-05")   # BUDI 2 -> 1 open
    screen.on_show()
    tk_root.update_idletasks()

    assert screen._search.get() == "bud"
    assert screen._search_query == "bud"
    # fresh data re-filtered with the preserved query
    assert len(_list_row_frames(screen)) == 1
    assert screen._search._counter_label.cget("text") == "1 dari 2"
    screen.destroy()


def test_on_show_clears_panel_when_selection_vanishes(temp_db_path, monkeypatch, tk_root):
    screen, (_budi, ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._show_for(ani)
    tk_root.update_idletasks()
    assert screen._current_employee_id == ani

    _resolve(temp_db_path, ani, "2026-05-04")    # ANI's only issue -> gone
    screen.on_show()
    tk_root.update_idletasks()

    assert screen._current_employee_id is None
    texts = [w.cget("text") for w in screen.right.winfo_children()
             if isinstance(w, ctk.CTkLabel)]
    assert any("Pilih pegawai" in t for t in texts)
    screen.destroy()


def test_on_show_rereads_contact_mark(temp_db_path, monkeypatch, tk_root):
    screen, (budi, _ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._show_for(budi)
    tk_root.update_idletasks()
    assert "Tandai" in screen._contact_btn.cget("text")

    with get_connection(temp_db_path) as conn:
        mark_contacted(conn, employee_id=budi, year_month="2026-05")
    screen.on_show()
    tk_root.update_idletasks()
    assert screen._contact_btn.cget("text") == "✓ Sudah dihubungi"
    screen.destroy()


def test_on_show_without_month_behaves_like_init(temp_db_path, monkeypatch, tk_root):
    screen, _ = _make_screen(temp_db_path, monkeypatch, tk_root, seed=False)
    screen.on_show()   # no active month — must not raise
    tk_root.update_idletasks()
    assert screen._rows_cache == []
    assert screen._current_employee_id is None
    labels = [w for w in screen.list_frame.winfo_children()
              if isinstance(w, ctk.CTkLabel)]
    assert any("belum ada bulan aktif" in lbl.cget("text") for lbl in labels)
    screen.destroy()


def test_on_show_is_idempotent(temp_db_path, monkeypatch, tk_root):
    screen, (budi, _ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._show_for(budi)
    screen.on_show()
    screen.on_show()
    tk_root.update_idletasks()
    assert screen._current_employee_id == budi
    assert len(_list_row_frames(screen)) == 2
    screen.destroy()


# ---- messagebox -> toast / feedback ----------------------------------------

def test_salin_copies_and_shows_toast(temp_db_path, monkeypatch, tk_root):
    screen, (budi, _ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._show_for(budi)
    tk_root.update_idletasks()
    copied, toasts = [], []
    monkeypatch.setattr(mod.pyperclip, "copy", lambda t: copied.append(t))
    monkeypatch.setattr(mod, "show_success_toast",
                        lambda *a, **k: toasts.append((a, k)))
    screen._salin()
    assert len(copied) == 1 and "Budi" in copied[0]
    assert len(toasts) == 1
    assert toasts[0][1]["title"] == "Tersalin"
    screen.destroy()


def test_messagebox_import_removed():
    """The screen module no longer imports tkinter.messagebox."""
    assert not hasattr(mod, "messagebox")


def test_kirim_without_phone_warns_via_feedback(temp_db_path, monkeypatch, tk_root):
    screen, (_budi, ani) = _make_screen(temp_db_path, monkeypatch, tk_root)
    screen._show_for(ani)    # ANI has no phone
    tk_root.update_idletasks()
    warns, opened = [], []
    monkeypatch.setattr(mod.feedback, "show_warning",
                        lambda *a, **k: warns.append(a))
    monkeypatch.setattr(mod.webbrowser, "open", lambda url: opened.append(url))
    screen._kirim()
    assert len(warns) == 1
    assert opened == []
    screen.destroy()
