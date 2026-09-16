"""Durable shopper preferences (e.g. 'always organic'), stored as JSON on disk
so they apply automatically in later sessions without being restated."""

import json
import os

PREFS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preferences.json")


def load_preferences() -> dict:
    if not os.path.exists(PREFS_PATH):
        return {}
    with open(PREFS_PATH) as f:
        return json.load(f)


def save_preference(key: str, value) -> dict:
    current = load_preferences()
    current[key] = value
    with open(PREFS_PATH, "w") as f:
        json.dump(current, f, indent=2)
    return current
