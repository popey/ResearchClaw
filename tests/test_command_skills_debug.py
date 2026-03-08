from researchclaw.agents.command_handler import CommandHandler


class _DummyMemory:
    compact_summary = ""

    def new_session(self):
        return None

    def compact(self):
        return None

    def clear(self):
        return None

    def get_stats(self):
        return {
            "message_count": 0,
            "session_count": 0,
            "has_summary": False,
            "note_count": 0,
            "paper_count": 0,
        }

    def get_discussed_papers(self):
        return []


class _DummyAgent:
    def __init__(self):
        self.working_dir = "."
        self.memory = _DummyMemory()
        self._skill_docs = []

    def get_last_skill_debug(self):
        return {
            "selected": ["news"],
            "details": [
                {
                    "name": "news",
                    "mode": "keywords",
                    "score": 1.2,
                    "matched": ["news"],
                },
            ],
        }

    def get_skill_debug_for_query(self, query: str):
        return {
            "selected": ["browser_visible"],
            "details": [
                {
                    "name": "browser_visible",
                    "mode": "slash",
                    "score": 10000.0,
                    "matched": ["browser_visible"],
                },
            ],
            "query": query,
        }


def test_command_skills_debug_last() -> None:
    handler = CommandHandler(_DummyAgent())
    out = handler.handle("/skills debug")
    assert out is not None
    assert "Skill Debug" in out
    assert "news" in out


def test_command_skills_debug_query() -> None:
    handler = CommandHandler(_DummyAgent())
    out = handler.handle("/skills debug /browser_visible open browser")
    assert out is not None
    assert "browser_visible" in out
