# -*- coding: utf-8 -*-
"""
Minimal i18n for the desktop app (English default + German).

Usage:
    from i18n import t, current_language, set_language, LANGS, restart_app
    label.setText(t("refresh"))
    label.setText(t("connected", name="Wohnzimmer"))   # formatted

The chosen language is stored in app_config.json next to the app and read at
startup. Switching language saves it and restarts the app (clean and reliable,
instead of live-retranslating every Qt widget).
"""

import json
import os
import sys

LANGS = {"en": "English", "de": "Deutsch"}
_DEFAULT = "en"

_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.json")
_lang = None


def _load_cfg() -> dict:
    try:
        with open(_cfg_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def current_language() -> str:
    global _lang
    if _lang is None:
        _lang = _load_cfg().get("language", _DEFAULT)
        if _lang not in LANGS:
            _lang = _DEFAULT
    return _lang


def set_language(lang: str) -> None:
    global _lang
    if lang not in LANGS:
        return
    _lang = lang
    data = _load_cfg()
    data["language"] = lang
    try:
        with open(_cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def t(key: str, **kwargs) -> str:
    """Translate a key for the current language, with optional str.format args."""
    table = STR.get(current_language(), {})
    s = table.get(key)
    if s is None:
        s = STR.get("en", {}).get(key, key)
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


def restart_app() -> None:
    """Relaunch the app so the new language takes effect. Caller should then quit."""
    import subprocess
    try:
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable] + sys.argv[1:])
        else:
            subprocess.Popen([sys.executable] + sys.argv)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# String table. Keys are grouped by area. English is the source of truth;
# any missing key falls back to English, then to the key itself.
# ---------------------------------------------------------------------------

STR = {
    "en": {
        # --- language switch UI ---
        "language": "Language",
        "restart_title": "Restart required",
        "restart_msg": "The language will change after a restart. Restart now?",
    },
    "de": {
        "language": "Sprache",
        "restart_title": "Neustart nötig",
        "restart_msg": "Die Sprache wird nach einem Neustart übernommen. Jetzt neu starten?",
    },
}
