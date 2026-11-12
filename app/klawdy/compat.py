"""Everything that depends on Claude Code internals lives here.

Claude Code has no public API for some things Klawdy shows (conversation titles, enabling or
disabling an MCP server, where synced skills live). Those details were read from Claude Code
{TESTED_WITH} and may change in any update, so every function here:

  * never raises — on unexpected data it logs a warning and returns a safe empty value;
  * is covered by `diagnose()`, shown in Settings › About and `python3 -m klawdy --diagnose`.

Official, stable mechanisms (hooks, `claude -p`, `--resume`, `claude mcp list/login`) are
used everywhere else.
"""
import fcntl
import glob
import json
import os
import re
import shutil
import subprocess
import time

from . import config

TESTED_WITH = "2.1.322"
__doc__ = __doc__.replace("{TESTED_WITH}", TESTED_WITH)

CLAUDE_DIR = os.path.join(config.HOME, ".claude")
CLAUDE_JSON = os.path.join(config.HOME, ".claude.json")
PROJECTS_DIR = os.path.join(CLAUDE_DIR, "projects")

_warned = set()


def _warn(key, *msg):
    if key not in _warned:
        _warned.add(key)
        config.log("compat warning:", key, *msg)


def short(text, n=38):
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------- the claude binary
def claude_bin():
    return shutil.which("claude") or os.path.join(config.HOME, ".local", "bin", "claude")


_version = [None]


def claude_version():
    if _version[0] is None:
        try:
            out = subprocess.run([claude_bin(), "--version"], capture_output=True, text=True,
                                 timeout=15, stdin=subprocess.DEVNULL).stdout
            m = re.search(r"\d+\.\d+\.\d+", out)
            _version[0] = m.group(0) if m else ""
        except Exception:
            _version[0] = ""
    return _version[0]


# ---------------------------------------------------------------- transcripts (~/.claude/projects/*/<id>.jsonl)
def find_transcript(sid):
    if not sid:
        return None
    try:
        for d in os.listdir(PROJECTS_DIR):
            p = os.path.join(PROJECTS_DIR, d, sid + ".jsonl")
            if os.path.exists(p):
                return p
    except OSError:
        pass
    return None


def _user_text(entry):
    c = (entry.get("message") or {}).get("content")
    if isinstance(c, list):
        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
    if isinstance(c, str):
        c = " ".join(c.split())
        if c and not c.startswith("<"):            # skip internal commands/reminders
            return c
    return ""


def transcript_info(path):
    """(cwd, first user message) of a transcript. ("", "") if unreadable."""
    cwd, first = "", ""
    if not path:
        return cwd, first
    try:
        with open(path, errors="replace") as f:
            for i, line in enumerate(f):
                if i > 400 or (cwd and first):
                    break
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(d, dict):
                    continue
                cwd = cwd or d.get("cwd") or ""
                if not first and d.get("type") == "user" and not d.get("isMeta"):
                    first = _user_text(d)
    except OSError:
        pass
    except Exception as e:  # noqa: BLE001 — unexpected format
        _warn("transcript_info", e)
    return cwd, first


TITLE_TYPES = {b'"custom-title"': "customTitle", b'"ai-title"': "aiTitle"}
_title_cache = {}      # path -> (checked_at, mtime, title)


def transcript_title(path):
    """Conversation title: /rename > Claude's automatic title > first message. Cached."""
    try:
        st = os.stat(path)
    except (OSError, TypeError):
        return ""
    now = time.time()
    c = _title_cache.get(path)
    if c and (c[1] == st.st_mtime or now - c[0] < 10):
        return c[2]
    title = ""
    try:
        with open(path, "rb") as f:
            f.seek(max(0, st.st_size - 600_000))
            for line in reversed(f.read().splitlines()):
                for marker, key in TITLE_TYPES.items():
                    if marker in line:
                        try:
                            title = json.loads(line).get(key) or ""
                        except ValueError:
                            title = ""
                        break
                if title:
                    break
    except OSError:
        pass
    except Exception as e:  # noqa: BLE001
        _warn("transcript_title", e)
    if not title:
        title = short(transcript_info(path)[1], 40)
    _title_cache[path] = (now, st.st_mtime, title)
    return title


