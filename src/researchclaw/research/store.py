"""Persistence backends for research workflows and linked graph state."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Protocol

from researchclaw.constant import RESEARCH_DIR, RESEARCH_STATE_FILE

from .models import ResearchState


class ResearchStore(Protocol):
    """Minimal persistence protocol used by the research service."""

    @property
    def path(self) -> Path:
        """Location of the underlying persistence file."""

    async def load(self) -> ResearchState:
        """Load the current research state."""

    async def save(self, state: ResearchState) -> None:
        """Persist the current research state."""


class JsonResearchStore:
    """Single-file JSON persistence for the research domain."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            env_path = os.environ.get("RESEARCHCLAW_RESEARCH_STATE_PATH", "").strip()
            path = env_path or (Path(RESEARCH_DIR) / RESEARCH_STATE_FILE)
        self._path = Path(path).expanduser().resolve()
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    async def load(self) -> ResearchState:
        async with self._lock:
            if not self._path.exists():
                return ResearchState()
            payload = self._path.read_text(encoding="utf-8")
            return ResearchState.model_validate_json(payload)

    async def save(self, state: ResearchState) -> None:
        async with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
            payload = state.model_dump(mode="json")
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp_path.replace(self._path)


class SQLiteResearchStore:
    """SQLite-backed research persistence with state snapshots and audit index."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        bootstrap_json_path: str | Path | None = None,
    ) -> None:
        if path is None:
            env_path = os.environ.get("RESEARCHCLAW_RESEARCH_DB_PATH", "").strip()
            path = env_path or (Path(RESEARCH_DIR) / "state.db")
        self._path = Path(path).expanduser().resolve()
        self._bootstrap_json_path = (
            Path(bootstrap_json_path).expanduser().resolve()
            if bootstrap_json_path
            else None
        )
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state_snapshot (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """,
        )
        conn.commit()

    def _bootstrap_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if self._bootstrap_json_path is not None:
            candidates.append(self._bootstrap_json_path)
        env_path = os.environ.get("RESEARCHCLAW_RESEARCH_STATE_PATH", "").strip()
        if env_path:
            candidates.append(Path(env_path).expanduser().resolve())
        candidates.append(Path(RESEARCH_DIR).expanduser().resolve() / RESEARCH_STATE_FILE)
        unique: list[Path] = []
        for candidate in candidates:
            if candidate.suffix.lower() != ".json":
                continue
            if candidate == self._path:
                continue
            if candidate not in unique:
                unique.append(candidate)
        return unique

    def _bootstrap_from_json_if_needed(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT payload FROM state_snapshot WHERE id = 1",
        ).fetchone()
        if row is not None:
            return
        for candidate in self._bootstrap_candidates():
            if not candidate.is_file():
                continue
            try:
                payload = candidate.read_text(encoding="utf-8")
                state = ResearchState.model_validate_json(payload)
            except Exception:
                continue
            self._save_sync(conn, state)
            return

    def _save_sync(self, conn: sqlite3.Connection, state: ResearchState) -> None:
        payload = json.dumps(
            state.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        updated_at = getattr(state, "updated_at", None) or ""
        if not updated_at:
            updated_at = max(
                [
                    *[item.updated_at for item in state.projects if getattr(item, "updated_at", "")],
                    *[item.updated_at for item in state.workflows if getattr(item, "updated_at", "")],
                    *[item.updated_at for item in state.notes if getattr(item, "updated_at", "")],
                    *[item.updated_at for item in state.claims if getattr(item, "updated_at", "")],
                    *[item.updated_at for item in state.evidences if getattr(item, "updated_at", "")],
                ],
                default="",
            )
        conn.execute(
            """
            INSERT INTO state_snapshot (id, payload, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (payload, updated_at),
        )

        existing_rows = conn.execute("SELECT id FROM audit_events").fetchall()
        existing_ids = {str(row["id"]) for row in existing_rows}
        for event in state.audit_events:
            if event.id in existing_ids:
                continue
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, project_id, workflow_id, entity_type, entity_id, action, created_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.project_id,
                    event.workflow_id,
                    event.entity_type,
                    event.entity_id,
                    event.action,
                    event.created_at,
                    json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                ),
            )
        conn.commit()

    async def load(self) -> ResearchState:
        async with self._lock:
            conn = self._connect()
            try:
                self._ensure_schema(conn)
                self._bootstrap_from_json_if_needed(conn)
                row = conn.execute(
                    "SELECT payload FROM state_snapshot WHERE id = 1",
                ).fetchone()
                if row is None:
                    return ResearchState()
                return ResearchState.model_validate_json(str(row["payload"]))
            finally:
                conn.close()

    async def save(self, state: ResearchState) -> None:
        async with self._lock:
            conn = self._connect()
            try:
                self._ensure_schema(conn)
                self._save_sync(conn, state)
            finally:
                conn.close()


def build_default_research_store() -> ResearchStore:
    """Return the default persistence backend for the research domain."""

    db_path = os.environ.get("RESEARCHCLAW_RESEARCH_DB_PATH", "").strip()
    state_path = os.environ.get("RESEARCHCLAW_RESEARCH_STATE_PATH", "").strip()
    if state_path and Path(state_path).suffix.lower() == ".json" and not db_path:
        return JsonResearchStore(state_path)
    if state_path and Path(state_path).suffix.lower() == ".db":
        return SQLiteResearchStore(state_path)
    return SQLiteResearchStore(
        db_path or (Path(RESEARCH_DIR) / "state.db"),
        bootstrap_json_path=state_path or (Path(RESEARCH_DIR) / RESEARCH_STATE_FILE),
    )
