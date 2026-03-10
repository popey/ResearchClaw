from researchclaw.agents.react_agent import ScholarAgent


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
