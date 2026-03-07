from pathlib import Path

from researchclaw.agents.skill_compat import (
    SkillDoc,
    build_skill_context_prompt,
    parse_skill_doc,
    select_relevant_skills,
)


def test_parse_skill_doc_from_skill_md(tmp_path: Path) -> None:
    skill_dir = tmp_path / "browser_visible"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "- name: browser_visible\n"
        "- description: Open a visible browser\n\n"
        "# Browser Visible\n",
        encoding="utf-8",
    )

    parsed = parse_skill_doc(skill_dir, executable=False)
    assert parsed is not None
    assert parsed.name == "browser_visible"
    assert "visible browser" in parsed.description
    assert "browser-visible" in parsed.aliases


def test_parse_skill_doc_with_yaml_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "news"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: news\n"
        "description: Fetch latest headlines\n"
        "---\n\n"
        "# News Skill\n",
        encoding="utf-8",
    )
    parsed = parse_skill_doc(skill_dir, executable=False)
    assert parsed is not None
    assert parsed.name == "news"
    assert parsed.description == "Fetch latest headlines"


def test_select_relevant_skills_by_slash_command() -> None:
    skills = [
        SkillDoc(
            name="browser_visible",
            description="",
            content="# Browser",
            path="/tmp/browser/SKILL.md",
            aliases={"browser-visible", "browser_visible"},
            keywords={"browser", "visible"},
        ),
        SkillDoc(
            name="news",
            description="",
            content="# News",
            path="/tmp/news/SKILL.md",
            aliases={"news"},
            keywords={"news"},
        ),
    ]
    selected = select_relevant_skills(
        "请执行 /browser_visible 打开有界面浏览器",
        skills,
    )
    assert [s.name for s in selected] == ["browser_visible"]


def test_build_skill_context_prompt_includes_selected_skill() -> None:
    skills = [
        SkillDoc(
            name="research-collect",
            description="Collect papers and repos",
            content="# Collect\nUse arxiv_search",
            path="/tmp/research-collect/SKILL.md",
            executable=False,
            aliases={"research-collect", "research_collect"},
            keywords={"research", "collect", "papers"},
        ),
    ]
    prompt = build_skill_context_prompt("/research-collect llm agent papers", skills)
    assert "Available skills:" in prompt
    assert "Selected skills for current user message:" in prompt
    assert "## SKILL: research-collect" in prompt


def test_select_relevant_skills_chinese_keywords() -> None:
    skills = [
        SkillDoc(
            name="dingtalk_channel_connect",
            description="Use DingTalk channel setup workflow",
            content="# 钉钉 Channel 自动连接\n支持钉钉登录与频道配置",
            path="/tmp/dingtalk/SKILL.md",
            aliases={"dingtalk-channel-connect", "dingtalk_channel_connect"},
            keywords={"dingtalk", "钉钉", "频道", "连接"},
        ),
    ]
    selected = select_relevant_skills("帮我配置钉钉频道接入", skills)
    assert [s.name for s in selected] == ["dingtalk_channel_connect"]
