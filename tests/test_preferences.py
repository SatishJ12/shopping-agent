import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import preferences

PREFS_PATH = preferences.PREFS_PATH


def _cleanup():
    if os.path.exists(PREFS_PATH):
        os.remove(PREFS_PATH)


def test_load_preferences_missing_file_returns_empty():
    _cleanup()
    assert preferences.load_preferences() == {}


def test_save_preference_persists_to_disk():
    _cleanup()
    result = preferences.save_preference("organic_only", True)
    assert result == {"organic_only": True}

    with open(PREFS_PATH) as f:
        on_disk = json.load(f)
    assert on_disk == {"organic_only": True}
    _cleanup()


def test_save_preference_merges_with_existing():
    _cleanup()
    preferences.save_preference("organic_only", True)
    result = preferences.save_preference("max_price", 20)
    assert result == {"organic_only": True, "max_price": 20}
    _cleanup()