def recent_transcripts(limit=25, exclude=()):
    """Most recent transcript files: [(mtime, path)]."""
    files = []
    try:
        for d in os.listdir(PROJECTS_DIR):
            pd = os.path.join(PROJECTS_DIR, d)
            if not os.path.isdir(pd):
                continue
            for fn in os.listdir(pd):
                if fn.endswith(".jsonl") and fn[:-6] not in exclude:
                    p = os.path.join(pd, fn)
                    files.append((os.path.getmtime(p), p))
    except OSError:
        pass
    files.sort(reverse=True)
    return files[:limit]


# ---------------------------------------------------------------- MCP servers
def parse_mcp_list(text):
    """Parse `claude mcp list` output: lines like 'name: target - ✔ Connected'."""
    servers = []
    for line in (text or "").splitlines():
        if ": " not in line or " - " not in line:
            continue
        left, status = line.rsplit(" - ", 1)
        name = left.split(": ", 1)[0].strip()
        if name:
            servers.append({"name": name, "status": status.strip()})
    return servers


def mcp_status_kind(status):
    """'ok' | 'auth' | 'unconfigured' | 'off' | 'error' — independent of the CLI wording."""
    s = (status or "").lower()
    if "connected" in s or "✔" in s or "✓" in s:
        return "ok"
    if "auth" in s:
        return "auth"
    if "not configured" in s:
        return "unconfigured"
    if s in ("off", "disabled"):
        return "off"
    return "error"


def mcp_list():
    try:
        r = subprocess.run([claude_bin(), "mcp", "list"], cwd=config.HOME, capture_output=True,
                           text=True, timeout=120, stdin=subprocess.DEVNULL)
        servers = parse_mcp_list(r.stdout)
        if not servers and r.stdout.strip() and "No MCP servers" not in r.stdout:
            _warn("mcp_list", "unrecognised output")
        return servers
    except Exception as e:  # noqa: BLE001
        _warn("mcp_list", e)
        return []


# The "disabled" list is the same one Claude Code's /mcp menu writes (per project, in
# ~/.claude.json). It is not a documented setting.
DISABLED_KEY = "disabledMcpServers"


def _read_claude_json():
    with open(CLAUDE_JSON) as f:
        return json.load(f)


def mcp_disabled(project=None):
    try:
        p = _read_claude_json().get("projects", {}).get(project or config.HOME, {})
        v = p.get(DISABLED_KEY, [])
        return set(v) if isinstance(v, list) else set()
    except FileNotFoundError:
        return set()
    except Exception as e:  # noqa: BLE001
        _warn("mcp_disabled", e)
        return set()


def mcp_set_enabled(name, enabled):
    """Enable/disable an MCP server for new conversations. Returns True if the change stuck.

    ~/.claude.json is also written by every running Claude Code session, so: take our own
    lock, re-read right before writing, replace atomically, keep a daily backup and verify."""
    lock_path = os.path.join(config.CACHE_DIR, "claude-json.lock")
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        backup = os.path.join(config.CACHE_DIR, f"claude.json.{time.strftime('%Y%m%d')}.bak")
        if os.path.exists(CLAUDE_JSON) and not os.path.exists(backup):
            shutil.copy2(CLAUDE_JSON, backup)
        for _attempt in range(3):
            try:
                st = os.stat(CLAUDE_JSON)
                data = _read_claude_json()
            except FileNotFoundError:
                st, data = None, {}
            if not isinstance(data, dict):
                _warn("mcp_set_enabled", "unexpected ~/.claude.json format")
                return False
            projects = data.setdefault("projects", {})
            projects.setdefault(config.HOME, {})
            for p in projects.values():
                if isinstance(p, dict):
                    lst = [x for x in p.get(DISABLED_KEY, []) if x != name]
                    if not enabled:
                        lst.append(name)
                    p[DISABLED_KEY] = lst
            tmp = CLAUDE_JSON + ".klawdy.tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.chmod(tmp, (st.st_mode & 0o777) if st else 0o600)
            # someone else wrote meanwhile? start over with their version
            try:
                if st and os.stat(CLAUDE_JSON).st_mtime != st.st_mtime:
                    os.remove(tmp)
                    continue
            except FileNotFoundError:
                pass
            os.replace(tmp, CLAUDE_JSON)
            break
    return (name in mcp_disabled()) != enabled


