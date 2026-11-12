#!/usr/bin/env bash
# Klawdy installer (Linux). Safe to run again at any time to update.
#
# Usage: bash install.sh [options]
#   --voice              also install offline voice commands (~1 GB of models)
#   --manual-hooks       write the Claude Code hooks into ~/.claude/settings.json
#                        (only if you don't install Klawdy as a Claude Code plugin)
#   --terminal-at-login  also open a terminal with Claude when you log in
#   --no-desktop         skip autostart, keyboard shortcut and GNOME extension (CI/servers)
#   -h, --help
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${KLAWDY_HOME:-$HOME/.local/share/klawdy}"
OLD_DEST="$HOME/.local/share/claude-mascot"            # pre-2.0 name
EXT_UUID="klawdy@local"
OLD_EXT_UUID="claude-mascot@local"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
SETTINGS="$HOME/.claude/settings.json"
KB_PATH=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/klawdy/
OLD_KB_PATH=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/claude-mascot/

VOICE=0
MANUAL_HOOKS=0
TERM_LOGIN=0
DESKTOP=1
for a in "$@"; do
  case "$a" in
    --voice) VOICE=1 ;;
    --no-voice|--sem-voz) VOICE=0 ;;
    --manual-hooks) MANUAL_HOOKS=1 ;;
    --terminal-at-login|--terminal-no-login) TERM_LOGIN=1 ;;
    --no-desktop) DESKTOP=0 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a (see --help)"; exit 1 ;;
  esac
done

PT=0
case "${LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in pt*) PT=1 ;; esac
t() { if [ "$PT" = 1 ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
step() { printf '\n\033[1;38;5;173m==> %s\033[0m\n' "$(t "$1" "$2")"; }
info() { printf '    %s\n' "$(t "$1" "$2")"; }
warn() { printf '\033[1;33m    ! %s\033[0m\n' "$(t "$1" "$2")"; }

as_root() {
  if [ "$(id -u)" = 0 ]; then "$@"
  elif sudo -n true 2>/dev/null; then sudo -n "$@"
  elif [ -t 0 ]; then sudo "$@"
  else return 99
  fi
}

# ---------------------------------------------------------------- checks
step "Verificando o sistema" "Checking the system"
CLAUDE="$(command -v claude || true)"
[ -z "$CLAUDE" ] && [ -x "$HOME/.local/bin/claude" ] && CLAUDE="$HOME/.local/bin/claude"
if [ -z "$CLAUDE" ]; then
  warn "Claude Code não encontrado. Instale antes: https://docs.claude.com/claude-code" \
       "Claude Code not found. Install it first: https://docs.claude.com/claude-code"
  exit 1
fi
info "Claude Code: $CLAUDE" "Claude Code: $CLAUDE"
DE="${XDG_CURRENT_DESKTOP:-}"
case "$DE" in
  *GNOME*) GNOME=1; info "Desktop: GNOME (${XDG_SESSION_TYPE:-?})" "Desktop: GNOME (${XDG_SESSION_TYPE:-?})" ;;
  *) GNOME=0
     info "Desktop: ${DE:-?}. Klawdy funciona; ir até o terminal da sessão e o atalho automático são só do GNOME." \
          "Desktop: ${DE:-?}. Klawdy works; jumping to a session's terminal and the automatic shortcut are GNOME-only." ;;
esac

# ---------------------------------------------------------------- dependencies
step "Dependências do sistema" "System dependencies"
have_gtk() {
  python3 - <<'PY' 2>/dev/null
import gi
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
import cairo  # noqa: F401
PY
}
NEED=0
have_gtk || NEED=1
command -v jq >/dev/null || NEED=1
command -v notify-send >/dev/null || NEED=1
if [ "$VOICE" = 1 ]; then
  python3 -c 'import venv' 2>/dev/null || NEED=1
  python3 -c 'import ensurepip' 2>/dev/null || NEED=1
  for c in pw-record curl unzip; do command -v "$c" >/dev/null || NEED=1; done
fi
if [ "$NEED" = 0 ]; then
  info "Tudo já instalado." "Everything is already installed."
