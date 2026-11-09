"""Tiny persisted settings: ~/.config/lyrics-overlay/settings.json."""

import json
import os

PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                    "lyrics-overlay", "settings.json")
DEFAULTS = {"font_scale": 1.0, "words_at_once": 1, "word_mode": True, "inverted": False, "clock_scale": 1.0}


def load():
    try:
        with open(PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(values):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w") as f:
            json.dump(values, f)
    except OSError:
        pass
