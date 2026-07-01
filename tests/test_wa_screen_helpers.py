from src.ui.screens.whatsapp_assistant import _initials, _avatar_tint


def test_initials():
    assert _initials("RIZKY PRATAMA") == "RP"
    assert _initials("SITI") == "SI"
    assert _initials("") == "?"


def test_avatar_tint_deterministic_and_valid():
    a = _avatar_tint("RIZKY PRATAMA")
    assert a == _avatar_tint("RIZKY PRATAMA")     # stable
    assert a.startswith("#") and len(a) == 7