else
  if command -v apt-get >/dev/null; then
    PKGS=(python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 jq libnotify-bin)
    [ "$VOICE" = 1 ] && PKGS+=(python3-venv pipewire-bin curl unzip speech-dispatcher)
    CMD=(apt-get install -y "${PKGS[@]}")
  elif command -v dnf >/dev/null; then
    PKGS=(python3 python3-gobject python3-cairo gtk3 jq libnotify)
    [ "$VOICE" = 1 ] && PKGS+=(pipewire-utils curl unzip speech-dispatcher-utils)
    CMD=(dnf install -y "${PKGS[@]}")
  elif command -v pacman >/dev/null; then
    PKGS=(python python-gobject python-cairo gtk3 jq libnotify)
    [ "$VOICE" = 1 ] && PKGS+=(pipewire curl unzip speech-dispatcher)
    CMD=(pacman -S --needed --noconfirm "${PKGS[@]}")
  elif command -v zypper >/dev/null; then
    PKGS=(python3 python3-gobject python3-gobject-cairo typelib-1_0-Gtk-3_0 jq libnotify-tools)
    [ "$VOICE" = 1 ] && PKGS+=(pipewire-tools curl unzip speech-dispatcher)
    CMD=(zypper --non-interactive install "${PKGS[@]}")
  else
    warn "Não reconheci o gerenciador de pacotes. Instale: PyGObject (GTK 3 + cairo), jq e notify-send." \
         "Unknown package manager. Please install: PyGObject (GTK 3 + cairo), jq and notify-send."
    exit 2
  fi
  info "Instalando: ${PKGS[*]}" "Installing: ${PKGS[*]}"
  if command -v apt-get >/dev/null; then as_root apt-get update -qq || true; fi
  if ! as_root "${CMD[@]}"; then
    warn "Preciso da sua senha para instalar pacotes. Rode num terminal:" \
         "I need your password to install packages. Run in a terminal:"
    echo "      sudo ${CMD[*]}"
    warn "e depois rode este instalador de novo." "and then run this installer again."
    exit 2
  fi
fi

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
  warn "É preciso Python 3.10 ou mais novo." "Python 3.10 or newer is required."
  exit 1
fi

# ---------------------------------------------------------------- app files
step "Copiando o Klawdy para $DEST" "Copying Klawdy to $DEST"
stop_running() {
  ps -eo pid=,args= | awk '/python3? -m klawdy($| )|[c]laude-mascot\/(mascot|voice)\.py|-m klawdy\.voice/ && !/--(prompt|run|send)/ {print $1}' |
    while read -r pid; do
      if [ "$pid" != "$$" ]; then kill "$pid" 2>/dev/null || true; fi
    done
}
stop_running
mkdir -p "$DEST"
if [ -d "$OLD_DEST" ]; then                      # migrate from "claude-mascot" (keeps the 1 GB of voice models)
  for d in venv models; do
    if [ -d "$OLD_DEST/$d" ] && [ ! -e "$DEST/$d" ]; then mv "$OLD_DEST/$d" "$DEST/$d"; fi
  done
  rm -rf "$OLD_DEST"
  info "Instalação antiga (claude-mascot) migrada." "Old installation (claude-mascot) migrated."
fi
rm -rf "$DEST/klawdy"
cp -r "$SRC/app/klawdy" "$DEST/klawdy"
find "$DEST/klawdy" -name __pycache__ -prune -exec rm -rf {} +
for f in hook.sh klawdy.sh prompt.sh make_sounds.py requirements-voice.txt; do
  install -m 0755 "$SRC/app/$f" "$DEST/$f"
done
python3 "$DEST/make_sounds.py" >/dev/null && info "Efeitos sonoros gerados." "Sound effects generated."
PYTHONPATH="$DEST" python3 -c 'from klawdy import config; config.migrate()' || true

