"""ResearchClaw Agent module.

Uses lazy-loading to avoid importing heavy dependencies when only CLI
skill-management commands are used.
"""

__all__ = ["ScholarAgent", "create_model_and_formatter"]


def __getattr__(name: str):
    if name == "ScholarAgent":
        from .react_agent import ScholarAgent

        return ScholarAgent
    if name == "create_model_and_formatter":
        from .model_factory import create_model_and_formatter

        return create_model_and_formatter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
