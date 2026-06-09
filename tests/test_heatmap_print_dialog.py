def test_dialog_defaults_and_confirm(tk_root):
    from src.ui.components.heatmap_print_dialog import HeatmapPrintDialog
    captured = {}
    d = HeatmapPrintDialog(tk_root, on_confirm=lambda s, o: captured.update(scope=s, outlier=o))
    tk_root.update_idletasks()
    assert d.scope_var.get() == "full"
    assert d.outlier_var.get() == "inc"
    d.scope_var.set("matrix")
    d.outlier_var.set("exc")
    d._confirm()
    assert captured == {"scope": "matrix", "outlier": "exc"}
