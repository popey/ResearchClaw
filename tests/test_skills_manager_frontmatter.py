from researchclaw.agents.skills_manager import _parse_skill_md


def test_parse_skill_md_yaml_frontmatter() -> None:
    text = (
        "---\n"
        "name: browser_visible\n"
        "description: launch visible browser\n"
        "triggers:\n"
        "  - visible browser\n"
        "  - headed\n"
        "---\n\n"
        "# Skill\n"
    )
    meta = _parse_skill_md(text)
    assert meta.get("name") == "browser_visible"
    assert meta.get("description") == "launch visible browser"
    triggers = meta.get("triggers")
    assert isinstance(triggers, list)
    assert "headed" in triggers


def test_parse_skill_md_bullet_fallback() -> None:
    text = "- name: cron\\n- description: schedule jobs\\n- triggers: cron, schedule\\n"
    meta = _parse_skill_md(text)
    assert meta.get("name") == "cron"
    assert meta.get("description") == "schedule jobs"
