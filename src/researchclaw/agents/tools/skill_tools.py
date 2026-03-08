"""Tools for reading and inspecting skill files at runtime."""

from __future__ import annotations

from typing import Any


def skills_list(active_only: bool = True) -> list[dict[str, Any]]:
    """List installed skills and their metadata."""
    from ..skills_manager import SkillsManager

    manager = SkillsManager()
    if active_only:
        active = set(manager.list_active_skills())
        all_skills = manager.list_available_skills()
        return [
            {
                "name": s.name,
                "description": s.description,
                "source": s.source,
                "enabled": s.name in active,
                "triggers": getattr(s, "triggers", []),
            }
            for s in all_skills
            if s.name in active
        ]

    all_skills = manager.list_available_skills()
    active = set(manager.list_active_skills())
    return [
        {
            "name": s.name,
            "description": s.description,
            "source": s.source,
            "enabled": s.name in active,
            "triggers": getattr(s, "triggers", []),
        }
        for s in all_skills
    ]


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
