#!/usr/bin/env bash
# Claude Code hook -> writes the session state for Klawdy to read.
# Usage: hook.sh <working|attention|done|idle|end>   (event JSON on stdin)
# Must never fail or block Claude.
state="${1:-idle}"
dir="${XDG_RUNTIME_DIR:-/tmp}/klawdy"
mkdir -p "$dir" 2>/dev/null || exit 0
input="$(cat 2>/dev/null)"
sid="$(jq -r '.session_id // "default"' <<<"$input" 2>/dev/null)"
sid="${sid//[^A-Za-z0-9_-]/}"          # used in a file name: keep it boring
[ -z "$sid" ] && sid="default"
event="$(jq -r '.hook_event_name // ""' <<<"$input" 2>/dev/null)"

if [ "$state" = "end" ]; then
  rm -f "$dir/$sid.json"
  exit 0
fi

# Unique tag for this session, put in the terminal window title (the GNOME extension finds it)
tag="[klawdy-${sid:0:6}]"
cwd="$(jq -r '.cwd // ""' <<<"$input" 2>/dev/null)"
proj="$(basename "${cwd:-$HOME}")"

# Find Claude's terminal (tty) walking up the process tree
tty=""
pid=$$
for _ in 1 2 3 4 5 6; do
  t="$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')"
  if [ -n "$t" ] && [ "$t" != "?" ]; then tty="/dev/$t"; break; fi
  pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
  if [ -z "$pid" ] || [ "$pid" -le 1 ]; then break; fi
done

# Session name (so every session isn't just the folder name):
#   1) name given in Klawdy's menu  2) /rename or Claude's automatic title  3) start of the first prompt
title="$(jq -r '.title // empty' "$dir/$sid.json" 2>/dev/null)"
case "$event" in SessionStart|UserPromptSubmit|Stop)
  names="${XDG_CONFIG_HOME:-$HOME/.config}/klawdy/names.json"
  custom="$(jq -r --arg s "$sid" '.[$s] // empty' "$names" 2>/dev/null)"
  tp="$(jq -r '.transcript_path // ""' <<<"$input" 2>/dev/null)"
  auto=""
  if [ -z "$custom" ] && [ -f "$tp" ]; then
    auto="$(tac "$tp" 2>/dev/null | grep -m1 -E '"type":"(custom-title|ai-title)"' \
            | jq -r '.customTitle // .aiTitle // empty' 2>/dev/null)"
  fi
  if [ -n "$custom" ]; then title="$custom"
  elif [ -n "$auto" ]; then title="$auto"
  elif [ -z "$title" ]; then
    title="$(jq -r '.prompt // empty' <<<"$input" 2>/dev/null | tr -s '\n\t' '  ' | cut -c1-40 | sed 's/[[:space:]]*$//')"
  fi
  ;;
esac
label="$proj"
if [ -n "$title" ]; then
  if [ "${cwd:-$HOME}" = "$HOME" ]; then label="$title"; else label="$proj · $title"; fi
fi

# Set the title at start, on each prompt and when done (not on every tool call)
if [ -n "$tty" ] && [ -w "$tty" ]; then
  case "$event" in SessionStart|UserPromptSubmit|Stop)
    printf '\033]0;Claude · %s %s\007' "$label" "$tag" >"$tty" 2>/dev/null ;;
  esac
fi

# Skill in use (Klawdy wears the viking helmet / sword / shield while it runs)
skill="$(jq -r '.skill // empty' "$dir/$sid.json" 2>/dev/null)"
case "$event" in
  SessionStart) skill="" ;;
  UserPromptSubmit)
    skill=""
    # "/skill-name ..." typed by the user (ignores Claude Code built-in commands)
    cmd="$(jq -r '.prompt // ""' <<<"$input" 2>/dev/null | sed -n '1s#^/\([A-Za-z0-9:_-]\+\).*#\1#p')"
    case "$cmd" in
      ""|clear|compact|help|mcp|config|model|resume|rename|exit|quit|cost|status|doctor|login|logout|\
      permissions|hooks|agents|plugin|plugins|chrome|context|export|vim|theme|ide|add-dir|memory|\
      fast|usage|bug|feedback|tasks|todos|statusline|terminal-setup|upgrade|release-notes|rewind|\
      privacy-settings|output-style|sandbox|keybindings|artifacts|effort) ;;
      *) skill="$cmd" ;;
    esac ;;
  PreToolUse)
    if [ "$(jq -r '.tool_name // ""' <<<"$input" 2>/dev/null)" = "Skill" ]; then
      s="$(jq -r '.tool_input.skill // .tool_input.command // .tool_input.name // empty' <<<"$input" 2>/dev/null)"
      [ -n "$s" ] && skill="$s"
    fi ;;
esac

tmp="$dir/.$sid.$$"
jq -c --arg s "$state" --argjson t "$(date +%s)" --arg tag "$tag" --arg tty "$tty" --arg title "$title" \
  --arg skill "$skill" \
  '{state:$s, time:$t, cwd:(.cwd // ""), tool:(.tool_name // ""),
    message:(.message // ""), ntype:(.notification_type // ""), tag:$tag, tty:$tty, title:$title,
    skill:$skill}' \
  <<<"$input" >"$tmp" 2>/dev/null && mv -f "$tmp" "$dir/$sid.json"
rm -f "$tmp" 2>/dev/null
exit 0
