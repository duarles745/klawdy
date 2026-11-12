#!/usr/bin/env bash
# Start Klawdy (once). XWayland allows "always on top" and free positioning on GNOME/Wayland.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pgrep -f "python3 -m klawdy$" >/dev/null && exit 0
export PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}"
GDK_BACKEND=x11 exec python3 -m klawdy "$@"
