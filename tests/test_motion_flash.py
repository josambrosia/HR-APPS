"""Item 10 & 17 — kilat pada baris yang baru berubah."""
import time
from tkinter import ttk
import customtkinter as ctk

from src.ui import motion
from src.ui.components.tree_style import style_treeview


def test_flash_row_mengembalikan_latar_semula(tk_root):
    motion.set_enabled(False)
    style_treeview("Fl.Treeview")
    t = ttk.Treeview(tk_root, style="Fl.Treeview", show="tree", height=3)
    t.insert("", "end", iid="a", text="Andi")
    try:
        motion.flash_row(t, "a", "#10B981", "#141414")
        # NOTE penyesuaian dari rencana: ttk.tag_configure(tag, opt) mengembalikan
        # objek Tcl_Obj, bukan str Python — str(v) == '#141414' tapi v == '#141414'
        # bernilai False. Bandingkan lewat str() supaya niat tesnya (warna kembali
        # ke rupa semula) tidak salah dibaca sebagai kegagalan.
        assert str(t.tag_configure(motion.FLASH_TAG, "background")) in ("#141414", "")
    finally:
        t.destroy()


def test_flash_row_pada_baris_yang_sudah_lenyap_tidak_meledak(tk_root):
    motion.set_enabled(True)
    try:
        style_treeview("Fl2.Treeview")
        t = ttk.Treeview(tk_root, style="Fl2.Treeview", show="tree", height=3)
        t.insert("", "end", iid="a", text="Andi")
        motion.flash_row(t, "a", "#10B981", "#141414")
        t.delete("a")
        tk_root.update()          # tidak boleh melempar
    finally:
        motion.set_enabled(False)


def test_flash_widget_mengembalikan_warna_semula(tk_root):
    motion.set_enabled(False)
    f = ctk.CTkFrame(tk_root, fg_color="#141414")
    try:
        motion.flash_widget(f, "#10B981", "#141414")
        assert f.cget("fg_color") == "#141414"
    finally:
        f.destroy()


def test_history_list_menandai_baris_teratas_saat_diminta(tk_root):
    """Item 17: hasil kerja yang barusan dilakukan muncul sebagai baris
    teratas yang tampilannya identik dengan baris lama."""
    from src.ui.components.history_list import HistoryList, HistoryRow
    motion.set_enabled(False)
    hl = HistoryList(tk_root, header="RIWAYAT", empty_text="kosong")
    try:
        hl.set_rows([HistoryRow(time="10:00", title="Laporan Juli.xlsx", tag="OK")],
                    flash_first=True)
        assert hl._first_row is not None
    finally:
        hl.destroy()


def test_flash_row_benar_benar_berkilat_saat_motion_menyala(tk_root):
    """Tes lain di berkas ini semuanya berjalan dengan motion MATI, di mana
    flash_row langsung mendarat di keadaan akhir dan restore() dipanggil
    seketika — logika tween-nya sendiri tidak pernah dieksekusi. Yang ini
    menutup lubang itu: warna latar harus benar-benar singgah di titik
    tengah antara from_color dan to_color sebelum tag kilat dilepas."""
    motion.set_enabled(True)
    try:
        style_treeview("Fl3.Treeview")
        t = ttk.Treeview(tk_root, style="Fl3.Treeview", show="tree", height=3)
        t.pack()
        t.insert("", "end", iid="a", text="Andi")
        tk_root.update()

        from_color, to_color = "#10B981", "#141414"
        motion.flash_row(t, "a", from_color, to_color)
        tk_root.update()
        first = str(t.tag_configure(motion.FLASH_TAG, "background"))
        assert first == from_color, "kilat tidak mulai dari warna sumber"
        assert motion.FLASH_TAG in t.item("a", "tags")

        seen_mid = False
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 3.0:
            tk_root.update()
            cur = str(t.tag_configure(motion.FLASH_TAG, "background"))
            if cur not in (from_color, to_color):
                seen_mid = True
            if motion.FLASH_TAG not in t.item("a", "tags"):
                break
        assert seen_mid, "warna tidak pernah singgah di titik tengah — tween tidak jalan"
        assert motion.FLASH_TAG not in t.item("a", "tags"), \
            "tag kilat tidak dilepas setelah animasi selesai"
        t.destroy()
    finally:
        motion.set_enabled(False)


def test_item10_resolve_sungguhan_memasang_kilat_pada_baris_resolved(
    temp_db_path, monkeypatch, tk_root,
):
    """Bukti wiring end-to-end (bukan cuma unit motion.flash_row): benar-benar
    resolve satu issue lewat IssuesScreen._on_save() dan pastikan baris yang
    mendarat di resolved_tree membawa tag kilat SEKETIKA (sebelum timer
    tween pertama sempat jalan) — supaya user, bukan cuma tes, tahu baris
    mana yang barusan berubah pada daftar panjang."""
    import src.ui.screens.issues as issues_mod
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.db.settings import set_setting
    from src.core.reason_mapper import REASON_LABELS

    monkeypatch.setattr(issues_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        eid = upsert_employee(conn, no_staff="1", nama="BUDI", dept="X")
        upsert_attendance(
            conn, employee_id=eid, tanggal="2026-05-04", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-05")

    motion.set_enabled(True)
    try:
        s = issues_mod.IssuesScreen(tk_root)
        try:
            open_children = s.open_tree.get_children()
            assert open_children, "seeding gagal — tidak ada open issue"
            iid = open_children[0]
            s.open_tree.selection_set(iid)
            s._on_select_open(None)
            assert s.selected_id is not None

            s.cat_var.set(REASON_LABELS["izin_sakit"])
            s._on_save()

            assert iid in s.resolved_tree.get_children(), \
                "baris tidak pindah ke resolved_tree setelah resolve"
            assert motion.FLASH_TAG in s.resolved_tree.item(iid, "tags"), \
                "resolve sungguhan tidak memasang tag kilat — item 10 tidak terpasang"
        finally:
            s.destroy()
    finally:
        motion.set_enabled(False)


def test_flash_widget_benar_benar_berkilat_saat_motion_menyala(tk_root):
    """Sisi positif dari test_flash_widget_mengembalikan_warna_semula (yang
    berjalan dengan motion mati): fg_color harus benar-benar melintasi
    warna antara, bukan cuma melompat langsung ke to_color."""
    motion.set_enabled(True)
    try:
        f = ctk.CTkFrame(tk_root, fg_color="#141414")
        f.pack()
        tk_root.update()

        # NOTE penyesuaian dari rencana: berbeda dari flash_row (yang memasang
        # from_color secara sinkron sebelum menjadwalkan tween), flash_widget
        # TIDAK mengatur from_color seketika — frame pertama baru terpasang
        # saat timer after() pertama benar-benar jatuh tempo. Jadi tes ini
        # tidak boleh mengasumsikan cget() seketika setelah pemanggilan sudah
        # menunjukkan from_color; ia harus menunggu lewat loop waktu nyata.
        from_color, to_color = "#0F2218", "#141414"
        motion.flash_widget(f, from_color, to_color)

        seen_mid = False
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 3.0:
            tk_root.update()
            cur = f.cget("fg_color")
            if cur not in (from_color, to_color):
                seen_mid = True
            if cur == to_color and seen_mid:
                break
        assert seen_mid, "warna widget tidak pernah singgah di titik tengah"
        assert f.cget("fg_color") == to_color
        f.destroy()
    finally:
        motion.set_enabled(False)
