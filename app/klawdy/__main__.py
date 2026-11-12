"""Entry point.

  python3 -m klawdy                       floating mascot
  python3 -m klawdy --prompt [--skill S]  Ctrl+. prompt box
  python3 -m klawdy --run [--resume ID] [--cwd DIR] -- TEXT   background request (claude -p)
  python3 -m klawdy --send TAG SID CWD TEXT                   type into a session's terminal
  python3 -m klawdy --diagnose            compatibility check (prints and exits)
  python3 -m klawdy --version
"""
import os
import sys

from . import __version__, config


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    config.migrate()
    cmd = argv[0] if argv else ""
    if cmd == "--version":
        print(f"Klawdy {__version__}")
        return 0
    if cmd == "--diagnose":
        from . import compat
        for name, ok, detail in compat.diagnose():
            print(f"{'OK ' if ok else 'ERR'} {name}: {detail}")
        return 0
    if cmd == "--run":
        a, opts = argv[1:], {}
        while len(a) >= 2 and a[0] in ("--resume", "--cwd"):
            opts[a[0][2:]] = a[1]
            a = a[2:]
        if a and a[0] == "--":
            a = a[1:]
        from . import actions
        actions.run_main(" ".join(a), resume=opts.get("resume"), cwd=opts.get("cwd"))
        return 0
    if cmd == "--send" and len(argv) >= 5:
        from . import actions
        actions.send_main(argv[1], argv[2], argv[3], " ".join(argv[4:]))
        return 0

    from . import palette
    palette.set_color_theme(config.setting("color"))
    if cmd == "--prompt":
        skill = argv[2] if len(argv) >= 3 and argv[1] == "--skill" else None
        from .ui_windows import prompt_main
        prompt_main(skill)
        return 0
    if cmd:
        print(__doc__)
        return 2
    os.makedirs(config.STATE_DIR, exist_ok=True)
    from . import actions
    if config.setting("voice"):
        actions.start_voice()
    from .ui_mascot import mascot_main
    mascot_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
