"""Compatibility helpers for CoPaw/OpenClaw style SKILL.md workflows.

ResearchClaw historically loaded only Python-entry skills (``__init__.py`` or
``main.py``). CoPaw also supports doc-only skills where ``SKILL.md`` provides
operational guidance for existing tools. This module adds light-weight runtime
support for those guidance-style skills.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml


_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,63}")
_CJK_SEQ_RE = re.compile(r"[\u4e00-\u9fff]{2,64}")
_SLASH_CMD_RE = re.compile(r"/([a-zA-Z0-9][a-zA-Z0-9_-]{1,63})")
_TOKEN_SYNONYMS: dict[str, set[str]] = {
    "新闻": {"news", "latest", "headlines"},
    "科技": {"tech", "technology", "science"},
    "浏览器": {"browser"},
    "可见": {"visible", "headed"},
    "钉钉": {"dingtalk"},
    "频道": {"channel"},
    "定时": {"cron", "schedule"},
    "定时任务": {"cron", "schedule"},
    "邮件": {"email", "mail"},
}


def _norm(text: str) -> str:
    return _NON_WORD_RE.sub("-", text.lower()).strip("-")


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = {t for t in _TOKEN_RE.findall(lowered) if len(t) >= 3}
    for seq in _CJK_SEQ_RE.findall(text):
        seq = seq.strip()
        if len(seq) < 2:
            continue
        max_n = min(4, len(seq))
        for n in range(2, max_n + 1):
            for i in range(0, len(seq) - n + 1):
                tokens.add(seq[i : i + n])
    return tokens


def _expand_query_tokens(tokens: set[str]) -> set[str]:
    """Expand token set with lightweight bilingual synonyms."""
    expanded = set(tokens)
    for token in list(tokens):
        if token in _TOKEN_SYNONYMS:
            expanded |= _TOKEN_SYNONYMS[token]
    return expanded


@dataclass
class SkillDoc:
    """Parsed skill metadata used for prompt-time guidance injection."""

    name: str
    description: str
    content: str
    path: str
    executable: bool = False
    aliases: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    triggers: set[str] = field(default_factory=set)


def _normalize_trigger_values(value: object) -> set[str]:
    """Normalize trigger values from SKILL.md metadata."""
    items: list[str] = []
    if value is None:
        return set()
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        items.extend([p for p in parts if p])
    elif isinstance(value, list):
        for v in value:
            if isinstance(v, str) and v.strip():
                items.append(v.strip())
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str) and k.strip():
                items.append(k.strip())
            if isinstance(v, str) and v.strip():
                items.append(v.strip())
    return set(items)


def parse_skill_doc(skill_dir: Path, *, executable: bool) -> SkillDoc | None:
    """Parse ``SKILL.md`` in a skill directory."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None

    content = skill_md.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        return None

    name = skill_dir.name
    description = ""
    trigger_values: set[str] = set()

    lines = content.splitlines()
    # Frontmatter style:
    # ---
    # name: xxx
    # description: yyy
    # ---
    if lines and lines[0].strip() == "---":
        fm_lines: list[str] = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            fm_lines.append(line)
        try:
            loaded = yaml.safe_load("\n".join(fm_lines))
            if isinstance(loaded, dict):
                value = loaded.get("name")
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                value = loaded.get("description")
                if isinstance(value, str) and value.strip():
                    description = value.strip()
                trigger_values |= _normalize_trigger_values(loaded.get("triggers"))
                trigger_values |= _normalize_trigger_values(loaded.get("trigger"))
                trigger_values |= _normalize_trigger_values(loaded.get("keywords"))
                trigger_values |= _normalize_trigger_values(loaded.get("aliases"))
        except Exception:
            # Keep resilient parsing for partially malformed frontmatter.
            for raw_line in fm_lines:
                line = raw_line.strip()
                if not line or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip().strip('"').strip("'")
                if key == "name" and value:
                    name = value
                elif key == "description" and value:
                    description = value

    # Bullet style:
    # - name: xxx
    # - description: yyy
    if not description or not name:
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("- name:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    name = value
                continue
            if line.startswith("- description:"):
                value = line.split(":", 1)[1].strip().strip('"').strip("'")
                description = value
                continue
            if line.startswith("- triggers:"):
                trigger_values |= _normalize_trigger_values(
                    line.split(":", 1)[1].strip(),
                )
                continue
            if line.startswith("- keywords:"):
                trigger_values |= _normalize_trigger_values(
                    line.split(":", 1)[1].strip(),
                )
                continue
            if description:
                break

    aliases = {_norm(name), _norm(skill_dir.name)}
    aliases |= {_norm(t) for t in trigger_values if t}
    aliases |= {a.replace("-", "_") for a in aliases}
    aliases |= {a.replace("_", "-") for a in aliases}

    keywords = set(aliases)
    keywords |= _tokens(name)
    keywords |= _tokens(description)
    keywords |= _tokens(" ".join(trigger_values))
    # Include a capped portion of the body so Chinese and domain terms
    # in SKILL.md content can still trigger selection.
    keywords |= _tokens(content[:4000])

    return SkillDoc(
        name=name,
        description=description,
        content=content,
        path=str(skill_md),
        executable=executable,
        aliases=aliases,
        keywords=keywords,
        triggers={t for t in trigger_values if t.strip()},
    )


def _rank_skills(
    query: str,
    skills: Iterable[SkillDoc],
    *,
    max_count: int = 3,
) -> list[tuple[float, SkillDoc, set[str], str]]:
    """Rank relevant skills with score + matched keywords + mode."""
    all_skills = list(skills)
    if not query or not all_skills:
        return []

    q = query.lower()
    q_norm = _norm(q)
    q_tokens = _expand_query_tokens(_tokens(q))
    slash_cmds = {_norm(m.group(1)) for m in _SLASH_CMD_RE.finditer(query)}
    slash_cmds |= {c.replace("-", "_") for c in list(slash_cmds)}
    slash_cmds |= {c.replace("_", "-") for c in list(slash_cmds)}

    explicit: list[tuple[float, SkillDoc, set[str], str]] = []
    for skill in all_skills:
        if slash_cmds & skill.aliases:
            matched = slash_cmds & skill.aliases
            explicit.append((10_000.0, skill, set(matched), "slash"))
            continue

        if any(
            re.search(rf"(?<![a-z0-9_/-]){re.escape(alias)}(?![a-z0-9_/-])", q)
            for alias in skill.aliases
            if alias
        ):
            explicit.append((5_000.0, skill, set(), "alias"))
            continue

        if skill.name and _norm(skill.name) and _norm(skill.name) in q_norm:
            explicit.append((3_000.0, skill, set(), "name"))

    if explicit:
        seen: set[str] = set()
        ordered: list[tuple[float, SkillDoc, set[str], str]] = []
        for score, s, matched, mode in explicit:
            key = _norm(s.name)
            if key in seen:
                continue
            seen.add(key)
            ordered.append((score, s, matched, mode))
        return ordered[:max_count]

    doc_freq: dict[str, int] = {}
    for skill in all_skills:
        for kw in skill.keywords:
            doc_freq[kw] = doc_freq.get(kw, 0) + 1

    weighted: list[tuple[float, SkillDoc, set[str], str]] = []
    for skill in all_skills:
        matched = skill.keywords & q_tokens
        if not matched:
            continue
        weight = 0.0
        for token in matched:
            df = max(1, doc_freq.get(token, 1))
            weight += 1.0 / float(df)
        weighted.append((weight, skill, set(matched), "keywords"))

    weighted.sort(key=lambda x: x[0], reverse=True)
    if not weighted:
        return []

    # Keep only candidates close to the top score to avoid noisy generic hits.
    top = weighted[0][0]
    cutoff = max(1.0, top * 0.6)
    return [item for item in weighted if item[0] >= cutoff][:max_count]


def select_relevant_skills(
    query: str,
    skills: Iterable[SkillDoc],
    *,
    max_count: int = 3,
) -> list[SkillDoc]:
    """Select skills likely relevant to the current user query."""
    ranked = _rank_skills(query, skills, max_count=max_count)
    return [item[1] for item in ranked]


def explain_skill_selection(
    query: str,
    skills: Iterable[SkillDoc],
    *,
    max_count: int = 3,
) -> dict[str, object]:
    """Return debug details for skill-selection decisions."""
    ranked = _rank_skills(query, skills, max_count=max_count)
    return {
        "query": query,
        "selected": [item[1].name for item in ranked],
        "details": [
            {
                "name": skill.name,
                "score": round(float(score), 4),
                "mode": mode,
                "matched": sorted(list(matched))[:32],
            }
            for score, skill, matched, mode in ranked
        ],
    }


def build_skill_context_prompt(
    query: str,
    skills: Iterable[SkillDoc],
    *,
    selected_skills: Iterable[SkillDoc] | None = None,
    selection_debug: dict[str, object] | None = None,
    max_skill_chars: int = 10_000,
    max_total_chars: int = 24_000,
) -> str:
    """Build a system-message snippet describing available and selected skills."""
    all_skills = list(skills)
    if not all_skills:
        return ""

    selected = (
        list(selected_skills)
        if selected_skills is not None
        else select_relevant_skills(query, all_skills)
    )
    debug_info = (
        selection_debug
        if selection_debug is not None
        else explain_skill_selection(query, all_skills)
    )

    lines: list[str] = []
    lines.append("[Skill Compatibility]")
    lines.append(
        "These skills come from active SKILL.md files (CoPaw/OpenClaw style).",
    )
    lines.append(
        "Use them as operational playbooks; then call concrete tools to execute.",
    )
    lines.append("")
    lines.append("Available skills:")
    for skill in sorted(all_skills, key=lambda s: _norm(s.name)):
        mode = "executable-tools" if skill.executable else "guidance-only"
        desc = skill.description or "(no description)"
        lines.append(f"- {skill.name} [{mode}]: {desc}")

    if not selected:
        return "\n".join(lines)

    lines.append("")
    lines.append("Selected skills for current user message:")
    lines.extend(f"- {s.name}" for s in selected)
    debug_details = debug_info.get("details") if isinstance(debug_info, dict) else None
    if isinstance(debug_details, list) and debug_details:
        lines.append("")
        lines.append("Selection debug:")
        for detail in debug_details[: max(1, len(selected))]:
            if not isinstance(detail, dict):
                continue
            name = str(detail.get("name", ""))
            score = detail.get("score", "")
            mode = str(detail.get("mode", ""))
            matched = detail.get("matched", [])
            matched_str = ", ".join(matched[:8]) if isinstance(matched, list) else ""
            lines.append(f"- {name}: mode={mode}, score={score}, matched=[{matched_str}]")
    lines.append("")
    lines.append("Selected skill content:")

    used = len("\n".join(lines))
    for skill in selected:
        body = skill.content[:max_skill_chars]
        remaining = max_total_chars - used
        if remaining <= 400:
            break
        if len(body) > remaining:
            body = body[:remaining]
        lines.append("")
        lines.append(f"## SKILL: {skill.name}")
        lines.append(body)
        used += len(body) + 32

    lines.append("")
    lines.append(
        "If a skill references files under references/ or scripts/, read them via skills_read_file.",
    )
    return "\n".join(lines)
