#!/usr/bin/env bash
# Remove Klawdy (and leftovers of the pre-2.0 "claude-mascot") from this machine.
# Usage: bash uninstall.sh [--keep-voice]   (--keep-voice keeps the ~1 GB of voice models)
set -uo pipefail
DEST="${KLAWDY_HOME:-$HOME/.local/share/klawdy}"
KEEP_VOICE=0
case "${1:-}" in --keep-voice|--manter-voz) KEEP_VOICE=1 ;; esac
PT=0
case "${LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in pt*) PT=1 ;; esac
t() { if [ "$PT" = 1 ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi; }

ps -eo pid=,args= | awk '/python3? -m klawdy($| )|[c]laude-mascot\/(mascot|voice)\.py|-m klawdy\.voice/ {print $1}' |
  while read -r pid; do kill "$pid" 2>/dev/null; done
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
rm -f "$AUTOSTART/klawdy.desktop" "$AUTOSTART/klawdy-terminal.desktop" \
      "$AUTOSTART/claude-mascot.desktop" "$AUTOSTART/claude-terminal.desktop"

if command -v gsettings >/dev/null 2>&1; then
  BASE=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings
  cur="$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null)"
  if [ -n "$cur" ]; then
    new="$(python3 -c "import ast,sys; l=ast.literal_eval(sys.argv[1].replace('@as ','') or '[]'); print(str([x for x in l if x not in sys.argv[2:]]))" \
           "$cur" "$BASE/klawdy/" "$BASE/claude-mascot/")"
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$new"
    for p in klawdy claude-mascot; do
      gsettings reset-recursively "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$BASE/$p/" 2>/dev/null
    done
  fi
  gnome-extensions disable klawdy@local 2>/dev/null
  gnome-extensions disable claude-mascot@local 2>/dev/null
fi
rm -rf "$HOME/.local/share/gnome-shell/extensions/klawdy@local" "$HOME/.local/share/gnome-shell/extensions/claude-mascot@local"

if [ "$KEEP_VOICE" = 1 ] && [ -d "$DEST" ]; then
  find "$DEST" -mindepth 1 -maxdepth 1 ! -name venv ! -name models -exec rm -rf {} +
  t "Modelos de voz mantidos em $DEST/{venv,models}." "Voice models kept in $DEST/{venv,models}."
else
  rm -rf "$DEST"
fi
rm -rf "$HOME/.local/share/claude-mascot" \
       "${XDG_CONFIG_HOME:-$HOME/.config}/klawdy" "$HOME/.config/claude-mascot" \
       "${XDG_CACHE_HOME:-$HOME/.cache}/klawdy" "$HOME/.cache/claude-mascot" \
       "${XDG_RUNTIME_DIR:-/tmp}/klawdy" "${XDG_RUNTIME_DIR:-/tmp}/claude-mascot"

SETTINGS="$HOME/.claude/settings.json"
if [ -f "$SETTINGS" ] && command -v jq >/dev/null; then
  tmp="$(mktemp)"
  jq 'if .hooks then .hooks |= (map_values(map(.hooks |= map(select((.command // "") | test("(claude-mascot|klawdy)/hook\\.sh") | not)))
                                     | map(select((.hooks | length) > 0))) | with_entries(select((.value | length) > 0)))
      | if (.hooks | length) == 0 then del(.hooks) else . end else . end' "$SETTINGS" >"$tmp" && mv "$tmp" "$SETTINGS"
fi

t "Klawdy removido. Se instalou como plugin, rode no Claude Code:  /plugin uninstall klawdy@klawdy" \
  "Klawdy removed. If you installed it as a plugin, run in Claude Code:  /plugin uninstall klawdy@klawdy"
t "(CLAUDE_CODE_DISABLE_TERMINAL_TITLE em ~/.claude/settings.json pode ser apagado se quiser.)" \
  "(You may delete CLAUDE_CODE_DISABLE_TERMINAL_TITLE from ~/.claude/settings.json if you like.)"
