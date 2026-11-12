---
description: Start (or restart) Klawdy, the desktop companion
allowed-tools: Bash
---

Start Klawdy detached from this terminal:

```
setsid -f "$HOME/.local/share/klawdy/klawdy.sh" >/dev/null 2>&1 < /dev/null
```

If the file does not exist, tell the user to run `/klawdy-setup` first. Answer in the user's language.
