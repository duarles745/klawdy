#!/usr/bin/env bash
# Install, check and uninstall Klawdy on a fresh Ubuntu (run as root inside a container).
#   docker run --rm -v "$PWD":/src:ro ubuntu:24.04 bash /src/tests/clean_install.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive HOME=/root LANG=C.UTF-8
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
apt-get update -qq >/dev/null && apt-get install -y -qq ca-certificates >/dev/null
# a fake `claude` is enough for the installer and the diagnostics
# shellcheck disable=SC2016  # $1 belongs to the generated script
printf '#!/bin/sh\ncase "$1" in --version) echo "2.1.322 (Claude Code)";; mcp) echo "No MCP servers configured.";; esac\n' \
  >/usr/local/bin/claude
chmod +x /usr/local/bin/claude
rm -rf /work && cp -r "$SRC" /work && cd /work

bash install.sh --manual-hooks --no-desktop
APP="$HOME/.local/share/klawdy"
test -f "$APP/klawdy/__init__.py"
test "$(find "$APP/sounds" -name '*.wav' | wc -l)" -ge 5
test "$(jq '.hooks.Stop | length' ~/.claude/settings.json)" = 1
PYTHONPATH="$APP" python3 -m klawdy --version
PYTHONPATH="$APP" python3 -m klawdy --diagnose
echo '{"session_id":"abc","hook_event_name":"UserPromptSubmit","prompt":"/debug x"}' |
  XDG_RUNTIME_DIR=/tmp "$APP/hook.sh" working
test "$(jq -r .skill /tmp/klawdy/abc.json)" = debug

bash install.sh --manual-hooks --no-desktop >/dev/null      # idempotent
test "$(jq '.hooks.Stop | length' ~/.claude/settings.json)" = 1

python3 -m unittest discover -s tests -t .

bash uninstall.sh
test ! -e "$APP"
test "$(jq '.hooks' ~/.claude/settings.json)" = null
echo "clean install: OK"
