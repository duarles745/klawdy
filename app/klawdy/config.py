"""Paths, settings and migration from the old "claude-mascot" layout.

This module must stay free of GTK imports: the voice process (a separate venv) and the
tests import it too.
"""
import json
import os
import shutil
import time

HOME = os.path.expanduser("~")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../klawdy (install dir)


def _xdg(var, default):
    return os.path.join(os.environ.get(var) or os.path.join(HOME, default), "klawdy")


STATE_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "klawdy")
CONF_DIR = _xdg("XDG_CONFIG_HOME", ".config")
CACHE_DIR = _xdg("XDG_CACHE_HOME", ".cache")

SETTINGS_FILE = os.path.join(CONF_DIR, "config.json")
NAMES_FILE = os.path.join(CONF_DIR, "names.json")
POS_FILE = os.path.join(CONF_DIR, "pos.json")
ANSWER_FILE = os.path.join(STATE_DIR, "answer.result")
VOICE_FILE = os.path.join(STATE_DIR, "voice.json")
TRIGGER_FILE = os.path.join(STATE_DIR, "voice.trigger")
PERM_DIR = os.path.join(STATE_DIR, "perm")           # permission requests from permission.sh
MASCOT_PID = os.path.join(STATE_DIR, "mascot.pid")   # permission.sh only waits while Klawdy runs
PERM_HOOK = os.path.join(APP_DIR, "permission.sh")
LAST_ANSWER_MD = os.path.join(CACHE_DIR, "last-answer.md")
LOG_FILE = os.path.join(CACHE_DIR, "klawdy.log")
VOICE_LOG = os.path.join(CACHE_DIR, "voice.log")
SOUNDS_DIR = os.path.join(APP_DIR, "sounds")
VENV_PY = os.path.join(APP_DIR, "venv", "bin", "python")

# Safe defaults: anything that lets Claude act without a human approving each step is OFF.
DEFAULTS = {
    "lang": "auto",          # "auto" | "pt" | "en"
    "size": 230,
    "color": "orange",
    "costume": "none",
    "scenery": True,
    "sounds": True,
    "speak": False,          # read answers aloud (spd-say)
    "voice": False,          # always-on wake word listening
    "voice_installs": False,  # let voice commands install downloaded programs (asks for password)
    "wake_words": [],        # extra wake words/regexes; empty = language default
    "chrome": False,         # Claude in Chrome for background/voice requests (no per-step approval)
    "terminal": None,        # force a terminal emulator (ptyxis, gnome-terminal, konsole, kitty…)
    "skill_gear": {},
    "recent_skills": [],
}


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def setting(key):
    return load_settings().get(key, DEFAULTS.get(key))


def write_json(path, data):
    """Atomic write (temp file + rename) so readers never see half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def save_settings(d):
    try:
        write_json(SETTINGS_FILE, d)
    except OSError as e:
        log("could not save settings:", e)


def set_setting(key, value):
    d = load_settings()
    d[key] = value
    save_settings(d)


def log(*a, path=None):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path or LOG_FILE, "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- migration (claude-mascot -> klawdy)
OLD_CONF = os.path.join(HOME, ".config", "claude-mascot")


def migrate():
    """Copy settings, session names and position from the pre-2.0 "claude-mascot" folders (once).

    Security-sensitive options are not carried over silently: Chrome and voice-installs start
    OFF in 2.0 and have to be enabled again (with an explicit warning)."""
    marker = os.path.join(CONF_DIR, ".migrated")
    if os.path.exists(marker) or not os.path.isdir(OLD_CONF):
        return False
    os.makedirs(CONF_DIR, exist_ok=True)
    for name in ("names.json", "pos.json"):
        src, dst = os.path.join(OLD_CONF, name), os.path.join(CONF_DIR, name)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
    try:
        with open(os.path.join(OLD_CONF, "config.json")) as f:
            old = json.load(f)
    except Exception:
        old = {}
    new = load_settings()
    for k, v in old.items():
        if k in ("chrome",):
            continue
        new.setdefault(k, v)
    # voice used to default to ON; keep it on only for people who actually installed it
    if "voice" not in old and os.path.exists(VENV_PY):
        new.setdefault("voice", True)
    save_settings(new)
    with open(marker, "w") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    log("migrated settings from", OLD_CONF)
    return True
