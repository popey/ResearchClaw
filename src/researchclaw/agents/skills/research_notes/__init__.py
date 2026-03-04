"""Research notes skill – structured note-taking with tagging and search."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ....constant import MEMORY_DIR


def register():
    """Register research note tools."""

    def create_note(
        title: str,
        content: str,
        tags: Optional[list[str]] = None,
        paper_refs: Optional[list[str]] = None,
    ) -> dict:
        """Create a structured research note.

        Parameters
        ----------
        title:
            Note title.
        content:
            Note content (supports Markdown).
        tags:
            Categorisation tags.
        paper_refs:
            References to papers (ArXiv IDs, DOIs, etc.).

        Returns
        -------
        dict
            Created note record.
        """
        notes_dir = Path(MEMORY_DIR) / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        note_id = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        note = {
            "note_id": note_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "paper_refs": paper_refs or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        # Save as individual Markdown file
        md_file = notes_dir / f"{note_id}.md"
        header = f"---\ntitle: {title}\ntags: {', '.join(tags or [])}\ndate: {note['created_at']}\n---\n\n"
        md_file.write_text(header + content, encoding="utf-8")

        # Also append to index
        index_file = notes_dir / "index.jsonl"
        with open(index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(note, ensure_ascii=False) + "\n")

        return note

    def search_notes(
        query: str,
        tags: Optional[list[str]] = None,
        max_results: int = 20,
    ) -> list[dict]:
        """Search research notes.

        Parameters
        ----------
        query:
            Search query.
        tags:
            Optional filter by tags.
        max_results:
            Maximum results.
        """
        notes_dir = Path(MEMORY_DIR) / "notes"
        index_file = notes_dir / "index.jsonl"

        if not index_file.exists():
            return []

        results = []
        query_lower = query.lower()

        for line in index_file.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                note = json.loads(line)
                searchable = f"{note.get('title', '')} {note.get('content', '')}".lower()

                if query_lower in searchable:
                    if tags and not set(tags) & set(note.get("tags", [])):
                        continue
                    results.append(note)
            except json.JSONDecodeError:
                continue

        return results[-max_results:]

    def list_note_tags() -> dict[str, int]:
        """List all tags used in research notes with their counts."""
        notes_dir = Path(MEMORY_DIR) / "notes"
        index_file = notes_dir / "index.jsonl"

        if not index_file.exists():
            return {}

        tag_counts: dict[str, int] = {}
        for line in index_file.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            try:
                note = json.loads(line)
                for tag in note.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            except json.JSONDecodeError:
                continue

        return dict(sorted(tag_counts.items(), key=lambda x: -x[1]))

    return {
        "create_note": create_note,
        "search_notes": search_notes,
        "list_note_tags": list_note_tags,
    }
