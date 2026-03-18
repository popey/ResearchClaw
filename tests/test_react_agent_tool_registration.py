from pathlib import Path

import researchclaw.agents.react_agent as react_agent_module
from researchclaw.agents.react_agent import ScholarAgent
from researchclaw.agents.skill_compat import SkillDoc


def _make_agent(namesake_strategy: str) -> ScholarAgent:
    agent = ScholarAgent.__new__(ScholarAgent)
    agent._tools = {}
    agent.namesake_strategy = namesake_strategy  # type: ignore[attr-defined]
    agent._tool_schemas = []  # type: ignore[attr-defined]
    agent._build_tool_schemas = lambda: [{"type": "function"}]  # type: ignore[attr-defined]
    return agent


def test_register_tool_skip_duplicate() -> None:
    agent = _make_agent("skip")
    f1 = lambda: "a"
    f2 = lambda: "b"
    agent._register_tool("dup", f1, source="t1")
    agent._register_tool("dup", f2, source="t2")
    assert agent._tools["dup"] is f1


def test_register_tool_rename_duplicate() -> None:
    agent = _make_agent("rename")
    f1 = lambda: "a"
    f2 = lambda: "b"
    agent._register_tool("dup", f1, source="t1")
    renamed = agent._register_tool("dup", f2, source="t2")
    assert renamed != "dup"
    assert agent._tools["dup"] is f1
    assert agent._tools[renamed] is f2


def test_register_mcp_clients_refreshes_schemas() -> None:
    agent = _make_agent("override")

    class _DummyMcp:
        name = "demo"

        def get_tools(self):
            return {"mcp_tool": lambda: "ok"}

    agent.register_mcp_clients([_DummyMcp()])
    assert "mcp_tool" in agent._tools
    assert agent._tool_schemas == [{"type": "function"}]


def test_load_skill_accepts_get_tools_entrypoint(tmp_path) -> None:
    skill_dir = tmp_path / "third_party_skill"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "def sample_tool():\n"
        "    return 'ok'\n\n"
        "def get_tools():\n"
        "    return {'sample_tool': sample_tool}\n",
        encoding="utf-8",
    )

    agent = _make_agent("override")
    agent._load_skill(skill_dir)
    assert "sample_tool" in agent._tools


def test_register_builtin_tools_excludes_skill_bound_tools() -> None:
    agent = _make_agent("override")
    agent._register_builtin_tools()

    assert "run_shell" in agent._tools
    assert "read_file" in agent._tools
    assert "skills_activate" in agent._tools

    assert "arxiv_search" not in agent._tools
    assert "read_paper" not in agent._tools
    assert "plot_chart" not in agent._tools
    assert "cron_list_jobs" not in agent._tools
    assert "cron_create_job" not in agent._tools


def test_load_real_cron_skill_registers_cron_tools() -> None:
    agent = _make_agent("override")
    skill_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "researchclaw"
        / "agents"
        / "skills"
        / "cron"
    )

    agent._load_skill(skill_dir)

    assert "cron_list_jobs" in agent._tools
    assert "cron_create_job" in agent._tools


def test_build_messages_logs_selected_skills(monkeypatch) -> None:
    class _Memory:
        compact_summary = ""

        def get_recent_messages(self):
            return []

    agent = _make_agent("override")
    agent.sys_prompt = "system"  # type: ignore[attr-defined]
    agent.memory = _Memory()  # type: ignore[attr-defined]
    agent._skill_docs = [  # type: ignore[attr-defined]
        SkillDoc(
            name="browser_visible",
            description="Open a visible browser",
            content="# Browser",
            path="/tmp/browser/SKILL.md",
            aliases={"browser_visible", "browser-visible"},
            keywords={"browser", "visible"},
        ),
    ]
    agent._refresh_skill_docs = lambda: None  # type: ignore[attr-defined]
    agent._last_skill_debug = {}  # type: ignore[attr-defined]
    messages_seen: list[str] = []

    def _fake_info(message, *args, **kwargs):
        rendered = str(message) % args if args else str(message)
        messages_seen.append(rendered)

    monkeypatch.setattr(react_agent_module.logger, "info", _fake_info)

    messages = agent._build_messages("请执行 /browser_visible 打开浏览器")

    assert messages[0]["role"] == "system"
    assert any("[Skill Select]" in item for item in messages_seen)
    assert any("browser_visible" in item for item in messages_seen)
