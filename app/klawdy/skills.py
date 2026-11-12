"""Installed skills and the viking gear Klawdy wears while one is running."""
import re
import time

from . import compat, config
from .i18n import _

# helmet: any skill · sword: skills that make/fix things · shield: skills that protect/check
SWORD_RE = re.compile(r"debug|code|run\b|build|creat|generat|implement|fix|simplif|engineer|figma|"
                      r"n8n|mcp|game|deploy|workflow|automat|plugin|init|loop|schedule|api|design|"
                      r"architect|system|refactor|tech-debt|docx|xlsx|pptx|pdf", re.I)
SHIELD_RE = re.compile(r"secur|review|complian|risk|incident|audit|access|test|attack|checklist|"
                       r"vendor|privacy|runbook|change-request|escalation", re.I)


def skill_gear(skill, custom=None):
    """Set of pieces for a skill. Customisable in config.json:
    "skill_gear": {"skill-name": ["sword", "shield"]}  (the helmet is always on)."""
    if not skill:
        return set()
    custom = config.setting("skill_gear") if custom is None else custom
    for key in (skill, skill.split(":")[-1]):
        if isinstance(custom, dict) and key in custom:
            return set(custom[key]) | {"helmet"}
    gear = {"helmet"}
    if SWORD_RE.search(skill):
        gear.add("sword")
    if SHIELD_RE.search(skill):
        gear.add("shield")
    if gear == {"helmet"}:
        gear.add("sword")          # research, documents, etc.: helmet + sword
    return gear


def builtin_skills():
    """Skills bundled with Claude Code (not on disk)."""
    return [
        ("code-review", _("Revisa as mudanças atuais procurando bugs")),
        ("simplify", _("Simplifica e limpa o código alterado")),
        ("security-review", _("Revisão de segurança das mudanças da branch")),
        ("init", _("Cria o CLAUDE.md com a documentação do projeto")),
        ("run", _("Roda o app do projeto para ver a mudança funcionando")),
        ("dataviz", _("Gráficos, dashboards e visualizações de dados")),
        ("claude-api", _("Referência da API do Claude / SDK da Anthropic")),
        ("claude-in-chrome", _("Automatiza o Chrome: clicar, preencher, capturar")),
        ("loop", _("Repete um prompt em intervalos")),
        ("schedule", _("Agenda tarefas recorrentes na nuvem")),
        ("update-config", _("Configura o settings.json do Claude Code")),
        ("fewer-permission-prompts", _("Libera comandos comuns para pedir menos permissão")),
    ]


_cache = [0.0, []]


def list_skills():
    """[{name, group, desc, hint}] of every available skill (60 s cache)."""
    if time.time() - _cache[0] < 60:
        return _cache[1]
    skills = []
    for name, group, md in compat.skill_files():
        fm = compat.read_frontmatter(md)
        skills.append({"name": name, "group": group,
                       "desc": " ".join((fm.get("description") or "").split()),
                       "hint": fm.get("argument-hint", "")})
    for name, desc in builtin_skills():
        skills.append({"name": name, "group": "claude-code", "desc": desc, "hint": ""})
    _cache[:] = [time.time(), skills]
    return skills


def find_skill(name):
    return next((s for s in list_skills() if s["name"] == name), None)


def remember_skill(name):
    st = config.load_settings()
    rec = [name] + [x for x in st.get("recent_skills", []) if x != name]
    st["recent_skills"] = rec[:6]
    config.save_settings(st)
