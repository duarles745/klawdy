#!/usr/bin/env bash
# Ctrl+. -> opens (or closes, if already open) Klawdy's prompt box
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if pkill -f "python3 -m klawdy --prompt"; then exit 0; fi
export PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}"
GDK_BACKEND=x11 exec python3 -m klawdy --prompt
