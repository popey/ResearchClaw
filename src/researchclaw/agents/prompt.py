"""System prompt construction for ScholarAgent.

Reads Markdown profile files from the working directory to build a
research-oriented system prompt. Falls back to a sensible default when
the required files are missing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..constant import WORKING_DIR

logger = logging.getLogger(__name__)

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_SYS_PROMPT = """\
You are **Scholar**, an AI research assistant created by ResearchClaw.

Your mission is to help academic researchers with their scientific workflow:
- Searching and discovering relevant papers (ArXiv, Semantic Scholar, Google Scholar)
- Reading, summarizing, and critically analyzing research papers
- Managing references and BibTeX citations
- Performing data analysis and creating publication-quality visualizations
- Assisting with LaTeX writing and literature reviews
- Tracking experiments and maintaining research notes
- Staying up-to-date with the latest publications in the user's fields of interest

Guidelines:
- Always cite sources when referring to specific papers or findings
- Be precise with scientific terminology
- When summarizing papers, highlight methodology, key findings, and limitations
- For data analysis, explain statistical methods and assumptions
- Provide BibTeX entries when recommending papers
- Respect the user's research domain expertise — assist, don't patronize
- When uncertain about scientific claims, clearly state the uncertainty

You have access to various research tools. Use them proactively to help the user.
"""

# ── Prompt file configuration ──────────────────────────────────────────────


@dataclass
class PromptFileSpec:
    """Specification for a single prompt file."""

    filename: str
    required: bool = True


@dataclass
class PromptConfig:
    """Ordered list of Markdown files that compose the system prompt."""

    files: list[PromptFileSpec] = field(
        default_factory=lambda: [
            PromptFileSpec("AGENTS.md", required=True),
            PromptFileSpec("SOUL.md", required=True),
            PromptFileSpec("PROFILE.md", required=False),
            PromptFileSpec("RESEARCH_AREAS.md", required=False),
        ],
    )


# ── Builder ─────────────────────────────────────────────────────────────────

_YAML_FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


class PromptBuilder:
    """Build the system prompt from Markdown files in a directory."""

    def __init__(
        self,
        directory: str | Path,
        config: Optional[PromptConfig] = None,
    ) -> None:
        self.directory = Path(directory)
        self.config = config or PromptConfig()

    def build(self) -> str:
        """Read and concatenate prompt files.

        Returns the concatenated Markdown content, or
        :data:`DEFAULT_SYS_PROMPT` if any required file is missing.
        """
        parts: list[str] = []
        for spec in self.config.files:
            path = self.directory / spec.filename
            if not path.is_file():
                if spec.required:
                    logger.warning(
                        "Required prompt file missing: %s – using default prompt",
                        path,
                    )
                    return DEFAULT_SYS_PROMPT
                continue

            text = path.read_text(encoding="utf-8")
            # Strip optional YAML front-matter
            text = _YAML_FRONT_MATTER.sub("", text).strip()
            parts.append(f"# {spec.filename}\n\n{text}")

        if not parts:
            return DEFAULT_SYS_PROMPT

        return "\n\n---\n\n".join(parts)


# ── Convenience functions ───────────────────────────────────────────────────


def build_system_prompt_from_working_dir() -> str:
    """Build the system prompt using files in :data:`WORKING_DIR`."""
    return PromptBuilder(WORKING_DIR).build()


def build_bootstrap_guidance(language: str = "en") -> str:
    """Return first-run bootstrap guidance.

    Parameters
    ----------
    language:
        ``"en"`` for English, ``"zh"`` for Chinese.
    """
    if language.startswith("zh"):
        return (
            "# 🌟 引导模式已激活\n\n"
            "**你现在处于首次运行引导阶段。**\n\n"
            "工作目录里存在 `BOOTSTRAP.md`，你应先按引导建立协作关系，再进入常规问答。\n\n"
            "请按下面顺序执行：\n"
            "1. 阅读并遵循 `BOOTSTRAP.md` 的步骤，先和用户完成初次沟通。\n"
            "2. 协助用户完善关键文件：`PROFILE.md`、`SOUL.md`、`AGENTS.md`、`HEARTBEAT.md`。\n"
            "3. 引导用户确认语言、研究方向、沟通偏好与任务节奏。\n"
            "4. 引导完成后，提醒用户可删除 `BOOTSTRAP.md`（或在工作区手动维护）。\n\n"
            "如果用户明确要求跳过引导，就继续回答用户当前问题。"
        )
    return (
        "# 🌟 Bootstrap Mode Activated\n\n"
        "**You are in first-run onboarding mode.**\n\n"
        "A `BOOTSTRAP.md` file exists in the workspace. Guide the user through onboarding before regular Q&A.\n\n"
        "Please follow this order:\n"
        "1. Read and follow the steps in `BOOTSTRAP.md`.\n"
        "2. Help the user complete key files: `PROFILE.md`, `SOUL.md`, `AGENTS.md`, `HEARTBEAT.md`.\n"
        "3. Confirm language, research areas, collaboration preferences, and cadence.\n"
        "4. After onboarding, remind the user they can remove `BOOTSTRAP.md`.\n\n"
        "If the user explicitly wants to skip onboarding, proceed with their current request."
    )
