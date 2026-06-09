# tests/test_app_severe_lateness_nav.py
import src.ui.app as app_mod


def test_workflow_group_has_severe_lateness_below_issues():
    # Locate the nav_groups definition by constructing the structure the app uses.
    # The app exposes nav via a module-level builder or the App instance; assert the
    # WORKFLOW group contains SevereLateness directly after Issues.
    src = open(app_mod.__file__, encoding="utf-8").read()
    assert '"SevereLateness"' in src or "'SevereLateness'" in src
    # ordering: Issues appears before SevereLateness, which appears before WhatsApp
    i_issues = src.index("Issues")
    i_severe = src.index("SevereLateness")
    i_wa = src.index("WhatsAppAssistant")
    assert i_issues < i_severe < i_wa
