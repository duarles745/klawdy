"""Things Klawdy does outside its own window: terminals, background runs, sounds, D-Bus."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

from . import compat, config
from .i18n import _


def python_env():
    """Environment for child processes that import the klawdy package."""
    env = dict(os.environ, GDK_BACKEND="x11")
    env["PYTHONPATH"] = config.APP_DIR + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def spawn_self(*args, detach=True):
    """Run `python3 -m klawdy <args>` in the background."""
    return subprocess.Popen([sys.executable, "-m", "klawdy", *args], env=python_env(),
                            start_new_session=detach, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- terminal
def terminal_cmd(cmd, cwd=None):
    """Command that opens `cmd` in a new window of whatever terminal is installed."""
    cwd = cwd or config.HOME
    pref = config.setting("terminal")
    options = [
        ("ptyxis", ["ptyxis", "--new-window", "-d", cwd, "--"]),
        ("gnome-terminal", ["gnome-terminal", "--working-directory", cwd, "--"]),
        ("kgx", ["kgx", "-e"]),
        ("konsole", ["konsole", "--workdir", cwd, "-e"]),
        ("xfce4-terminal", ["xfce4-terminal", "--working-directory", cwd, "-x"]),
        ("tilix", ["tilix", "-w", cwd, "-e"]),
        ("kitty", ["kitty", "-d", cwd]),
        ("alacritty", ["alacritty", "--working-directory", cwd, "-e"]),
        ("wezterm", ["wezterm", "start", "--cwd", cwd, "--"]),
        ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
        ("xterm", ["xterm", "-e"]),
    ]
    if pref:
        options.sort(key=lambda o: o[0] != pref)
    for name, prefix in options:
        if shutil.which(name):
            return prefix + cmd
    return ["xterm", "-e"] + cmd


def launch_claude(prompt=None, resume=None, cwd=None, fork=False):
    """Open Claude Code in a new terminal (optionally resuming a conversation).

    Interactive sessions ask before every Chrome action, so --chrome is safe here."""
    args = ["--chrome"] if config.setting("chrome") else []
    if resume:
        args += ["--resume", resume] + (["--fork-session"] if fork else [])
    if prompt:
        args.append(prompt)
    cmd = ["bash", "-lc", 'claude "$@"; exec bash', "claude"] + args
    cwd = cwd if cwd and os.path.isdir(cwd) else config.HOME
    subprocess.Popen(terminal_cmd(cmd, cwd), cwd=cwd)


def launch_prompt_popup(skill=None):
    args = ["--prompt"] + (["--skill", skill] if skill else [])
    spawn_self(*args)


# ---------------------------------------------------------------- voice process
def voice_installed():
    return os.path.exists(config.VENV_PY)


def voice_running():
    return subprocess.run(["pgrep", "-f", "-m klawdy.voice"], capture_output=True).returncode == 0


def start_voice():
    if not voice_installed() or voice_running():
        return
    env = python_env()
    env.pop("GDK_BACKEND", None)
    subprocess.Popen([config.VENV_PY, "-m", "klawdy.voice"], env=env, start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- feedback
def play_sound(name):
    if not config.setting("sounds"):
        return
    path = os.path.join(config.SOUNDS_DIR, name + ".wav")
    player = shutil.which("pw-play") or shutil.which("paplay") or shutil.which("aplay")
    if player and os.path.exists(path):
        subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(title, body):
    if shutil.which("notify-send"):
        subprocess.Popen(["notify-send", "-a", "Klawdy", "-i", "dialog-information", title, body])


# ---------------------------------------------------------------- GNOME extension (D-Bus)
DBUS_PATHS = [("/org/klawdy/Klawdy", "org.klawdy.Klawdy"),
              ("/org/claude/Mascot", "org.claude.Mascot")]      # pre-2.0 extension, until re-login


def shell_call(method, *args):
    """Call the GNOME Shell extension. Returns True/False, or None if no extension answers."""
    if not shutil.which("gdbus"):
        return None
    for path, iface in DBUS_PATHS:
        try:
            r = subprocess.run(["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
                                "--object-path", path, "--method", f"{iface}.{method}", *args],
                               capture_output=True, text=True, timeout=5)
        except Exception:
            continue
        if r.returncode == 0:
            return "true" in r.stdout
    return None


# ---------------------------------------------------------------- background runs (claude -p)
def perm_settings():
    """--settings JSON that adds the popup permission hook to one background run only."""
    hook = {"type": "command", "command": shlex.quote(config.PERM_HOOK), "timeout": 300}
    return json.dumps({"hooks": {"PermissionRequest": [{"hooks": [hook]}]}})


def answer_permission(req_id, allow):
    """Answer a request left by permission.sh (atomic write: the hook polls for the file)."""
    req_id = "".join(c for c in str(req_id) if c.isalnum() or c == "-")
    if not req_id:
        return
    path = os.path.join(config.PERM_DIR, req_id + ".answer")
    try:
        with open(path + ".tmp", "w") as f:
            f.write("allow" if allow else "deny")
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def run_main(prompt, resume=None, cwd=None, fork=False):
    """Run a prompt with `claude -p` and leave the answer for the mascot.

    There is no terminal to ask for approval, so a PermissionRequest hook (permission.sh) asks
    in a popup next to the mascot; without an answer the tool is denied, as `-p` always did.
    Chrome is added only when the user enabled it in Settings (with a warning): web pages can
    contain instructions meant for Claude (prompt injection)."""
    os.makedirs(config.STATE_DIR, exist_ok=True)
    started = time.strftime("%Y-%m-%d %H:%M")
    cmd = [compat.claude_bin(), "-p", "--output-format", "json", "--settings", perm_settings()]
    if resume:
        cmd += ["--resume", resume] + (["--fork-session"] if fork else [])
    if config.setting("chrome"):
        # the prompt goes through stdin because --allowedTools swallows the following arguments
        cmd += ["--chrome", "--allowedTools", "mcp__claude-in-chrome"]
    if not (cwd and os.path.isdir(cwd)):
        cwd = config.HOME
    sid = None
    try:
        r = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, timeout=1800)
        out = (r.stdout or "").strip()
        try:
            j = json.loads(out)
            answer = (j.get("result") or "").strip() or _("(sem resposta)")
            sid = j.get("session_id")
            ok = r.returncode == 0 and not j.get("is_error")
        except ValueError:
            answer = out or (r.stderr or "").strip() or _("(sem resposta)")
            ok = r.returncode == 0
    except Exception as e:  # noqa: BLE001
        answer, ok = f"{type(e).__name__}: {e}", False
    save_answer(prompt, answer, ok, started, sid=sid, cwd=cwd)
    notify(_("Claude respondeu") if ok else _("Claude: erro"), answer[:400])


def save_answer(prompt, answer, ok, started, sid=None, cwd=None, title=None):
    try:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        with open(config.LAST_ANSWER_MD, "w") as f:
            f.write(f"# {title or _('Pedido')} ({started})\n\n{prompt}\n\n# {_('Resposta')}\n\n{answer}\n")
    except OSError:
        pass
    config.write_json(config.ANSWER_FILE, {"prompt": prompt, "answer": answer, "ok": ok,
                                           "time": time.time(), "sid": sid, "cwd": cwd})


def send_main(tag, sid, cwd, text):
    """Type the message into the conversation's terminal (via the GNOME extension)."""
    time.sleep(0.3)  # let the popup close before moving the focus
    if shell_call("Send", tag, text):
        return
    # Without the extension we cannot type into the terminal: answer in a copy of the
    # conversation (same context) in the background, without touching the open session.
    notify("Klawdy", _("Não consegui enviar para o terminal (extensão do GNOME inativa).\n"
                       "Respondendo numa cópia da conversa em segundo plano…"))
    run_main(text, resume=sid, cwd=cwd, fork=True)