# ---------------------------------------------------------------- Claude Code
step "Configurando o Claude Code" "Configuring Claude Code"
mkdir -p "$HOME/.claude"
[ -f "$SETTINGS" ] || echo '{}' >"$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak-klawdy-$(date +%Y%m%d%H%M%S)"
tmp="$(mktemp)"
# - fixed terminal title (Klawdy finds the session's window by the tag hook.sh puts there)
# - remove Klawdy hooks written by hand before; add them again only with --manual-hooks
jq --arg hook "$DEST/hook.sh" --argjson manual "$MANUAL_HOOKS" '
def clean: map(.hooks |= map(select((.command // "") | test("(claude-mascot|klawdy)/hook\\.sh") | not)))
           | map(select((.hooks | length) > 0));
def h(s): [{hooks: [{type: "command", command: ("\"" + $hook + "\" " + s), timeout: 5}]}];
.env = ((.env // {}) + {CLAUDE_CODE_DISABLE_TERMINAL_TITLE: "1"})
| .hooks = ((.hooks // {}) | map_values(clean) | with_entries(select((.value | length) > 0)))
| if $manual == 1 then
    .hooks.SessionStart += h("idle") | .hooks.UserPromptSubmit += h("working")
    | .hooks.PreToolUse += h("working") | .hooks.PostToolUse += h("working")
    | .hooks.Notification += h("attention") | .hooks.Stop += h("done") | .hooks.SessionEnd += h("end")
  else . end
| if (.hooks | length) == 0 then del(.hooks) else . end
' "$SETTINGS" >"$tmp" && mv "$tmp" "$SETTINGS"
info "settings.json atualizado (backup ao lado)." "settings.json updated (backup next to it)."
PLUGINS="$HOME/.claude/plugins/installed_plugins.json"
if [ "$MANUAL_HOOKS" = 1 ]; then
  info "Hooks gravados no settings.json." "Hooks written to settings.json."
elif [ -z "${CLAUDE_PLUGIN_ROOT:-}" ] && ! grep -qs '"klawdy@' "$PLUGINS"; then
  warn "Os hooks vêm pelo plugin. No Claude Code rode:" "Hooks come with the plugin. In Claude Code run:"
  echo "      /plugin marketplace add duarles745/klawdy"
  echo "      /plugin install klawdy@klawdy"
  warn "(ou rode este instalador com --manual-hooks)" "(or run this installer with --manual-hooks)"
fi
if grep -qs '"mascote-desktop@' "$PLUGINS"; then
  warn "O plugin antigo continua instalado. No Claude Code rode: /plugin uninstall mascote-desktop@mascote" \
       "The old plugin is still installed. In Claude Code run: /plugin uninstall mascote-desktop@mascote"
fi

# ---------------------------------------------------------------- desktop integration
EXT_RELOGIN=0
if [ "$DESKTOP" = 1 ]; then
  step "Abrir automaticamente ao fazer login" "Start automatically at login"
  mkdir -p "$AUTOSTART"
  [ -f "$AUTOSTART/claude-terminal.desktop" ] && TERM_LOGIN=1          # keep the old choice
  rm -f "$AUTOSTART/claude-mascot.desktop" "$AUTOSTART/claude-terminal.desktop"
  cat >"$AUTOSTART/klawdy.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Klawdy
Comment=Desktop companion that shows what Claude Code is doing
Exec=$DEST/klawdy.sh
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
EOF
  info "Klawdy no login: ok" "Klawdy at login: ok"
  if [ "$TERM_LOGIN" = 1 ]; then
    cat >"$AUTOSTART/klawdy-terminal.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Code terminal (Klawdy)
Exec=env PYTHONPATH=$DEST python3 -c "from klawdy import actions; actions.launch_claude()"
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF
    info "Terminal com Claude no login: ok" "Terminal with Claude at login: ok"
  fi

  list_edit() {   # list_edit <gsettings-value> <add> <remove>  -> prints the new list
    python3 - "$1" "$2" "$3" <<'PY'
import ast, sys
cur = sys.argv[1].replace("@as ", "").strip()
items = ast.literal_eval(cur) if cur else []
items = [x for x in items if x != sys.argv[3]]
if sys.argv[2] and sys.argv[2] not in items:
    items.append(sys.argv[2])
print(str(items))
PY
  }
  if [ "$GNOME" = 1 ] && command -v gsettings >/dev/null &&
     gsettings writable org.gnome.settings-daemon.plugins.media-keys custom-keybindings >/dev/null 2>&1; then
    step "Atalho Ctrl+. (perguntar ao Claude)" "Ctrl+. shortcut (ask Claude)"
    cur="$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings)"
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$(list_edit "$cur" "$KB_PATH" "$OLD_KB_PATH")"
    gsettings reset-recursively "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$OLD_KB_PATH" 2>/dev/null || true
    S="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KB_PATH"
    gsettings set "$S" name "Klawdy: ask Claude"
    gsettings set "$S" command "$DEST/prompt.sh"
    gsettings set "$S" binding "<Control>period"
    info "Ctrl+. configurado." "Ctrl+. configured."

    step "Extensão do GNOME (clicar no Klawdy leva ao terminal da sessão)" \
         "GNOME extension (clicking Klawdy jumps to the session's terminal)"
    mkdir -p "$EXT_DIR/$EXT_UUID"
    cp "$SRC/gnome-extension/$EXT_UUID/"* "$EXT_DIR/$EXT_UUID/"
    # the old extension keeps running until the next login (Klawdy talks to it meanwhile); its files can go
    rm -rf "${EXT_DIR:?}/$OLD_EXT_UUID"
    if gnome-extensions enable "$EXT_UUID" 2>/dev/null; then
      info "Extensão ativada." "Extension enabled."
    else
      cur="$(gsettings get org.gnome.shell enabled-extensions)"
      gsettings set org.gnome.shell enabled-extensions "$(list_edit "$cur" "$EXT_UUID" "")"
      info "Extensão instalada; ela liga no próximo login." "Extension installed; it turns on at the next login."
      EXT_RELOGIN=1
    fi
  else
    info "Atalho de teclado: crie um atalho no seu desktop que rode  $DEST/prompt.sh" \
         "Keyboard shortcut: create a shortcut in your desktop settings that runs  $DEST/prompt.sh"
  fi
fi

# ---------------------------------------------------------------- voice (opt-in)
if [ "$VOICE" = 1 ]; then
  step "Comando de voz (offline, ~1 GB — pode demorar)" "Voice commands (offline, ~1 GB — may take a while)"
  [ -x "$DEST/venv/bin/python" ] || python3 -m venv "$DEST/venv"
  "$DEST/venv/bin/python" -m pip install --quiet --upgrade pip
  "$DEST/venv/bin/python" -m pip install --quiet -r "$DEST/requirements-voice.txt"
  info "Bibliotecas de voz instaladas." "Voice libraries installed."
  VLANG="$(PYTHONPATH="$DEST" python3 -c 'from klawdy.i18n import lang; print(lang())')"
  if [ "$VLANG" = pt ]; then MODEL=vosk-model-small-pt-0.3; else MODEL=vosk-model-small-en-us-0.15; fi
  mkdir -p "$DEST/models"
  if [ ! -d "$DEST/models/$MODEL" ]; then
    info "Baixando o modelo Vosk ($MODEL)…" "Downloading the Vosk model ($MODEL)…"
    z="$(mktemp --suffix=.zip)"
    curl -fL --progress-bar -o "$z" "https://alphacephei.com/vosk/models/$MODEL.zip"
    unzip -q -o "$z" -d "$DEST/models"
    rm -f "$z"
  fi
  info "Baixando/conferindo o modelo Whisper small…" "Downloading/checking the Whisper small model…"
  "$DEST/venv/bin/python" -c "
from faster_whisper import WhisperModel
WhisperModel('small', device='cpu', compute_type='int8', download_root='$DEST/models/whisper')"
  PYTHONPATH="$DEST" python3 -c 'from klawdy import config; config.set_setting("voice", True)'
  info "Voz pronta (palavra de ativação ligada; desligue nas Configurações se preferir)." \
       "Voice ready (wake word on; turn it off in Settings if you prefer)."
elif [ -x "$DEST/venv/bin/python" ]; then
  info "Voz já instalada." "Voice already installed."
else
  info "Voz não instalada (rode com --voice para instalar)." "Voice not installed (run with --voice to install it)."
fi

# ---------------------------------------------------------------- start
if [ "$DESKTOP" = 1 ] && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
  step "Abrindo o Klawdy" "Starting Klawdy"
  setsid -f "$DEST/klawdy.sh" >/dev/null 2>&1 </dev/null || true
  sleep 2
  if pgrep -f "python3 -m klawdy$" >/dev/null; then
    info "O Klawdy está no canto inferior direito da tela." "Klawdy is in the bottom-right corner of the screen."
  else
    warn "O Klawdy não abriu. Teste num terminal: $DEST/klawdy.sh" "Klawdy did not start. Try in a terminal: $DEST/klawdy.sh"
  fi
fi

echo
t "Pronto! Próximos passos:" "Done! Next steps:"; echo
t "  1. Abra uma NOVA sessão do Claude Code (as já abertas não recebem os hooks novos)." \
  "  1. Open a NEW Claude Code session (sessions already open don't get the new hooks)."; echo
if [ "$EXT_RELOGIN" = 1 ]; then
  t "  2. Faça logout e login para a extensão do GNOME ligar." "  2. Log out and back in to turn the GNOME extension on."; echo
fi
echo
t "Como usar: arraste = mover · clique = ir para o terminal · duplo clique = novo Claude" \
  "How to use: drag = move · click = go to the terminal · double-click = new Claude"; echo
t "           rodinha = tamanho · botão direito = menu (Configurações, skills, MCPs) · Ctrl+. = perguntar" \
  "            wheel = size · right-click = menu (Settings, skills, MCP servers) · Ctrl+. = ask"; echo
