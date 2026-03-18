"""Tools for reading and inspecting skill files at runtime."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def skills_list(active_only: bool = True) -> list[dict[str, Any]]:
    """List installed skills and their metadata."""
    from ..skills_manager import SkillsManager

    manager = SkillsManager()
    if active_only:
        active = set(manager.list_active_skills())
        all_skills = manager.list_available_skills()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "source": s.source,
                "scope": getattr(s, "scope", ""),
                "path": s.path,
                "location": getattr(s, "location", ""),
                "enabled": s.name in active,
                "triggers": getattr(s, "triggers", []),
                "format": getattr(s, "format", "legacy"),
                "diagnostics": getattr(s, "diagnostics", []),
            }
            for s in all_skills
            if s.name in active
        ]

    all_skills = manager.list_available_skills()
    active = set(manager.list_active_skills())
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "source": s.source,
            "scope": getattr(s, "scope", ""),
            "path": s.path,
            "location": getattr(s, "location", ""),
            "enabled": s.name in active,
            "triggers": getattr(s, "triggers", []),
            "format": getattr(s, "format", "legacy"),
            "diagnostics": getattr(s, "diagnostics", []),
        }
        for s in all_skills
    ]


def skills_activate(
    skill_name: str,
    source: str = "active",
) -> dict[str, Any]:
    """Return SKILL.md content and bundled file inventory for a skill."""
    from ..skills_manager import SkillsManager

    logger.info(
        "[Skill Activate] requested skill=%s source=%s",
        skill_name,
        source,
    )
    payload = SkillsManager().activate_skill(skill_name=skill_name, source=source)
    if payload is None:
        logger.warning(
            "[Skill Activate] skill not found skill=%s source=%s",
            skill_name,
            source,
        )
        return {
            "error": (
                "Skill not found. Use skills_list() first to inspect available "
                "skills and their paths."
            ),
        }
    logger.info(
        "[Skill Activate] loaded id=%s name=%s refs=%d scripts=%d",
        payload.get("id", ""),
        payload.get("name", ""),
        len(payload.get("references", []) or []),
        len(payload.get("scripts", []) or []),
    )
    return payload


def skills_read_file(
    skill_name: str,
    file_path: str = "SKILL.md",
    source: str = "active",
) -> str:
    """Read SKILL.md or references/scripts file from a skill."""
    from ..skills_manager import SkillsManager

    content = SkillsManager().load_skill_file(
        skill_name=skill_name,
        file_path=file_path,
        source=source,
    )
    if content is None:
        return (
            "Error: skill file not found or path not allowed. "
            "Allowed files: SKILL.md, references/*, scripts/*"
        )
    return content
