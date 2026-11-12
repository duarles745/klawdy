#!/usr/bin/env bash
# PermissionRequest hook for Klawdy's background runs (`claude -p`, added with --settings by
# actions.run_main). Leaves the request in $XDG_RUNTIME_DIR/klawdy/perm/<id>.json, Klawdy shows a
# popup with Aprovar / Recusar and writes <id>.answer ("allow" | "deny").
# No mascot running, or no answer in time -> no output: Claude Code decides as usual (in -p: denied).
dir="${XDG_RUNTIME_DIR:-/tmp}/klawdy"
pdir="$dir/perm"
pid="$(cat "$dir/mascot.pid" 2>/dev/null)"
pid="${pid//[^0-9]/}"
alive() { [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }
alive || exit 0
mkdir -p "$pdir" 2>/dev/null || exit 0
input="$(cat 2>/dev/null)"

id="$(date +%s%N)-$$"
req="$pdir/$id.json"
ans="$pdir/$id.answer"
trap 'rm -f "$req" "$req.tmp" "$ans"' EXIT
if ! jq -c --arg id "$id" --argjson t "$(date +%s)" \
  '{id:$id, time:$t, sid:(.session_id // ""), cwd:(.cwd // ""), tool:(.tool_name // ""),
    input:(.tool_input // {})}' <<<"$input" >"$req.tmp" 2>/dev/null; then
  exit 0
fi
mv -f "$req.tmp" "$req" || exit 0

decide() {
  jq -cn --arg b "$1" --arg m "$2" \
    '{hookSpecificOutput:{hookEventName:"PermissionRequest",
      decision:({behavior:$b} + (if $m == "" then {} else {message:$m} end))}}'
}

limit=$(( $(date +%s) + ${KLAWDY_PERM_WAIT:-280} ))   # the hook timeout is 300 s
while [ "$(date +%s)" -lt "$limit" ] && alive; do
  if [ -f "$ans" ]; then
    case "$(head -c 16 "$ans" 2>/dev/null)" in
      allow) decide allow "" ;;
      deny)  decide deny "The user denied this in Klawdy's permission popup." ;;
    esac
    exit 0
  fi
  sleep 0.3
done
exit 0
