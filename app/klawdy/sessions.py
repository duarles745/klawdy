"""Claude Code sessions as seen by the hooks, their names, and past conversations."""
import json
import os
import time

from . import compat, config
from .compat import short
from .i18n import _

DONE_SECS = 8
STALE_SECS = 6 * 3600
PRIORITY = {"attention": 3, "working": 2, "done": 1, "idle": 0}


def state_label(state):
    return {"attention": _("precisa de você"), "working": _("trabalhando"),
            "done": _("pronto"), "idle": _("parado")}.get(state, state)


# ---------------------------------------------------------------- names
def load_names():
    try:
        with open(config.NAMES_FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_name(sid, name):
    d = load_names()
    if name:
        d[sid] = name
    else:
        d.pop(sid, None)
    config.write_json(config.NAMES_FILE, d)


_tpath_cache = {}


def transcript_path(sid):
    p = _tpath_cache.get(sid)
    if p and os.path.exists(p):
        return p
    p = compat.find_transcript(sid)
    if p:
        _tpath_cache[sid] = p
    return p


def session_name(sid, cwd=None, fallback="", names=None):
    """Friendly name: '<title>' (or '<folder> · <title>' outside the home folder)."""
    names = load_names() if names is None else names
    title = names.get(sid) or compat.transcript_title(transcript_path(sid)) or fallback
    proj = os.path.basename(cwd or "") or "~"
    if not title:
        return f"{proj} #{sid[:4]}"
    if cwd and os.path.realpath(cwd) != os.path.realpath(config.HOME):
        return f"{proj} · {short(title, 34)}"
    return short(title, 40)


# ---------------------------------------------------------------- live sessions (hook state files)
def read_sessions(now=None, state_dir=None):
    """Sessions written by hook.sh, most urgent first. Removes stale files."""
    now = now or time.time()
    state_dir = state_dir or config.STATE_DIR
    names = load_names()
    sessions = []
    try:
        entries = os.listdir(state_dir)
    except FileNotFoundError:
        return sessions
    for fn in entries:
        if not fn.endswith(".json") or fn == os.path.basename(config.VOICE_FILE):
            continue
        path = os.path.join(state_dir, fn)
        try:
            with open(path) as f:
                s = json.load(f)
        except Exception:
            continue
        if not isinstance(s, dict):
            continue
        if now - s.get("time", 0) > STALE_SECS:
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        st = s.get("state", "idle")
        if st == "attention":
            msg = (s.get("message") or "").lower()
            if s.get("ntype") == "idle_prompt" or "waiting for your input" in msg:
                st = "done"             # only waiting for the next prompt
        if st == "done" and now - s.get("time", 0) > DONE_SECS:
            st = "idle"
        s["eff"] = st
        s["sid"] = fn[:-5]
        s["name"] = session_name(s["sid"], s.get("cwd"), s.get("title", ""), names)
        sessions.append(s)
    sessions.sort(key=lambda s: (PRIORITY.get(s["eff"], 0), s.get("time", 0)), reverse=True)
    return sessions


def read_voice(now=None):
    now = now or time.time()
    try:
        with open(config.VOICE_FILE) as f:
            v = json.load(f)
    except Exception:
        return None
    age = now - v.get("time", 0)
    if v.get("state") == "listening" and age > 12:
        return None
    if v.get("state") in ("done", "error") and age > 3:
        return None
    if v.get("state") == "running" and age > 900:
        return None
    return v


# ---------------------------------------------------------------- conversations to send a prompt to
def list_targets():
    """Options for the Ctrl+. picker. The first one (default) is always the most recent."""
    now = time.time()
    live = []
    try:
        for fn in os.listdir(config.STATE_DIR):
            if not fn.endswith(".json") or fn == os.path.basename(config.VOICE_FILE):
                continue
            try:
                with open(os.path.join(config.STATE_DIR, fn)) as f:
                    s = json.load(f)
            except Exception:
                continue
            if now - s.get("time", 0) > STALE_SECS or not s.get("tag"):
                continue
            s["sid"] = fn[:-5]
            live.append(s)
    except FileNotFoundError:
        pass
    live.sort(key=lambda s: s.get("time", 0), reverse=True)
    live_ids = {s["sid"] for s in live}

    past = []
    for mt, p in compat.recent_transcripts(25, exclude=live_ids):
        cwd, first = compat.transcript_info(p)
        if not first:
            continue
        past.append({"sid": os.path.basename(p)[:-6], "cwd": cwd or config.HOME, "first": first, "mtime": mt})
        if len(past) >= 8:
            break

    out = []
    for s in live:
        sid = s["sid"]
        cwd = s.get("cwd") or config.HOME
        tcwd, first = compat.transcript_info(transcript_path(sid))
        name = session_name(sid, cwd, s.get("title") or first)
        cwd = tcwd or cwd  # folder where the conversation started (needed by --resume)
        where = _("terminal") if s.get("tty") else _("segundo plano")
        label = f"🟢 {name} · {state_label(s.get('state'))} ({where})"
        out.append({"kind": "live", "sid": sid, "tag": s["tag"], "cwd": cwd, "label": label,
                    "time": s.get("time", 0)})
    for p in past:
        when = time.strftime("%d/%m %H:%M", time.localtime(p["mtime"]))
        name = session_name(p["sid"], p["cwd"], p["first"])
        out.append({"kind": "past", "sid": p["sid"], "cwd": p["cwd"], "time": p["mtime"],
                    "label": f"🕘 {when} · {name}"})

    out.sort(key=lambda o: o["time"], reverse=True)
    if out:
        out[0] = dict(out[0], label=_("⭐ Mais recente: ") + out[0]["label"][2:])
    out.append({"kind": "new_term", "label": _("＋ Nova conversa (abre um terminal)")})
    out.append({"kind": "new_bg", "label": _("＋ Nova conversa em segundo plano")})
    return out