# ---------------------------------------------------------------- skills on disk
def read_frontmatter(path):
    """Simple fields of a SKILL.md YAML header (name, description, argument-hint)."""
    out, key = {}, None
    try:
        with open(path, errors="replace") as f:
            if f.readline().strip() != "---":
                return out
            for line in f:
                if line.strip() == "---":
                    break
                m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
                if m:
                    key, val = m.group(1), m.group(2).strip()
                    out[key] = "" if val in (">", "|", ">-", "|-") else val.strip("\"'")
                elif key and line.startswith((" ", "\t")):
                    out[key] = (out[key] + " " + line.strip()).strip()
    except OSError:
        pass
    return out


def skill_files():
    """[(invocation name, group, SKILL.md path)] for skills found on disk.

    Layouts (Claude Code 2.1): plugins synced from the account, skills synced from claude.ai,
    and the documented personal skills folder ~/.claude/skills/<name>/SKILL.md."""
    found = []
    try:
        for root in sorted(glob.glob(os.path.join(CLAUDE_DIR, "plugins", "synced", "*", "*", "skills"))):
            plugin = os.path.basename(os.path.dirname(root))
            for md in sorted(glob.glob(os.path.join(root, "*", "SKILL.md"))):
                found.append((plugin, plugin, md))
        for md in sorted(glob.glob(os.path.join(CLAUDE_DIR, "skills", "synced", "*", "*", "SKILL.md"))):
            found.append(("anthropic-skills", "anthropic-skills", md))
        for md in sorted(glob.glob(os.path.join(CLAUDE_DIR, "skills", "*", "SKILL.md"))):
            found.append(("", "personal", md))
    except Exception as e:  # noqa: BLE001
        _warn("skill_files", e)
    out = []
    for prefix, group, md in found:
        name = read_frontmatter(md).get("name") or os.path.basename(os.path.dirname(md))
        out.append((f"{prefix}:{name}" if prefix else name, group, md))
    return out


# ---------------------------------------------------------------- self-check
def diagnose():
    """[(check, ok, detail)] — what works on this machine / Claude Code version."""
    out = []
    ver = claude_version()
    out.append(("claude", bool(ver), ver or "not found"))
    if ver and ver != TESTED_WITH:
        out.append(("version", True, f"tested with {TESTED_WITH}, found {ver}: if something "
                                     "looks off, please report it"))
    recent = recent_transcripts(3)
    titles = [transcript_title(p) for _m, p in recent]
    out.append(("conversation titles", not recent or any(titles),
                f"{sum(1 for t in titles if t)}/{len(recent)} recent conversations have a title"
                if recent else "no transcripts yet"))
    try:
        data = _read_claude_json()
        ok = isinstance(data, dict) and isinstance(data.get("projects", {}), dict)
        out.append(("MCP on/off (~/.claude.json)", ok, "readable" if ok else "unexpected format"))
    except FileNotFoundError:
        out.append(("MCP on/off (~/.claude.json)", True, "no file yet"))
    except Exception as e:  # noqa: BLE001
        out.append(("MCP on/off (~/.claude.json)", False, str(e)))
    out.append(("skills", True, f"{len(skill_files())} found on disk"))
    for tool in ("jq", "gdbus"):
        out.append((tool, bool(shutil.which(tool)), shutil.which(tool) or "missing"))
    return out
