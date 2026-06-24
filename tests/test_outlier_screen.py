"""Smoke test for the Outlier screen — verifies it constructs without error
against a temp DB with sample data. Deep UI behaviour is covered by the
src/db/outlier.py unit tests."""
import customtkinter as ctk

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.db.outlier import exclude_employee


def test_outlier_screen_constructs(temp_db_path, monkeypatch, tk_root):
    # Point the screen module's DB_PATH at the temp DB
    import src.ui.screens.outlier as outlier_mod
    monkeypatch.setattr(outlier_mod, "DB_PATH", temp_db_path)

    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="X")
        for emp in (a, b):
            upsert_attendance(
                conn, employee_id=emp, tanggal="2026-04-01", hari="Senin",
                tipe="Hari Kerja", jadwal="08.00 - 16.00",
                masuk="08.05", keluar="16.00", kerja_jam=8.0,
                lembur_jam=None, terlambat_menit=5, has_issue=0,
                imported_from="W1.xls",
            )
        set_setting(conn, "current_month", "2026-04")
        exclude_employee(conn, a, "2026-04")
        conn.commit()

    screen = outlier_mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()


def test_outlier_screen_constructs_with_no_active_month(temp_db_path, monkeypatch, tk_root):
    """Empty state — no current_month set — must not crash."""
    import src.ui.screens.outlier as outlier_mod
    monkeypatch.setattr(outlier_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)

    screen = outlier_mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()


def test_outlier_screen_binds_ctrl_f(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.outlier as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()
    bindings = screen.bind("<Control-f>")
    assert bindings != ""
    screen.destroy()


def test_outlier_search_filters_disertakan_only(temp_db_path, monkeypatch, tk_root):
    """SearchBar filters Disertakan section by name; Dikecualikan stays
    untouched (the latter is short by design and excluding a hidden
    employee from search would be confusing)."""
    import src.ui.screens.outlier as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-05")
        e1 = upsert_employee(conn, no_staff="1", nama="BUDI", dept="X")
        e2 = upsert_employee(conn, no_staff="2", nama="ANI", dept="Y")
        e3 = upsert_employee(conn, no_staff="3", nama="CITRA", dept="Z")
        for eid in (e1, e2, e3):
            upsert_attendance(
                conn, employee_id=eid, tanggal="2026-05-01", hari="Jumat",
                tipe="Hari Kerja", jadwal="08.00 - 16.00",
                masuk="08.00", keluar="16.00", kerja_jam=8.0,
                lembur_jam=None, terlambat_menit=0, has_issue=0,
                imported_from="W1.xls",
            )
        conn.commit()
    screen = mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()
    assert len(screen._disertakan_rows) == 3
    screen._apply_filter("bud")
    tk_root.update_idletasks()
    visible = [r for r in screen._disertakan_rows if r.winfo_manager() == "pack"]
    assert len(visible) == 1
    screen._apply_filter("")
    tk_root.update_idletasks()
    visible = [r for r in screen._disertakan_rows if r.winfo_manager() == "pack"]
    assert len(visible) == 3
    screen.destroy()


def test_outlier_header_has_badge_no_searchbar(temp_db_path, monkeypatch, tk_root):
    """Regression guard for v16.0.2 hotfix: the BULAN AKTIF badge must
    be in the Outlier header (side='right'), and SearchBar must NOT be
    in the header — it has been relocated to a slim filter row between
    the header and the scrollable content.

    Prevents reintroducing the v16.0.1 layout where SearchBar competed
    with the badge for right-side space.
    """
    from src.ui.components.search_bar import SearchBar
    import src.ui.screens.outlier as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()

    # Locate header (grid row 0 child of screen).
    header = None
    for child in screen.winfo_children():
        info = child.grid_info() if hasattr(child, "grid_info") else {}
        if isinstance(child, ctk.CTkFrame) and info.get("row") == 0:
            header = child
            break
    assert header is not None, "Header frame (grid row 0) must exist"

    # SearchBar must NOT be among header's children.
    def _has_searchbar(widget):
        try:
            children = widget.winfo_children()
        except Exception:
            return False
        for c in children:
            if isinstance(c, SearchBar):
                return True
            if _has_searchbar(c):
                return True
        return False

    assert not _has_searchbar(header), \
        "SearchBar must NOT be in the Outlier header (relocated v16.0.2)"

    # BULAN AKTIF badge must be in header, packed side='right'.
    badges = []
    for grandchild in header.winfo_children():
        if isinstance(grandchild, ctk.CTkFrame):
            for label in grandchild.winfo_children():
                try:
                    if isinstance(label, ctk.CTkLabel) and \
                       "BULAN AKTIF" in str(label.cget("text")):
                        badges.append(grandchild)
                        break
                except Exception:
                    pass
    assert len(badges) >= 1, "BULAN AKTIF badge must exist in header"
    pi_badge = badges[0].pack_info()
    assert pi_badge.get("side") == "right", \
        f"BULAN AKTIF badge must be packed side='right', got {pi_badge.get('side')}"

    # SearchBar must exist somewhere on the screen (relocated to filter row).
    assert hasattr(screen, "_search"), "screen._search must exist"
    assert isinstance(screen._search, SearchBar)
    screen.destroy()


def test_outlier_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.outlier as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()
