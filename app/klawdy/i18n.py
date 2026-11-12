"""Tiny i18n: source strings are pt-BR, `EN` maps them to English.

Language: setting "lang" ("pt" | "en"), or "auto" = system locale (pt* -> pt, anything else -> en).
Usage: _("Tamanho: {size}px", size=230)
"""
import os

from . import config
from .strings_en import EN

_lang = [None]


def lang():
    if _lang[0] is None:
        choice = config.setting("lang")
        if choice in ("pt", "en"):
            _lang[0] = choice
        else:
            env = (os.environ.get("LANGUAGE") or os.environ.get("LC_ALL")
                   or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "")
            _lang[0] = "pt" if env.lower().startswith("pt") else "en"
    return _lang[0]


def reset():
    """Call after the "lang" setting changes."""
    _lang[0] = None


def _(text, **kw):
    if lang() == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text
