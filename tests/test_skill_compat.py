from types import SimpleNamespace
from pathlib import Path

from researchclaw.agents.skill_compat import (
    SkillDoc,
    build_skill_context_prompt,
    explain_skill_selection,
    extract_skill_runtime_spec,
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


def test_parse_skill_doc_openclaw_metadata_flags(tmp_path: Path) -> None:
    skill_dir = tmp_path / "planner"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: planner\n"
        "description: Plan tasks for the user\n"
        "user-invocable: true\n"
        "disable-model-invocation: true\n"
        "aliases:\n"
        "  - task-planner\n"
        "metadata:\n"
        "  short-description: planner\n"
        "---\n\n"
        "# Planner Skill\n",
        encoding="utf-8",
    )
    parsed = parse_skill_doc(skill_dir, executable=True)
    assert parsed is not None
    assert parsed.user_invocable is True
    assert parsed.model_invocable is False
    assert "task-planner" in parsed.aliases
    assert parsed.metadata["name"] == "planner"


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


def test_select_relevant_skills_skip_user_only_skill_without_slash() -> None:
    skills = [
        SkillDoc(
            name="planner",
            description="User-invoked planning workflow",
            content="# Planner",
            path="/tmp/planner/SKILL.md",
            aliases={"planner"},
            keywords={"plan", "planner"},
            user_invocable=True,
            model_invocable=False,
        ),
    ]
    selected = select_relevant_skills("帮我规划一下本周任务", skills)
    assert selected == []


def test_select_relevant_skills_skip_non_user_invocable_slash_alias() -> None:
    skills = [
        SkillDoc(
            name="internal-only",
            description="Internal automation",
            content="# Internal",
            path="/tmp/internal/SKILL.md",
            aliases={"internal-only", "internal_only"},
            keywords={"internal"},
            user_invocable=False,
            model_invocable=True,
        ),
    ]
    selected = select_relevant_skills("执行 /internal_only", skills)
    assert selected == []


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


def test_build_skill_context_prompt_hides_user_only_skill_from_available_list() -> None:
    skills = [
        SkillDoc(
            name="planner",
            description="User-invoked planning workflow",
            content="# Planner",
            path="/tmp/planner/SKILL.md",
            executable=False,
            aliases={"planner"},
            keywords={"plan", "planner"},
            user_invocable=True,
            model_invocable=False,
        ),
        SkillDoc(
            name="news",
            description="latest news lookup",
            content="# News",
            path="/tmp/news/SKILL.md",
            executable=False,
            aliases={"news"},
            keywords={"news", "latest"},
        ),
    ]
    prompt = build_skill_context_prompt("latest news", skills)
    assert "- news [guidance-only, model-auto]:" in prompt
    assert "- planner [guidance-only, user-slash]:" not in prompt


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


def test_explain_skill_selection_contains_details() -> None:
    skills = [
        SkillDoc(
            name="news",
            description="latest news lookup",
            content="# News",
            path="/tmp/news/SKILL.md",
            aliases={"news"},
            keywords={"news", "latest"},
        ),
    ]
    debug = explain_skill_selection("latest news", skills)
    assert debug["selected"] == ["news"]
    assert isinstance(debug.get("details"), list)


def test_explain_skill_selection_chinese_news_synonym() -> None:
    skills = [
        SkillDoc(
            name="news",
            description="latest headlines",
            content="# News",
            path="/tmp/news/SKILL.md",
            aliases={"news"},
            keywords={"news", "latest", "headlines"},
        ),
    ]
    debug = explain_skill_selection("给我今天科技新闻", skills)
    assert debug["selected"] == ["news"]


def test_extract_skill_runtime_spec_supports_multiple_exports() -> None:
    fn = lambda: "ok"

    module = SimpleNamespace(
        TOOLS={"tool_a": fn},
        register=lambda: {"tool_b": lambda: "b"},
    )
    runtime = extract_skill_runtime_spec(module)
    assert runtime.entrypoint == "TOOLS"
    assert runtime.tools == {"tool_a": fn}

    module = SimpleNamespace(
        get_tools=lambda: [
            {"name": "tool_c", "handler": fn},
        ],
    )
    runtime = extract_skill_runtime_spec(module)
    assert runtime.entrypoint == "get_tools"
    assert runtime.tools == {"tool_c": fn}

    module = SimpleNamespace(
        skill=SimpleNamespace(
            get_tools=lambda: {"tool_d": fn},
        ),
    )
    runtime = extract_skill_runtime_spec(module)
    assert runtime.entrypoint == "skill"
    assert runtime.tools == {"tool_d": fn}
