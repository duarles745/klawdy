---
description: Install/update Klawdy on the desktop (dependencies, autostart, Ctrl+. shortcut, GNOME extension; voice with --voice)
argument-hint: "[--voice] [--terminal-at-login]"
allowed-tools: Bash
---

Run the Klawdy installer bundled with this plugin and follow its output:

```
bash "${CLAUDE_PLUGIN_ROOT}/install.sh" $ARGUMENTS
```

- The installer may need `sudo` for system packages. If sudo asks for a password and there is no interactive
  terminal, ask the user to run it themselves by typing `! bash "${CLAUDE_PLUGIN_ROOT}/install.sh" $ARGUMENTS`.
- `--voice` downloads ~1 GB of offline speech models; warn that it can take a while.
- At the end, explain the next steps the installer printed (mainly: log out/in to enable the GNOME extension),
  in the user's language.
