# tests/test_changelog_v17.py
from src import config


def test_version_is_v17():
    assert config.APP_VERSION == "17.0.0"


def test_changelog_has_v17_entry_on_top():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "17.0.0"
    kinds = [k for k, _ in top["changes"]]
    assert "feat" in kinds
    assert any("Severe Lateness" in desc for _, desc in top["changes"])
