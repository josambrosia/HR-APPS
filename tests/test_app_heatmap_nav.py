import src.ui.app as app_mod


def test_heatmap_in_insight_after_dashboard():
    src = open(app_mod.__file__, encoding="utf-8").read()
    assert '"Heatmap"' in src
    i_dash = src.index('"Dashboard", "Dashboard"')
    i_heat = src.index('"Heatmap", "Heatmap"')
    assert i_dash < i_heat, "Heatmap must be in INSIGHT group after Dashboard"
    assert 'name == "Heatmap"' in src, "router must handle Heatmap"
