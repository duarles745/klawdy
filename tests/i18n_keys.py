"""Collect every translatable string: _("...") literals plus theme/costume/group names."""
import ast
import os
import sys

PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "klawdy")


def keys():
    found = {}
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".py") or fn == "strings_en.py":
            continue
        tree = ast.parse(open(os.path.join(PKG, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, fn)
    sys.path.insert(0, os.path.join(PKG, ".."))
    from klawdy import themes  # noqa: E402
    for row in themes.COLOR_THEMES + themes.COSTUMES:
        found.setdefault(row[1], "themes.py")
    for name in ("Suas skills (claude.ai)", "Do Claude Code", "Pessoais (~/.claude/skills)"):
        found.setdefault(name, "ui_mascot.py")
    return found


if __name__ == "__main__":
    for k, fn in keys().items():
        print(f"{fn}\t{k!r}")
