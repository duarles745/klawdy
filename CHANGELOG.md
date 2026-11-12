# Changelog

All notable changes to Klawdy. Versions follow [Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-11-12

The project becomes **Klawdy**, an unofficial community companion for Claude Code, ready to be shared.

### Changed
- New name and character: Klawdy has **six legs and two antennae** (antennae wobble while working,
  glow when it needs you and droop when it sleeps). The mascot no longer uses Anthropic's Clawd.
- Repository, plugin and folders renamed: `duarles745/klawdy`, plugin `klawdy@klawdy`,
  `~/.local/share/klawdy`, `~/.config/klawdy`, `~/.cache/klawdy`, GNOME extension `klawdy@local`.
  Settings, session names and position are migrated automatically from `claude-mascot`; the voice models
  are moved instead of downloaded again.
- Code split into the `klawdy` package (config, i18n, compat, sessions, skills, actions, painter, UI).
- The prompt box, menus and installer speak **English and Portuguese** (system language or Settings).
- Voice: the wake word is configurable (`Klawdy` by default in English, `Claudinho`/`Klawdy` in
  Portuguese) and the English Vosk model is used for English.

### Security
- **Claude in Chrome is off by default** for background and voice requests (they run without
  per-step approval; web pages can carry prompt injection). Turning it on shows a warning.
- **Voice commands are opt-in** at install time (`--voice`), and **installing programs by voice is off**
  by default (separate setting with a warning).
- `~/.claude.json` edits (MCP on/off) take a lock, re-read just before writing, replace atomically,
  keep a daily backup and verify the change.
- Session ids are sanitised before being used as file names in the hook.

### Added
- Settings window (General, Voice, Security, About) instead of editing `config.json`.
- `compat.py`: every use of undocumented Claude Code details in one place, failing safely, with a
  diagnostics report (Settings › About or `python3 -m klawdy --diagnose`). Tested with Claude Code 2.1.322.
- "Log in to…" menu for MCP servers that need authentication (`claude mcp login`).
- Installer: apt, dnf, pacman and zypper; `--manual-hooks` for use without the plugin system;
  `--no-desktop` for servers/CI; works on non-GNOME desktops with reduced features.
- Unit tests (stdlib `unittest`), a clean-install test in a fresh Ubuntu container and GitHub Actions CI
  (ruff, ShellCheck, tests, clean install).
- MIT licence, this changelog, English and Portuguese READMEs with an animated demo.

### Performance
- Adaptive frame rate: 30 fps when something happens, 10 fps idle, 5 fps asleep (was always 30).
- Voice: an energy gate feeds the recogniser only around sound, and Whisper is loaded on demand and
  unloaded after 10 idle minutes.

### Fixed
- The voice state file was read as if it were a Claude session.
- Session titles taken from the first prompt had a trailing space.
- "▸" rendered as a box in bubbles.
- The speech bubble overlapped the antennae, helmet or sword while Klawdy hopped.

## [1.3.0] — 2026-11-11
### Added (by Alvaro)
- Colour themes (10, including an animated rainbow), character costumes and matching background scenery.

## [1.2.0] — 2026-11-11
### Added
- "Use a skill" menu listing every installed skill; choosing one opens the prompt box ready for it.

## [1.1.0] — 2026-11-11
### Added
- Named sessions, open any conversation's history in a terminal, expandable answer bubble that hides after
  30 s, draggable prompt box, MCP servers menu, Claude in Chrome for background requests.
- Viking mode: helmet, sword and shield while a skill is running.

## [1.0.0] — 2026-11-11
- First version: floating mascot driven by Claude Code hooks, Ctrl+. prompt box, GNOME extension to jump to a
  session's terminal, offline voice commands, installer and Claude Code plugin.

[2.0.0]: https://github.com/duarles745/klawdy/releases/tag/v2.0.0
