"""Application service for project-centric research workflows."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import (
    ArtifactType,
    ArtifactRelation,
    AuditEvent,
    EvidenceSource,
    EvidenceType,
    ExperimentEvent,
    ExperimentExecutionCatalogEntry,
    ExperimentExecutionBinding,
    ExperimentProvenance,
    ExperimentRunnerProfile,
    ExperimentRunnerRule,
    ExperimentRunnerTemplate,
    ExperimentRun,
    ProjectMemoryEntry,
    ProactiveReminder,
    ProjectPaperWatch,
    ResultBundleSchemaDefinition,
    ResearchArtifact,
    ResearchClaim,
    ResearchDatasetVersion,
    ResearchEvidence,
    ResearchNote,
    ResearchProject,
    ResearchState,
    ResearchWorkflow,
    WorkflowCheckpoint,
    WorkflowExecutionPolicy,
    WORKFLOW_STAGES,
    WorkflowBinding,
    WorkflowStageName,
    WorkflowStageState,
    WorkflowTask,
    utc_now,
)
from .store import JsonResearchStore, ResearchStore, build_default_research_store


_DEFAULT_STAGE_TASKS: dict[str, tuple[str, str]] = {
    "literature_search": (
        "Search and shortlist core papers",
        "Collect the most relevant papers, benchmarks, and citation anchors.",
    ),
    "paper_reading": (
        "Read prioritized papers",
        "Extract methods, limitations, assumptions, and reusable evidence.",
    ),
    "note_synthesis": (
        "Synthesize notes into themes",
        "Turn raw reading notes into themes, gaps, tensions, and open questions.",
    ),
    "hypothesis_queue": (
        "Queue candidate hypotheses",
        "Rank plausible hypotheses or research directions with expected value.",
    ),
    "experiment_plan": (
        "Define an experiment plan",
        "Specify baselines, ablations, datasets, metrics, and exit criteria.",
    ),
    "experiment_run": (
        "Run or collect experiments",
        "Execute planned experiments and archive outputs for comparison.",
    ),
    "result_analysis": (
        "Analyze outcomes",
        "Interpret metrics, figures, and failure modes into reusable findings.",
    ),
    "writing_tasks": (
        "Draft writing tasks",
        "Convert validated findings into outlines, sections, and revision todos.",
    ),
    "review_and_followup": (
        "Review open risks and follow-ups",
        "Check unresolved claims, next actions, and long-running follow-up items.",
    ),
}


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _remove_empty_strings(items: Iterable[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _hours_since(value: str | None, *, now: datetime) -> float | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600.0)


def _stringify_metadata(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _json_ready(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _artifact_type_from_path(path: str) -> ArtifactType:
    suffix = Path(path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".webp", ".pdf"}:
        return "generated_figure"
    if suffix in {".csv", ".tsv", ".xlsx", ".xls", ".json"}:
        return "generated_table"
    if suffix in {".md", ".txt"}:
        return "summary"
    return "experiment_result"


class ResearchService:
    """Structured state management for research projects and workflows."""

    def __init__(self, store: ResearchStore | None = None) -> None:
        self._store = store or build_default_research_store()

    @property
    def path(self) -> Path:
        return self._store.path

    async def load_state(self) -> ResearchState:
        return await self._store.load()

    async def save_state(self, state: ResearchState) -> None:
        await self._store.save(state)

    # ---- generic find helpers ----

    @staticmethod
    def _project(state: ResearchState, project_id: str) -> ResearchProject:
        for item in state.projects:
            if item.id == project_id:
                return item
        raise ValueError(f"Unknown project: {project_id}")

    @staticmethod
    def _workflow(state: ResearchState, workflow_id: str) -> ResearchWorkflow:
        for item in state.workflows:
            if item.id == workflow_id:
                return item
        raise ValueError(f"Unknown workflow: {workflow_id}")

    @staticmethod
    def _claim(state: ResearchState, claim_id: str) -> ResearchClaim:
        for item in state.claims:
            if item.id == claim_id:
                return item
        raise ValueError(f"Unknown claim: {claim_id}")

    @staticmethod
    def _note(state: ResearchState, note_id: str) -> ResearchNote:
        for item in state.notes:
            if item.id == note_id:
                return item
        raise ValueError(f"Unknown note: {note_id}")

    @staticmethod
    def _experiment(state: ResearchState, experiment_id: str) -> ExperimentRun:
        for item in state.experiments:
            if item.id == experiment_id:
                return item
        raise ValueError(f"Unknown experiment: {experiment_id}")

    @staticmethod
    def _artifact(state: ResearchState, artifact_id: str) -> ResearchArtifact:
        for item in state.artifacts:
            if item.id == artifact_id:
                return item
        raise ValueError(f"Unknown artifact: {artifact_id}")

    @staticmethod
    def _workflow_stage(
        workflow: ResearchWorkflow,
        stage_name: WorkflowStageName,
    ) -> WorkflowStageState:
        for stage in workflow.stages:
            if stage.name == stage_name:
                return stage
        raise ValueError(f"Unknown workflow stage: {stage_name}")

    @staticmethod
    def _workflow_task(
        workflow: ResearchWorkflow,
        task_id: str,
    ) -> WorkflowTask:
        for task in workflow.tasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Unknown workflow task: {task_id}")

    @staticmethod
    def _touch(item: Any, *, now: str | None = None) -> None:
        if hasattr(item, "updated_at"):
            setattr(item, "updated_at", now or utc_now())

    @staticmethod
    def _model_payload(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return dict(value)
        return {"value": value}

    @staticmethod
    def _memory_entry(state: ResearchState, memory_id: str) -> ProjectMemoryEntry:
        for item in state.project_memory:
            if item.id == memory_id:
                return item
        raise ValueError(f"Unknown project memory entry: {memory_id}")

    @staticmethod
    def _dataset_version(
        state: ResearchState,
        dataset_version_id: str,
    ) -> ResearchDatasetVersion:
        for item in state.dataset_versions:
            if item.id == dataset_version_id:
                return item
        raise ValueError(f"Unknown dataset version: {dataset_version_id}")

    @staticmethod
    def _task_dependencies_satisfied(
        workflow: ResearchWorkflow,
        task: WorkflowTask,
    ) -> bool:
        dependency_ids = set(_remove_empty_strings(task.depends_on))
        if not dependency_ids:
            return True
        completed_statuses = {"completed", "cancelled"}
        for dependency_id in dependency_ids:
            dependency = ResearchService._workflow_task(workflow, dependency_id)
            if dependency.status not in completed_statuses:
                return False
        return True

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _hash_existing_paths(
        cls,
        paths: Iterable[str],
        *,
        base_dir: Path,
    ) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for item in paths:
            clean = str(item or "").strip()
            if not clean:
                continue
            resolved = cls._resolve_existing_path(clean, base_dir=base_dir)
            if resolved is None or not resolved.is_file():
                continue
            hashes[str(resolved)] = cls._hash_file(resolved)
        return hashes

    @staticmethod
    def _git_output(*args: str, cwd: Path | None = None) -> str:
        try:
            return subprocess.check_output(
                ["git", *args],
                cwd=str(cwd or Path.cwd()),
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            return ""

    def _record_audit_event(
        self,
        state: ResearchState,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        project_id: str = "",
        workflow_id: str = "",
        summary: str = "",
        actor: str = "system",
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            project_id=project_id,
            workflow_id=workflow_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            summary=summary,
            before=dict(before or {}),
            after=dict(after or {}),
            metadata=dict(metadata or {}),
        )
        state.audit_events.append(event)
        return event

    def _record_workflow_checkpoint(
        self,
        state: ResearchState,
        workflow: ResearchWorkflow,
        *,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowCheckpoint:
        snapshot = {
            "current_stage": workflow.current_stage,
            "status": workflow.status,
            "note_ids": list(workflow.note_ids),
            "claim_ids": list(workflow.claim_ids),
            "artifact_ids": list(workflow.artifact_ids),
            "experiment_ids": list(workflow.experiment_ids),
            "metadata": dict(metadata or {}),
        }
        checkpoint = WorkflowCheckpoint(
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            stage=workflow.current_stage,
            workflow_status=workflow.status,
            reason=reason,
            task_statuses={
                task.id: task.status
                for task in workflow.tasks
                if task.stage == workflow.current_stage
            },
            snapshot=snapshot,
        )
        last = next(
            (
                item
                for item in reversed(state.checkpoints)
                if item.workflow_id == workflow.id
            ),
            None,
        )
        if (
            last is not None
            and last.stage == checkpoint.stage
            and last.workflow_status == checkpoint.workflow_status
            and last.task_statuses == checkpoint.task_statuses
            and last.snapshot == checkpoint.snapshot
            and last.reason == checkpoint.reason
        ):
            return last
        state.checkpoints.append(checkpoint)
        return checkpoint

    @staticmethod
    def _clone_binding(binding: WorkflowBinding) -> WorkflowBinding:
        return WorkflowBinding.model_validate(binding.model_dump(mode="json"))

    def _merge_binding(
        self,
        *,
        base: WorkflowBinding,
        patch: dict[str, Any] | None,
    ) -> WorkflowBinding:
        if not patch:
            return self._clone_binding(base)
        payload = base.model_dump(mode="json")
        for key, value in patch.items():
            if value is None:
                continue
            if key == "metadata" and isinstance(value, dict):
                merged_metadata = dict(payload.get("metadata") or {})
                merged_metadata.update(value)
                payload[key] = merged_metadata
                continue
            payload[key] = value
        return WorkflowBinding.model_validate(payload)

    def _merge_execution_policy(
        self,
        *,
        base: WorkflowExecutionPolicy,
        patch: dict[str, Any] | None,
    ) -> WorkflowExecutionPolicy:
        if not patch:
            return WorkflowExecutionPolicy.model_validate(
                base.model_dump(mode="json"),
            )
        payload = base.model_dump(mode="json")
        for key, value in patch.items():
            if value is None:
                continue
            payload[key] = value
        return WorkflowExecutionPolicy.model_validate(payload)

    @staticmethod
    def _clone_experiment_runner(
        profile: ExperimentRunnerProfile,
    ) -> ExperimentRunnerProfile:
        return ExperimentRunnerProfile.model_validate(
            profile.model_dump(mode="json"),
        )

    def _merge_runner_template(
        self,
        *,
        base: ExperimentRunnerTemplate,
        patch: dict[str, Any] | None,
    ) -> ExperimentRunnerTemplate:
        if not patch:
            return ExperimentRunnerTemplate.model_validate(
                base.model_dump(mode="json"),
            )
        payload = base.model_dump(mode="json")
        for key, value in patch.items():
            if value is None:
                continue
            if key in {"metadata", "environment", "parameter_overrides", "input_data_overrides"} and isinstance(value, dict):
                merged_value = dict(payload.get(key) or {})
                merged_value.update(value)
                payload[key] = merged_value
                continue
            if key == "command" and isinstance(value, list):
                payload[key] = _remove_empty_strings(value)
                continue
            payload[key] = value
        return ExperimentRunnerTemplate.model_validate(payload)

    @staticmethod
    def _merge_execution_catalog(
        *,
        base: list[ExperimentExecutionCatalogEntry],
        patch: list[dict[str, Any]] | None,
    ) -> list[ExperimentExecutionCatalogEntry]:
        if patch is None:
            return [
                ExperimentExecutionCatalogEntry.model_validate(
                    item.model_dump(mode="json"),
                )
                for item in base
            ]
        return [
            ExperimentExecutionCatalogEntry.model_validate(item)
            for item in patch
            if isinstance(item, dict)
        ]

    @staticmethod
    def _merge_result_bundle_schemas(
        *,
        base: list[ResultBundleSchemaDefinition],
        patch: list[dict[str, Any]] | None,
    ) -> list[ResultBundleSchemaDefinition]:
        if patch is None:
            return [
                ResultBundleSchemaDefinition.model_validate(
                    item.model_dump(mode="json"),
                )
                for item in base
            ]
        return [
            ResultBundleSchemaDefinition.model_validate(item)
            for item in patch
            if isinstance(item, dict)
        ]

    @staticmethod
    def _merge_contract_dicts(*contracts: dict[str, Any] | None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            for key in ("required_metrics", "required_outputs", "required_artifact_types"):
                values = _remove_empty_strings(contract.get(key, []))
                if not values:
                    continue
                merged = list(payload.get(key, []) or [])
                for value in values:
                    _append_unique(merged, value)
                payload[key] = merged
            for key, value in contract.items():
                if key in {"required_metrics", "required_outputs", "required_artifact_types"}:
                    continue
                if value is None:
                    continue
                payload[key] = value
        return payload

    @staticmethod
    def _result_bundle_schema_contract(
        schema: ResultBundleSchemaDefinition | None,
    ) -> dict[str, Any]:
        if schema is None:
            return {}
        return {
            key: values
            for key, values in {
                "required_metrics": _remove_empty_strings(schema.required_metrics),
                "required_outputs": _remove_empty_strings(schema.required_outputs),
                "required_artifact_types": _remove_empty_strings(
                    schema.required_artifact_types,
                ),
            }.items()
            if values
        }

    def _project_result_bundle_schema(
        self,
        state: ResearchState,
        *,
        project_id: str,
        schema_name: str,
    ) -> ResultBundleSchemaDefinition | None:
        normalized = str(schema_name or "").strip()
        if not normalized:
            return None
        project = self._project(state, project_id)
        for item in list(getattr(project, "result_bundle_schemas", []) or []):
            if str(getattr(item, "name", "") or "").strip() == normalized:
                return item
        return None

    def _merge_runner_profile(
        self,
        *,
        base: ExperimentRunnerProfile,
        patch: dict[str, Any] | None,
    ) -> ExperimentRunnerProfile:
        if not patch:
            return self._clone_experiment_runner(base)
        payload = base.model_dump(mode="json")
        for key, value in patch.items():
            if value is None:
                continue
            if key == "default" and isinstance(value, dict):
                payload["default"] = self._merge_runner_template(
                    base=base.default,
                    patch=value,
                ).model_dump(mode="json")
                continue
            if key == "kind_overrides":
                if not isinstance(value, dict):
                    continue
                existing = {
                    name: dict(template)
                    for name, template in base.kind_overrides.items()
                }
                if not value:
                    payload[key] = {}
                    continue
                for kind, template_patch in value.items():
                    normalized_kind = str(kind or "").strip()
                    if not normalized_kind:
                        continue
                    if template_patch is None:
                        existing.pop(normalized_kind, None)
                        continue
                    if not isinstance(template_patch, dict):
                        continue
                    merged_patch = dict(existing.get(normalized_kind) or {})
                    merged_patch.update(template_patch)
                    validated = ExperimentRunnerTemplate.model_validate(merged_patch)
                    existing[normalized_kind] = validated.model_dump(
                        mode="json",
                        exclude_defaults=True,
                    )
                payload[key] = existing
                continue
            if key == "rules" and isinstance(value, list):
                payload[key] = [
                    ExperimentRunnerRule.model_validate(item).model_dump(mode="json")
                    for item in value
                    if isinstance(item, dict)
                ]
                continue
            payload[key] = value
        return ExperimentRunnerProfile.model_validate(payload)

    def _merge_experiment_execution(
        self,
        *,
        base: ExperimentExecutionBinding,
        patch: dict[str, Any] | None,
    ) -> ExperimentExecutionBinding:
        if not patch:
            return ExperimentExecutionBinding.model_validate(
                base.model_dump(mode="json"),
            )
        payload = base.model_dump(mode="json")
        for key, value in patch.items():
            if value is None:
                continue
            if key in {"metadata", "environment"} and isinstance(value, dict):
                merged_value = dict(payload.get(key) or {})
                merged_value.update(value)
                payload[key] = merged_value
                continue
            payload[key] = value
        return ExperimentExecutionBinding.model_validate(payload)

    @staticmethod
    def _ensure_workflow_scaffold(workflow: ResearchWorkflow) -> None:
        if workflow.stages:
            return
        workflow.stages = [WorkflowStageState(name=stage) for stage in WORKFLOW_STAGES]

    @staticmethod
    def _stage_task_list(
        workflow: ResearchWorkflow,
        stage_name: WorkflowStageName,
    ) -> list[WorkflowTask]:
        return [task for task in workflow.tasks if task.stage == stage_name]

    def _seed_stage_task(self, workflow: ResearchWorkflow) -> WorkflowTask:
        stage = self._workflow_stage(workflow, workflow.current_stage)
        existing = self._stage_task_list(workflow, workflow.current_stage)
        if existing:
            for task in existing:
                _append_unique(stage.task_ids, task.id)
            return existing[0]

        title, description = _DEFAULT_STAGE_TASKS.get(
            workflow.current_stage,
            ("Advance workflow stage", "Continue the current workflow stage."),
        )
        task = WorkflowTask(
            stage=workflow.current_stage,
            title=title,
            description=description,
            status="pending",
        )
        workflow.tasks.append(task)
        _append_unique(stage.task_ids, task.id)
        stage.updated_at = utc_now()
        return task

    def _recompute_workflow(
        self,
        workflow: ResearchWorkflow,
        *,
        now: str | None = None,
    ) -> ResearchWorkflow:
        current_time = now or utc_now()
        self._ensure_workflow_scaffold(workflow)
        stage = self._workflow_stage(workflow, workflow.current_stage)
        stage_tasks = self._stage_task_list(workflow, workflow.current_stage)
        for task in stage_tasks:
            _append_unique(stage.task_ids, task.id)

        if workflow.status in {"cancelled", "completed"}:
            return workflow

        if workflow.status == "draft":
            workflow.status = "queued"

        if workflow.status == "paused":
            stage.status = "pending"
            return workflow

        if not stage.started_at:
            stage.started_at = current_time

        if not workflow.started_at:
            workflow.started_at = current_time

        if not stage_tasks:
            self._seed_stage_task(workflow)
            stage_tasks = self._stage_task_list(workflow, workflow.current_stage)

        failed = [task for task in stage_tasks if task.status == "failed"]
        blocked = [task for task in stage_tasks if task.status == "blocked"]
        completed = [
            task for task in stage_tasks
            if task.status in {"completed", "cancelled"}
        ]

        if failed:
            workflow.status = "blocked"
            workflow.error = failed[-1].summary or f"Task failed: {failed[-1].title}"
            stage.status = "blocked"
            stage.blocked_reason = workflow.error
            stage.updated_at = current_time
            workflow.last_run_at = current_time
            self._touch(workflow, now=current_time)
            return workflow

        if blocked:
            workflow.status = "blocked"
            workflow.error = blocked[-1].summary or f"Task blocked: {blocked[-1].title}"
            stage.status = "blocked"
            stage.blocked_reason = workflow.error
            stage.updated_at = current_time
            workflow.last_run_at = current_time
            self._touch(workflow, now=current_time)
            return workflow

        if stage_tasks and len(completed) == len(stage_tasks):
            stage.status = "completed"
            stage.completed_at = current_time
            stage.updated_at = current_time
            workflow.last_transition_at = current_time
            current_index = WORKFLOW_STAGES.index(workflow.current_stage)
            if current_index == len(WORKFLOW_STAGES) - 1:
                workflow.status = "completed"
                workflow.completed_at = current_time
                workflow.last_run_at = current_time
                self._touch(workflow, now=current_time)
                return workflow

            next_stage = WORKFLOW_STAGES[current_index + 1]
            workflow.current_stage = next_stage  # type: ignore[assignment]
            workflow.status = "running"
            workflow.error = ""
            next_state = self._workflow_stage(workflow, workflow.current_stage)
            if next_state.status == "pending":
                next_state.status = "running"
            if not next_state.started_at:
                next_state.started_at = current_time
            next_state.updated_at = current_time
            self._seed_stage_task(workflow)
            workflow.last_run_at = current_time
            self._touch(workflow, now=current_time)
            return workflow

        stage.status = "running"
        stage.updated_at = current_time
        workflow.status = "running"
        workflow.error = ""
        workflow.last_run_at = current_time
        self._touch(workflow, now=current_time)
        return workflow

    @staticmethod
    def _note_matches(
        note: ResearchNote,
        *,
        query: str = "",
        note_type: str = "",
        tags: list[str] | None = None,
        project_id: str = "",
        workflow_id: str = "",
        claim_id: str = "",
        experiment_id: str = "",
    ) -> bool:
        if project_id and note.project_id != project_id:
            return False
        if workflow_id and note.workflow_id != workflow_id:
            return False
        if claim_id and claim_id not in note.claim_ids:
            return False
        if experiment_id and experiment_id not in note.experiment_ids:
            return False
        if note_type and note.note_type != note_type:
            return False
        wanted_tags = set(_remove_empty_strings(tags or []))
        if wanted_tags and not wanted_tags.intersection(note.tags):
            return False
        if query:
            haystack = " ".join(
                [
                    note.title,
                    note.content,
                    " ".join(note.tags),
                    " ".join(note.paper_refs),
                    _stringify_metadata(note.metadata),
                ],
            ).lower()
            if query.lower() not in haystack:
                return False
        return True

    @staticmethod
    def _project_binding(
        project: ResearchProject,
        workflow: ResearchWorkflow | None = None,
    ) -> WorkflowBinding:
        if workflow is not None:
            return WorkflowBinding.model_validate(
                workflow.bindings.model_dump(mode="json"),
            )
        return WorkflowBinding.model_validate(
            project.default_binding.model_dump(mode="json"),
        )

    def _add_artifact_to_state(
        self,
        state: ResearchState,
        *,
        project_id: str,
        title: str,
        artifact_type: ArtifactType,
        workflow_id: str = "",
        description: str = "",
        path: str = "",
        uri: str = "",
        source_type: str = "",
        source_id: str = "",
        experiment_id: str = "",
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchArtifact:
        artifact = ResearchArtifact(
            project_id=project_id,
            workflow_id=workflow_id,
            title=title,
            artifact_type=artifact_type,
            description=description,
            path=path,
            uri=uri,
            source_type=source_type,
            source_id=source_id,
            experiment_id=experiment_id,
            note_ids=_remove_empty_strings(note_ids or []),
            claim_ids=_remove_empty_strings(claim_ids or []),
            metadata=dict(metadata or {}),
        )
        state.artifacts.append(artifact)

        project = self._project(state, project_id)
        _append_unique(project.artifact_ids, artifact.id)
        self._touch(project)

        if workflow_id:
            workflow = self._workflow(state, workflow_id)
            _append_unique(workflow.artifact_ids, artifact.id)
            stage = self._workflow_stage(workflow, workflow.current_stage)
            _append_unique(stage.artifact_ids, artifact.id)
            self._touch(workflow)
            stage.updated_at = utc_now()

        if experiment_id:
            experiment = self._experiment(state, experiment_id)
            _append_unique(experiment.artifact_ids, artifact.id)

        for note_id in artifact.note_ids:
            note = self._note(state, note_id)
            _append_unique(note.artifact_ids, artifact.id)
            self._touch(note)

        for claim_id in artifact.claim_ids:
            claim = self._claim(state, claim_id)
            _append_unique(claim.artifact_ids, artifact.id)
            self._touch(claim)

        return artifact

    def _add_evidence_to_state(
        self,
        state: ResearchState,
        *,
        project_id: str,
        evidence_type: EvidenceType,
        summary: str,
        claim_ids: list[str],
        source: EvidenceSource,
        workflow_id: str = "",
        artifact_id: str = "",
        note_id: str = "",
        experiment_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ResearchEvidence:
        evidence = ResearchEvidence(
            project_id=project_id,
            evidence_type=evidence_type,
            summary=summary,
            claim_ids=_remove_empty_strings(claim_ids),
            workflow_id=workflow_id,
            artifact_id=artifact_id,
            note_id=note_id,
            experiment_id=experiment_id,
            source=source,
            metadata=dict(metadata or {}),
        )
        state.evidences.append(evidence)

        for claim_id in evidence.claim_ids:
            claim = self._claim(state, claim_id)
            _append_unique(claim.evidence_ids, evidence.id)
            self._touch(claim)

        if artifact_id:
            artifact = self._artifact(state, artifact_id)
            _append_unique(artifact.evidence_ids, evidence.id)
            self._touch(artifact)

        if note_id:
            note = self._note(state, note_id)
            _append_unique(note.evidence_ids, evidence.id)
            self._touch(note)

        if experiment_id:
            experiment = self._experiment(state, experiment_id)
            _append_unique(experiment.evidence_ids, evidence.id)
            self._touch(experiment)

        return evidence

    def _add_experiment_event_to_state(
        self,
        state: ResearchState,
        *,
        experiment: ExperimentRun,
        event_type: str,
        summary: str,
        status: str = "",
        metrics: dict[str, Any] | None = None,
        output_files: list[str] | None = None,
        note_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentEvent:
        event = ExperimentEvent(
            experiment_id=experiment.id,
            project_id=experiment.project_id,
            workflow_id=experiment.workflow_id,
            event_type=event_type,  # type: ignore[arg-type]
            summary=summary,
            status=status or experiment.status,
            metrics=dict(metrics or {}),
            output_files=_remove_empty_strings(output_files or []),
            note_ids=_remove_empty_strings(note_ids or []),
            artifact_ids=_remove_empty_strings(artifact_ids or []),
            metadata=dict(metadata or {}),
        )
        state.experiment_events.append(event)
        return event

    def _project_recent_items(
        self,
        items: list[Any],
        ids: list[str],
        *,
        limit: int = 5,
    ) -> list[Any]:
        wanted = set(ids)
        filtered = [item for item in items if getattr(item, "id", "") in wanted]
        filtered.sort(
            key=lambda item: str(getattr(item, "updated_at", "") or getattr(item, "created_at", "")),
            reverse=True,
        )
        return filtered[:limit]

    # ---- project APIs ----

    async def list_projects(self) -> list[ResearchProject]:
        state = await self.load_state()
        return list(state.projects)

    async def create_project(
        self,
        *,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
        default_binding: dict[str, Any] | None = None,
        execution_catalog: list[dict[str, Any]] | None = None,
        result_bundle_schemas: list[dict[str, Any]] | None = None,
        default_experiment_runner: dict[str, Any] | None = None,
        paper_watches: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchProject:
        state = await self.load_state()
        project = ResearchProject(
            name=name,
            description=description,
            tags=_remove_empty_strings(tags or []),
            default_binding=self._merge_binding(
                base=WorkflowBinding(),
                patch=default_binding,
            ),
            execution_catalog=self._merge_execution_catalog(
                base=[],
                patch=execution_catalog,
            ),
            result_bundle_schemas=self._merge_result_bundle_schemas(
                base=[],
                patch=result_bundle_schemas,
            ),
            default_experiment_runner=self._merge_runner_profile(
                base=ExperimentRunnerProfile(),
                patch=default_experiment_runner,
            ),
            paper_watches=[
                ProjectPaperWatch.model_validate(item)
                for item in (paper_watches or [])
            ],
            metadata=dict(metadata or {}),
        )
        state.projects.append(project)
        self._record_audit_event(
            state,
            entity_type="project",
            entity_id=project.id,
            action="create",
            project_id=project.id,
            summary=f"Created project '{project.name}'.",
            after=self._model_payload(project),
        )
        await self.save_state(state)
        return project

    async def get_project(self, project_id: str) -> ResearchProject:
        state = await self.load_state()
        return self._project(state, project_id)

    async def get_project_result_bundle_schema(
        self,
        *,
        project_id: str,
        schema_name: str,
    ) -> ResultBundleSchemaDefinition | None:
        state = await self.load_state()
        return self._project_result_bundle_schema(
            state,
            project_id=project_id,
            schema_name=schema_name,
        )

    async def update_project(
        self,
        *,
        project_id: str,
        description: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        default_binding: dict[str, Any] | None = None,
        execution_catalog: list[dict[str, Any]] | None = None,
        result_bundle_schemas: list[dict[str, Any]] | None = None,
        default_experiment_runner: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchProject:
        state = await self.load_state()
        project = self._project(state, project_id)
        before = self._model_payload(project)
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status  # type: ignore[assignment]
        if tags is not None:
            project.tags = _remove_empty_strings(tags)
        if default_binding:
            project.default_binding = self._merge_binding(
                base=project.default_binding,
                patch=default_binding,
            )
        if execution_catalog is not None:
            project.execution_catalog = self._merge_execution_catalog(
                base=project.execution_catalog,
                patch=execution_catalog,
            )
        if result_bundle_schemas is not None:
            project.result_bundle_schemas = self._merge_result_bundle_schemas(
                base=project.result_bundle_schemas,
                patch=result_bundle_schemas,
            )
        if default_experiment_runner is not None:
            project.default_experiment_runner = self._merge_runner_profile(
                base=project.default_experiment_runner,
                patch=default_experiment_runner,
            )
        if metadata:
            merged_metadata = dict(project.metadata)
            merged_metadata.update(dict(metadata))
            project.metadata = merged_metadata
        self._touch(project)
        self._record_audit_event(
            state,
            entity_type="project",
            entity_id=project.id,
            action="update",
            project_id=project.id,
            summary=f"Updated project '{project.name}'.",
            before=before,
            after=self._model_payload(project),
        )
        await self.save_state(state)
        return project

    async def add_project_paper_watch(
        self,
        *,
        project_id: str,
        query: str,
        source: str = "arxiv",
        max_results: int = 5,
        check_every_hours: int = 12,
    ) -> ResearchProject:
        state = await self.load_state()
        project = self._project(state, project_id)
        before = self._model_payload(project)
        watch = ProjectPaperWatch(
            query=query,
            source="semantic_scholar" if source == "semantic_scholar" else "arxiv",
            max_results=max(1, min(int(max_results), 20)),
            check_every_hours=max(1, int(check_every_hours)),
        )
        project.paper_watches.append(watch)
        self._touch(project)
        self._record_audit_event(
            state,
            entity_type="project",
            entity_id=project.id,
            action="paper_watch_add",
            project_id=project.id,
            summary=f"Added paper watch '{watch.query}' to project '{project.name}'.",
            before=before,
            after=self._model_payload(project),
            metadata={"watch_id": watch.id},
        )
        await self.save_state(state)
        return project

    @staticmethod
    def _experiment_bundle_validation_state(
        experiment: ExperimentRun,
    ) -> dict[str, Any]:
        bundle_validation = dict(
            dict(getattr(experiment, "metadata", {}) or {}).get(
                "result_bundle_validation",
                {},
            )
            or {},
        )
        schema_name = str(
            bundle_validation.get("schema_name")
            or getattr(experiment.execution, "result_bundle_schema", "")
            or "",
        ).strip()
        if bundle_validation.get("enabled"):
            if bundle_validation.get("passed", False):
                state = "passed"
                summary = "Result bundle validation passed."
            elif bundle_validation.get("schema_found") is False:
                state = "schema_missing"
                summary = "Configured result bundle schema could not be found."
            else:
                state = "failed"
                summary = "Result bundle validation failed."
            return {
                "enabled": True,
                "state": state,
                "passed": bool(bundle_validation.get("passed", False)),
                "schema_name": schema_name,
                "schema_found": bundle_validation.get("schema_found"),
                "missing_sections": _remove_empty_strings(
                    bundle_validation.get("missing_sections", []),
                ),
                "missing_metrics": _remove_empty_strings(
                    bundle_validation.get("missing_metrics", []),
                ),
                "missing_outputs": _remove_empty_strings(
                    bundle_validation.get("missing_outputs", []),
                ),
                "missing_artifact_types": _remove_empty_strings(
                    bundle_validation.get("missing_artifact_types", []),
                ),
                "summary": summary,
            }
        if schema_name:
            return {
                "enabled": False,
                "state": "pending",
                "passed": False,
                "schema_name": schema_name,
                "schema_found": None,
                "missing_sections": [],
                "missing_metrics": [],
                "missing_outputs": [],
                "missing_artifact_types": [],
                "summary": "Result bundle schema configured but validation is still pending.",
            }
        return {
            "enabled": False,
            "state": "not_configured",
            "passed": False,
            "schema_name": "",
            "schema_found": None,
            "missing_sections": [],
            "missing_metrics": [],
            "missing_outputs": [],
            "missing_artifact_types": [],
            "summary": "No result bundle schema configured.",
        }

    async def get_project_closure_report(self, project_id: str) -> dict[str, Any]:
        state = await self.load_state()
        project = self._project(state, project_id)
        workflow_ids = set(project.workflow_ids)
        claim_ids = set(project.claim_ids)
        experiment_ids = set(project.experiment_ids)
        artifact_ids = set(project.artifact_ids)

        workflows = [item for item in state.workflows if item.id in workflow_ids]
        claims = [item for item in state.claims if item.id in claim_ids]
        evidences = [item for item in state.evidences if item.project_id == project_id]
        experiments = [item for item in state.experiments if item.id in experiment_ids]
        artifacts = [item for item in state.artifacts if item.id in artifact_ids]

        workflow_status: dict[str, int] = {}
        for workflow in workflows:
            key = str(workflow.status or "").strip() or "unknown"
            workflow_status[key] = workflow_status.get(key, 0) + 1

        artifact_coverage: dict[str, int] = {}
        for artifact in artifacts:
            key = str(artifact.artifact_type or "").strip() or "unknown"
            artifact_coverage[key] = artifact_coverage.get(key, 0) + 1

        experiments_by_id = {item.id: item for item in experiments}
        artifacts_by_id = {item.id: item for item in artifacts}
        severity_rank = {"high": 0, "medium": 1, "low": 2}

        action_items: list[dict[str, Any]] = []
        claim_rows: list[dict[str, Any]] = []
        supported_claim_count = 0
        claims_with_evidence_count = 0
        ready_for_writing_claim_count = 0
        ready_for_submission_claim_count = 0

        for claim in sorted(
            claims,
            key=lambda item: item.updated_at or item.created_at,
            reverse=True,
        ):
            claim_evidences = [
                item
                for item in evidences
                if claim.id in set(item.claim_ids) or item.id in set(claim.evidence_ids)
            ]
            claim_evidences.sort(
                key=lambda item: item.updated_at or item.created_at,
                reverse=True,
            )
            evidence_types = sorted(
                {str(item.evidence_type) for item in claim_evidences if item.evidence_type},
            )

            related_experiment_ids = {
                run.id for run in experiments if claim.id in set(run.claim_ids)
            }
            related_experiment_ids.update(
                item.experiment_id for item in claim_evidences if item.experiment_id
            )
            related_experiments = [
                experiments_by_id[run_id]
                for run_id in related_experiment_ids
                if run_id in experiments_by_id
            ]
            completed_experiments = [
                item for item in related_experiments if item.status == "completed"
            ]

            related_artifact_ids = set(claim.artifact_ids)
            related_artifact_ids.update(
                item.artifact_id for item in claim_evidences if item.artifact_id
            )
            related_artifacts = [
                artifacts_by_id[artifact_id]
                for artifact_id in related_artifact_ids
                if artifact_id in artifacts_by_id
            ]
            artifact_types = sorted(
                {str(item.artifact_type) for item in related_artifacts if item.artifact_type},
            )

            has_strong_evidence = any(
                evidence_type
                in {
                    "paper",
                    "pdf_chunk",
                    "citation",
                    "experiment_result",
                    "generated_table",
                    "generated_figure",
                    "artifact",
                }
                for evidence_type in evidence_types
            )
            has_writing_artifact = any(
                item.artifact_type in {"analysis", "summary", "draft"}
                for item in related_artifacts
            )
            ready_for_writing = (
                claim.status == "supported"
                and bool(claim_evidences)
                and (has_strong_evidence or bool(completed_experiments))
            )
            ready_for_submission = ready_for_writing and has_writing_artifact

            gaps: list[str] = []
            if not claim_evidences:
                gaps.append("missing_evidence")
                action_items.append(
                    {
                        "severity": "high",
                        "kind": "claim_evidence_gap",
                        "title": f"Attach evidence to claim '{claim.text[:72]}'",
                        "summary": "The claim does not have any linked evidence yet.",
                        "target_type": "claim",
                        "target_id": claim.id,
                        "claim_id": claim.id,
                        "workflow_id": claim.workflow_id,
                    },
                )
            if claim.status != "supported":
                gaps.append(f"claim_status:{claim.status}")
                action_items.append(
                    {
                        "severity": "medium",
                        "kind": "claim_review",
                        "title": f"Review claim status for '{claim.text[:72]}'",
                        "summary": (
                            f"Claim status is '{claim.status}'. Promote, revise, or dispute it "
                            "before final writing."
                        ),
                        "target_type": "claim",
                        "target_id": claim.id,
                        "claim_id": claim.id,
                        "workflow_id": claim.workflow_id,
                    },
                )
            if claim_evidences and not has_strong_evidence and not completed_experiments:
                gaps.append("weak_evidence_mix")
                action_items.append(
                    {
                        "severity": "medium",
                        "kind": "claim_rigor_gap",
                        "title": f"Strengthen evidence for claim '{claim.text[:72]}'",
                        "summary": (
                            "The claim is only backed by lightweight notes. Add paper, figure, "
                            "table, or experiment evidence."
                        ),
                        "target_type": "claim",
                        "target_id": claim.id,
                        "claim_id": claim.id,
                        "workflow_id": claim.workflow_id,
                    },
                )
            if claim.status == "supported" and not has_writing_artifact:
                gaps.append("missing_writing_artifact")
                action_items.append(
                    {
                        "severity": "medium",
                        "kind": "claim_writing_gap",
                        "title": f"Write analysis for claim '{claim.text[:72]}'",
                        "summary": (
                            "The claim is supported, but there is no linked analysis, summary, "
                            "or draft artifact yet."
                        ),
                        "target_type": "claim",
                        "target_id": claim.id,
                        "claim_id": claim.id,
                        "workflow_id": claim.workflow_id,
                    },
                )

            if claim.status == "supported":
                supported_claim_count += 1
            if claim_evidences:
                claims_with_evidence_count += 1
            if ready_for_writing:
                ready_for_writing_claim_count += 1
            if ready_for_submission:
                ready_for_submission_claim_count += 1

            claim_rows.append(
                {
                    "claim_id": claim.id,
                    "workflow_id": claim.workflow_id,
                    "text": claim.text,
                    "status": claim.status,
                    "confidence": claim.confidence,
                    "evidence_count": len(claim_evidences),
                    "evidence_types": evidence_types,
                    "experiment_count": len(related_experiments),
                    "completed_experiment_count": len(completed_experiments),
                    "artifact_count": len(related_artifacts),
                    "artifact_types": artifact_types,
                    "ready_for_writing": ready_for_writing,
                    "ready_for_submission": ready_for_submission,
                    "gaps": gaps,
                    "updated_at": claim.updated_at,
                },
            )

        experiment_rows: list[dict[str, Any]] = []
        completed_experiment_count = 0
        reproducibility_ready_count = 0
        contract_failed_count = 0
        bundle_failed_count = 0

        for experiment in sorted(
            experiments,
            key=lambda item: item.finished_at or item.started_at or item.created_at,
            reverse=True,
        ):
            contract_validation = self._evaluate_experiment_artifact_contract(
                state,
                experiment,
            )
            bundle_validation = self._experiment_bundle_validation_state(experiment)
            reproducibility_ready = (
                experiment.status == "completed"
                and (
                    not contract_validation.get("enabled")
                    or contract_validation.get("passed", False)
                )
                and bundle_validation.get("state") in {"passed", "not_configured"}
            )

            gaps: list[str] = []
            if experiment.status == "completed":
                completed_experiment_count += 1
            else:
                gaps.append(f"status:{experiment.status}")
                if experiment.status in {"failed", "cancelled"}:
                    action_items.append(
                        {
                            "severity": "high",
                            "kind": "experiment_status",
                            "title": f"Recover experiment '{experiment.name}'",
                            "summary": (
                                f"Experiment is in status '{experiment.status}' and cannot "
                                "contribute to the final project loop yet."
                            ),
                            "target_type": "experiment",
                            "target_id": experiment.id,
                            "experiment_id": experiment.id,
                            "workflow_id": experiment.workflow_id,
                        },
                    )
            if contract_validation.get("enabled") and not contract_validation.get(
                "passed",
                False,
            ):
                gaps.append("artifact_contract_failed")
                contract_failed_count += 1
                action_items.append(
                    {
                        "severity": "high",
                        "kind": "experiment_contract",
                        "title": f"Resolve artifact contract for '{experiment.name}'",
                        "summary": str(contract_validation.get("summary") or "").strip(),
                        "target_type": "experiment",
                        "target_id": experiment.id,
                        "experiment_id": experiment.id,
                        "workflow_id": experiment.workflow_id,
                    },
                )
            bundle_state = str(bundle_validation.get("state") or "").strip()
            if bundle_state in {"failed", "schema_missing"}:
                gaps.append(f"result_bundle:{bundle_state}")
                bundle_failed_count += 1
                action_items.append(
                    {
                        "severity": "high" if bundle_state == "failed" else "medium",
                        "kind": "result_bundle",
                        "title": f"Fix result bundle for '{experiment.name}'",
                        "summary": str(bundle_validation.get("summary") or "").strip(),
                        "target_type": "experiment",
                        "target_id": experiment.id,
                        "experiment_id": experiment.id,
                        "workflow_id": experiment.workflow_id,
                    },
                )
            elif bundle_state == "pending":
                gaps.append("result_bundle:pending")
                action_items.append(
                    {
                        "severity": "medium",
                        "kind": "result_bundle_pending",
                        "title": f"Validate result bundle for '{experiment.name}'",
                        "summary": str(bundle_validation.get("summary") or "").strip(),
                        "target_type": "experiment",
                        "target_id": experiment.id,
                        "experiment_id": experiment.id,
                        "workflow_id": experiment.workflow_id,
                    },
                )
            if reproducibility_ready:
                reproducibility_ready_count += 1

            experiment_rows.append(
                {
                    "experiment_id": experiment.id,
                    "workflow_id": experiment.workflow_id,
                    "name": experiment.name,
                    "status": experiment.status,
                    "claim_count": len(experiment.claim_ids),
                    "artifact_count": len(experiment.artifact_ids),
                    "contract_enabled": bool(contract_validation.get("enabled")),
                    "contract_passed": bool(contract_validation.get("passed", False)),
                    "bundle_state": bundle_state,
                    "bundle_schema": str(bundle_validation.get("schema_name") or ""),
                    "reproducibility_ready": reproducibility_ready,
                    "missing_metrics": list(contract_validation.get("missing_metrics", [])),
                    "missing_outputs": list(contract_validation.get("missing_outputs", [])),
                    "missing_artifact_types": list(
                        contract_validation.get("missing_artifact_types", []),
                    ),
                    "bundle_missing_sections": list(
                        bundle_validation.get("missing_sections", []),
                    ),
                    "gaps": gaps,
                    "updated_at": experiment.finished_at
                    or experiment.started_at
                    or experiment.created_at,
                },
            )

        for workflow in workflows:
            if workflow.status != "blocked":
                continue
            action_items.append(
                {
                    "severity": "high",
                    "kind": "workflow_blocker",
                    "title": f"Unblock workflow '{workflow.title}'",
                    "summary": str(workflow.error or "Workflow is blocked.").strip(),
                    "target_type": "workflow",
                    "target_id": workflow.id,
                    "workflow_id": workflow.id,
                },
            )

        expected_artifact_types: list[str] = []
        if supported_claim_count or completed_experiment_count:
            expected_artifact_types.append("analysis")
        if supported_claim_count:
            expected_artifact_types.append("summary")
        if ready_for_writing_claim_count:
            expected_artifact_types.append("draft")
        missing_expected_artifact_types = [
            artifact_type
            for artifact_type in expected_artifact_types
            if artifact_coverage.get(artifact_type, 0) <= 0
        ]
        for artifact_type in missing_expected_artifact_types:
            action_items.append(
                {
                    "severity": "medium",
                    "kind": "project_artifact_gap",
                    "artifact_type": artifact_type,
                    "title": f"Create a project-level {artifact_type} artifact",
                    "summary": (
                        f"No '{artifact_type}' artifact is currently attached to this project, "
                        "which keeps the research loop from closing cleanly."
                    ),
                    "target_type": "project",
                    "target_id": project.id,
                },
            )

        action_items = [
            self._closure_action_enrich(item)
            for item in action_items
        ]

        action_items.sort(
            key=lambda item: (
                severity_rank.get(str(item.get("severity", "medium")), 99),
                str(item.get("title", "")),
            ),
        )

        readiness_checks = [
            supported_claim_count > 0,
            bool(claims) and claims_with_evidence_count == len(claims),
            completed_experiment_count > 0,
            contract_failed_count == 0,
            reproducibility_ready_count == completed_experiment_count
            if completed_experiment_count
            else False,
            artifact_coverage.get("analysis", 0) > 0 or artifact_coverage.get("summary", 0) > 0,
            artifact_coverage.get("draft", 0) > 0,
        ]
        completion_score = int(
            round(
                (sum(1 for item in readiness_checks if item) / len(readiness_checks))
                * 100,
            ),
        )
        ready_for_writing = (
            supported_claim_count > 0
            and ready_for_writing_claim_count >= supported_claim_count
            and (
                artifact_coverage.get("analysis", 0) > 0
                or artifact_coverage.get("summary", 0) > 0
            )
        )
        ready_for_submission = (
            ready_for_writing
            and completed_experiment_count > 0
            and contract_failed_count == 0
            and artifact_coverage.get("draft", 0) > 0
        )
        ready_for_reproducibility = (
            completed_experiment_count > 0
            and reproducibility_ready_count == completed_experiment_count
        )
        blocking_issue_count = sum(
            1 for item in action_items if item.get("severity") == "high"
        )
        warning_issue_count = sum(
            1 for item in action_items if item.get("severity") == "medium"
        )
        overall_status = "ready"
        if not (ready_for_submission and ready_for_reproducibility):
            overall_status = "blocked" if blocking_issue_count else "in_progress"

        return {
            "project": project,
            "readiness": {
                "overall_status": overall_status,
                "completion_score": completion_score,
                "ready_for_writing": ready_for_writing,
                "ready_for_submission": ready_for_submission,
                "ready_for_reproducibility": ready_for_reproducibility,
                "blocking_issue_count": blocking_issue_count,
                "warning_issue_count": warning_issue_count,
            },
            "summary": {
                "claims": len(claims),
                "supported_claims": supported_claim_count,
                "claims_with_evidence": claims_with_evidence_count,
                "ready_for_writing_claims": ready_for_writing_claim_count,
                "ready_for_submission_claims": ready_for_submission_claim_count,
                "experiments": len(experiments),
                "completed_experiments": completed_experiment_count,
                "reproducibility_ready_experiments": reproducibility_ready_count,
                "contract_failed_experiments": contract_failed_count,
                "bundle_failed_experiments": bundle_failed_count,
                "drafts": artifact_coverage.get("draft", 0),
                "analysis_artifacts": artifact_coverage.get("analysis", 0),
                "summary_artifacts": artifact_coverage.get("summary", 0),
            },
            "workflow_status": workflow_status,
            "artifact_coverage": {
                "by_type": dict(sorted(artifact_coverage.items())),
                "missing_expected_types": missing_expected_artifact_types,
            },
            "claim_matrix": claim_rows,
            "experiment_matrix": experiment_rows,
            "action_items": action_items[:20],
        }

    async def list_project_closure_actions(
        self,
        project_id: str,
        *,
        kind: str = "",
        severity: str = "",
        target_type: str = "",
        workflow_id: str = "",
        auto_executable: bool | None = None,
        materializable: bool | None = None,
        query: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        report = await self.get_project_closure_report(project_id)
        actions = list(report.get("action_items", []) or [])
        if kind:
            actions = [
                item for item in actions if str(item.get("kind", "") or "") == kind
            ]
        if severity:
            actions = [
                item
                for item in actions
                if str(item.get("severity", "") or "") == severity
            ]
        if target_type:
            actions = [
                item
                for item in actions
                if str(item.get("target_type", "") or "") == target_type
            ]
        if workflow_id:
            actions = [
                item
                for item in actions
                if str(item.get("workflow_id", "") or "") == workflow_id
            ]
        if auto_executable is not None:
            actions = [
                item
                for item in actions
                if bool(item.get("auto_executable")) is bool(auto_executable)
            ]
        if materializable is not None:
            actions = [
                item
                for item in actions
                if bool(item.get("materializable")) is bool(materializable)
            ]
        if query:
            query_text = str(query).strip().lower()
            actions = [
                item
                for item in actions
                if query_text in str(item.get("title", "") or "").lower()
                or query_text in str(item.get("summary", "") or "").lower()
                or query_text in str(item.get("kind", "") or "").lower()
                or query_text in str(item.get("target_id", "") or "").lower()
            ]
        return actions[: max(1, int(limit))]

    @staticmethod
    def _slugify(text: str, *, fallback: str = "item") -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", str(text or "").strip()).strip("-")
        return normalized.lower() or fallback

    def _storage_root(self) -> Path:
        base = self.path.parent
        if base.name == "research":
            return base.parent
        return base

    def _storage_dir(self, *parts: str) -> Path:
        path = self._storage_root().joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _closure_action_key(action: dict[str, Any]) -> str:
        return (
            f"{str(action.get('kind', '') or '').strip()}:"
            f"{str(action.get('target_id', '') or '').strip()}"
        )

    @staticmethod
    def _closure_action_ref_from_key(closure_key: str) -> tuple[str, str] | None:
        text = str(closure_key or "").strip()
        if not text or ":" not in text:
            return None
        action_kind, target_id = text.split(":", 1)
        action_kind = action_kind.strip()
        target_id = target_id.strip()
        if not action_kind or not target_id:
            return None
        return action_kind, target_id

    @staticmethod
    def _closure_action_stage(action: dict[str, Any]) -> str:
        kind = str(action.get("kind", "") or "").strip()
        if kind in {"experiment_contract", "result_bundle", "result_bundle_pending", "experiment_status"}:
            return "experiment_run"
        if kind in {"claim_writing_gap", "project_artifact_gap"}:
            return "writing_tasks"
        if kind == "workflow_blocker":
            return "review_and_followup"
        return "result_analysis"

    @staticmethod
    def _closure_action_assignee(action: dict[str, Any]) -> str:
        if bool(action.get("auto_executable")):
            return "agent"
        kind = str(action.get("kind", "") or "").strip()
        if kind in {"claim_review", "claim_evidence_gap", "claim_rigor_gap"}:
            return "analyst"
        return "agent"

    @staticmethod
    def _closure_action_suggested_tool(action: dict[str, Any]) -> str:
        kind = str(action.get("kind", "") or "").strip()
        if kind == "claim_writing_gap":
            return "research_artifact_upsert"
        if kind == "project_artifact_gap":
            return "research_artifact_upsert"
        if kind in {"claim_evidence_gap", "claim_rigor_gap"}:
            return "research_claim_attach_evidence"
        if kind == "claim_review":
            return "research_claim_update"
        if kind in {"experiment_contract", "experiment_status", "result_bundle", "result_bundle_pending"}:
            return "research_experiment_update"
        if kind == "workflow_blocker":
            return "research_workflow_update_task"
        return ""

    @staticmethod
    def _closure_action_auto_executable(action: dict[str, Any]) -> bool:
        return str(action.get("kind", "") or "").strip() in {
            "claim_writing_gap",
            "project_artifact_gap",
        }

    @staticmethod
    def _closure_action_materializable(action: dict[str, Any]) -> bool:
        return bool(str(action.get("kind", "") or "").strip())

    @staticmethod
    def _closure_action_enrich(action: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(action)
        enriched["closure_key"] = ResearchService._closure_action_key(action)
        enriched["stage"] = ResearchService._closure_action_stage(action)
        enriched["assignee"] = ResearchService._closure_action_assignee(action)
        enriched["suggested_tool"] = ResearchService._closure_action_suggested_tool(action)
        enriched["auto_executable"] = ResearchService._closure_action_auto_executable(action)
        enriched["materializable"] = ResearchService._closure_action_materializable(action)
        return enriched

    @staticmethod
    def _closure_action_by_key(
        report: dict[str, Any],
        *,
        action_kind: str,
        target_id: str,
    ) -> dict[str, Any] | None:
        wanted_key = f"{str(action_kind or '').strip()}:{str(target_id or '').strip()}"
        for action in list(report.get("action_items", []) or []):
            if str(action.get("closure_key", "") or "").strip() == wanted_key:
                return action
        return None

    @staticmethod
    def _resolve_project_workflow(
        state: ResearchState,
        project: ResearchProject,
        *,
        workflow_id: str = "",
    ) -> ResearchWorkflow | None:
        if workflow_id:
            for workflow in state.workflows:
                if workflow.id == workflow_id:
                    return workflow
        candidates = [item for item in state.workflows if item.project_id == project.id]
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (
                1 if item.status in {"running", "blocked", "queued"} else 0,
                str(item.updated_at or item.created_at),
            ),
            reverse=True,
        )
        return candidates[0]

    @staticmethod
    def _closure_action_existing_task(
        workflow: ResearchWorkflow,
        *,
        closure_key: str,
    ) -> WorkflowTask | None:
        for task in workflow.tasks:
            metadata = dict(getattr(task, "metadata", {}) or {})
            if str(metadata.get("closure_key", "") or "").strip() != closure_key:
                continue
            if task.status in {"completed", "cancelled"}:
                continue
            return task
        return None

    @staticmethod
    def _claim_writing_scaffold(
        claim: ResearchClaim,
        *,
        evidences: list[ResearchEvidence],
        experiments: list[ExperimentRun],
    ) -> str:
        evidence_lines = [
            f"- [{item.evidence_type}] {item.summary}"
            for item in evidences[:8]
        ] or ["- TODO: attach concrete evidence for this claim."]
        experiment_lines = [
            (
                f"- {item.name} [{item.status}]"
                + (
                    f" metrics={json.dumps(item.metrics, ensure_ascii=True, sort_keys=True)}"
                    if item.metrics
                    else ""
                )
            )
            for item in experiments[:5]
        ] or ["- No linked experiments yet."]
        return "\n".join(
            [
                f"# Analysis Draft for Claim {claim.id}",
                "",
                "## Claim",
                claim.text,
                "",
                "## Evidence Snapshot",
                *evidence_lines,
                "",
                "## Experiment Snapshot",
                *experiment_lines,
                "",
                "## Interpretation",
                "- What does the current evidence actually support?",
                "- What assumptions or caveats still need to be stated explicitly?",
                "- Which missing comparisons or controls remain?",
                "",
                "## Writing TODO",
                "- Convert the claim into 2-3 result sentences.",
                "- Add precise numbers from the strongest evidence.",
                "- State one limitation or open risk.",
            ],
        ).strip() + "\n"

    @staticmethod
    def _project_artifact_scaffold(
        project: ResearchProject,
        *,
        artifact_type: str,
        closure_report: dict[str, Any],
    ) -> str:
        summary = dict(closure_report.get("summary", {}) or {})
        readiness = dict(closure_report.get("readiness", {}) or {})
        title = f"{project.name} {artifact_type.replace('_', ' ').title()} Scaffold"
        if artifact_type == "draft":
            sections = [
                "# Title",
                "",
                "## Abstract",
                "- Problem:",
                "- Method:",
                "- Result:",
                "- Conclusion:",
                "",
                "## Introduction",
                "",
                "## Method",
                "",
                "## Experiments",
                "",
                "## Results",
                "",
                "## Limitations",
                "",
                "## Reproducibility Checklist",
                f"- Completion score: {readiness.get('completion_score', 0)}%",
                f"- Supported claims: {summary.get('supported_claims', 0)}",
                f"- Completed experiments: {summary.get('completed_experiments', 0)}",
            ]
            return "\n".join([title, "", *sections]).strip() + "\n"
        if artifact_type == "summary":
            lines = [
                f"# {project.name} Project Summary",
                "",
                f"- Supported claims: {summary.get('supported_claims', 0)}",
                f"- Claims with evidence: {summary.get('claims_with_evidence', 0)}",
                f"- Completed experiments: {summary.get('completed_experiments', 0)}",
                f"- Reproducibility-ready experiments: {summary.get('reproducibility_ready_experiments', 0)}",
                "",
                "## Key Findings",
                "- TODO: summarize the strongest validated findings.",
                "",
                "## Remaining Risks",
                "- TODO: describe the biggest open blocker before submission.",
            ]
            return "\n".join(lines).strip() + "\n"
        lines = [
            f"# {project.name} Analysis Overview",
            "",
            "## Closure Snapshot",
            json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True),
            "",
            "## Interpretation",
            "- TODO: connect the evidence graph to the experiment outcomes.",
            "- TODO: identify the strongest narrative thread for the paper.",
            "- TODO: note what still needs reviewer-facing justification.",
        ]
        return "\n".join(lines).strip() + "\n"

    async def materialize_project_closure_actions(
        self,
        project_id: str,
        *,
        limit: int = 5,
        action_kind: str = "",
        target_id: str = "",
    ) -> dict[str, Any]:
        report = await self.get_project_closure_report(project_id)
        state = await self.load_state()
        project = self._project(state, project_id)
        actions = list(report.get("action_items", []) or [])
        if action_kind and target_id:
            action = self._closure_action_by_key(
                report,
                action_kind=action_kind,
                target_id=target_id,
            )
            actions = [action] if action else []
        created_tasks: list[WorkflowTask] = []
        skipped: list[dict[str, Any]] = []
        changed = False

        for action in actions[: max(1, int(limit))]:
            if not isinstance(action, dict):
                continue
            if not bool(action.get("materializable")):
                skipped.append(
                    {
                        "action": action,
                        "reason": "action is not materializable",
                    },
                )
                continue
            workflow = self._resolve_project_workflow(
                state,
                project,
                workflow_id=str(action.get("workflow_id", "") or ""),
            )
            if workflow is None:
                skipped.append(
                    {
                        "action": action,
                        "reason": "project has no workflow to attach the follow-up task",
                    },
                )
                continue
            closure_key = str(action.get("closure_key", "") or "").strip()
            existing = self._closure_action_existing_task(
                workflow,
                closure_key=closure_key,
            )
            if existing is not None:
                skipped.append(
                    {
                        "action": action,
                        "reason": f"task already exists: {existing.id}",
                        "task": existing.model_dump(mode="json"),
                    },
                )
                continue
            stage_name = str(action.get("stage", workflow.current_stage) or workflow.current_stage)
            task = WorkflowTask(
                stage=stage_name,  # type: ignore[arg-type]
                title=str(action.get("title", "Project closure follow-up") or "Project closure follow-up"),
                description=str(action.get("summary", "") or ""),
                assignee=str(action.get("assignee", "agent") or "agent"),
                metadata={
                    "task_kind": "project_closure_followup",
                    "closure_key": closure_key,
                    "closure_kind": str(action.get("kind", "") or ""),
                    "closure_target_id": str(action.get("target_id", "") or ""),
                    "suggested_tool": str(action.get("suggested_tool", "") or ""),
                    "auto_executable": bool(action.get("auto_executable", False)),
                    "action_snapshot": dict(action),
                },
            )
            workflow.tasks.append(task)
            stage_state = self._workflow_stage(workflow, task.stage)
            _append_unique(stage_state.task_ids, task.id)
            stage_state.updated_at = utc_now()
            self._touch(workflow)
            created_tasks.append(task)
            changed = True

        if changed:
            await self.save_state(state)
        return {
            "project": project.model_dump(mode="json"),
            "created_count": len(created_tasks),
            "skipped_count": len(skipped),
            "tasks": [task.model_dump(mode="json") for task in created_tasks],
            "skipped": skipped,
            "closure": await self.get_project_closure_report(project_id),
        }

    async def execute_project_closure_action(
        self,
        project_id: str,
        *,
        action_kind: str,
        target_id: str,
    ) -> dict[str, Any]:
        report = await self.get_project_closure_report(project_id)
        action = self._closure_action_by_key(
            report,
            action_kind=action_kind,
            target_id=target_id,
        )
        if action is None:
            raise ValueError(
                f"Unknown closure action: {action_kind}:{target_id}",
            )
        if not bool(action.get("auto_executable")):
            materialized = await self.materialize_project_closure_actions(
                project_id,
                limit=1,
                action_kind=action_kind,
                target_id=target_id,
            )
            return {
                "executed": False,
                "materialized": materialized.get("created_count", 0) > 0,
                "reason": "Action requires a follow-up task instead of direct auto execution.",
                "closure_action": action,
                "materialize_result": materialized,
                "closure": await self.get_project_closure_report(project_id),
            }

        state = await self.load_state()
        project = self._project(state, project_id)
        kind = str(action.get("kind", "") or "").strip()
        workflow = self._resolve_project_workflow(
            state,
            project,
            workflow_id=str(action.get("workflow_id", "") or ""),
        )
        artifact = None
        note = None
        written_path = Path()

        if kind == "claim_writing_gap":
            claim = self._claim(state, target_id)
            evidences = [
                item for item in state.evidences if claim.id in set(item.claim_ids)
            ]
            experiments = [
                item for item in state.experiments if claim.id in set(item.claim_ids)
            ]
            drafts_dir = self._storage_dir("drafts", project.id)
            written_path = drafts_dir / f"claim-{claim.id}-analysis.md"
            written_path.write_text(
                self._claim_writing_scaffold(
                    claim,
                    evidences=evidences,
                    experiments=experiments,
                ),
                encoding="utf-8",
            )
            artifact = await self.upsert_artifact(
                project_id=project.id,
                workflow_id=claim.workflow_id,
                title=f"Claim analysis · {claim.text[:60]}",
                artifact_type="analysis",
                description="Auto-generated analysis scaffold from the project closure report.",
                path=str(written_path),
                source_type="closure_action",
                source_id=self._closure_action_key(action),
                claim_ids=[claim.id],
                metadata={
                    "auto_generated": True,
                    "closure_action": action,
                },
            )
            note = await self.create_note(
                project_id=project.id,
                workflow_id=claim.workflow_id,
                title=f"Claim writing scaffold · {claim.id}",
                content=(
                    f"Generated analysis scaffold for claim '{claim.text}'.\n\n"
                    f"Path: {written_path}"
                ),
                note_type="writing_note",
                claim_ids=[claim.id],
                artifact_ids=[artifact.id],
                tags=["closure", "auto-generated", "analysis"],
                metadata={
                    "closure_action": action,
                },
            )
        elif kind == "project_artifact_gap":
            artifact_type = str(action.get("artifact_type", "") or "").strip() or "draft"
            drafts_dir = self._storage_dir("drafts", project.id)
            written_path = drafts_dir / f"project-{project.id}-{artifact_type}.md"
            written_path.write_text(
                self._project_artifact_scaffold(
                    project,
                    artifact_type=artifact_type,
                    closure_report=report,
                ),
                encoding="utf-8",
            )
            artifact = await self.upsert_artifact(
                project_id=project.id,
                workflow_id=getattr(workflow, "id", ""),
                title=f"{project.name} {artifact_type} scaffold",
                artifact_type=artifact_type,
                description="Auto-generated scaffold from the project closure report.",
                path=str(written_path),
                source_type="closure_action",
                source_id=self._closure_action_key(action),
                metadata={
                    "auto_generated": True,
                    "closure_action": action,
                },
            )
            note = await self.create_note(
                project_id=project.id,
                workflow_id=getattr(workflow, "id", ""),
                title=f"Project {artifact_type} scaffold",
                content=(
                    f"Generated a project-level {artifact_type} scaffold to close the loop.\n\n"
                    f"Path: {written_path}"
                ),
                note_type="writing_note",
                artifact_ids=[artifact.id],
                tags=["closure", "auto-generated", artifact_type],
                metadata={
                    "closure_action": action,
                },
            )
        else:
            raise ValueError(f"Action '{kind}' is not auto executable.")

        return {
            "executed": True,
            "materialized": False,
            "reason": f"Auto-executed closure action {self._closure_action_key(action)}.",
            "closure_action": action,
            "artifact": artifact.model_dump(mode="json") if artifact is not None else None,
            "note": note.model_dump(mode="json") if note is not None else None,
            "written_path": str(written_path),
            "closure": await self.get_project_closure_report(project_id),
        }

    async def apply_project_closure_actions(
        self,
        project_id: str,
        *,
        closure_keys: list[str],
        mode: str = "execute",
    ) -> dict[str, Any]:
        cleaned_keys = _remove_empty_strings(closure_keys)
        if not cleaned_keys:
            raise ValueError("No closure action keys provided.")
        normalized_mode = str(mode or "execute").strip() or "execute"
        if normalized_mode not in {"execute", "materialize"}:
            raise ValueError("Closure action batch mode must be 'execute' or 'materialize'.")

        results: list[dict[str, Any]] = []
        executed_count = 0
        materialized_count = 0
        skipped_count = 0

        for closure_key in cleaned_keys:
            ref = self._closure_action_ref_from_key(closure_key)
            if ref is None:
                skipped_count += 1
                results.append(
                    {
                        "closure_key": closure_key,
                        "executed": False,
                        "materialized": False,
                        "skipped": True,
                        "reason": "Invalid closure action key.",
                    },
                )
                continue
            action_kind, target_id = ref
            if normalized_mode == "materialize":
                result = await self.materialize_project_closure_actions(
                    project_id,
                    limit=1,
                    action_kind=action_kind,
                    target_id=target_id,
                )
                created_count = int(result.get("created_count", 0) or 0)
                skipped_here = created_count <= 0
                materialized_count += 1 if created_count > 0 else 0
                skipped_count += 1 if skipped_here else 0
                results.append(
                    {
                        "closure_key": closure_key,
                        "executed": False,
                        "materialized": created_count > 0,
                        "created_count": created_count,
                        "skipped": skipped_here,
                        "reason": (
                            "Created follow-up task."
                            if created_count > 0
                            else "No new follow-up task was created."
                        ),
                    },
                )
                continue

            result = await self.execute_project_closure_action(
                project_id,
                action_kind=action_kind,
                target_id=target_id,
            )
            executed = bool(result.get("executed"))
            materialized = bool(result.get("materialized"))
            skipped = not executed and not materialized
            executed_count += 1 if executed else 0
            materialized_count += 1 if materialized else 0
            skipped_count += 1 if skipped else 0
            results.append(
                {
                    "closure_key": closure_key,
                    "executed": executed,
                    "materialized": materialized,
                    "skipped": skipped,
                    "reason": str(result.get("reason", "") or "").strip(),
                },
            )

        return {
            "mode": normalized_mode,
            "requested_count": len(cleaned_keys),
            "executed_count": executed_count,
            "materialized_count": materialized_count,
            "skipped_count": skipped_count,
            "results": results,
            "closure": await self.get_project_closure_report(project_id),
        }

    @staticmethod
    def _resolve_existing_path(path_text: str, *, base_dir: Path) -> Path | None:
        text = str(path_text or "").strip()
        if not text:
            return None
        path = Path(text).expanduser()
        if path.is_absolute():
            return path if path.exists() else None
        candidate = (base_dir / path).resolve()
        if candidate.exists():
            return candidate
        cwd_candidate = Path.cwd() / path
        if cwd_candidate.exists():
            return cwd_candidate.resolve()
        return None

    async def create_project_submission_package(self, project_id: str) -> dict[str, Any]:
        state = await self.load_state()
        project = self._project(state, project_id)
        dashboard = await self.get_project_dashboard(project_id)
        closure = await self.get_project_closure_report(project_id)
        dashboard_json = _json_ready(dashboard)
        closure_json = _json_ready(closure)

        package_root = self._storage_dir("packages", project.id)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bundle_dir = package_root / f"submission_{stamp}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = bundle_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        readme_path = bundle_dir / "README.md"
        closure_path = bundle_dir / "closure_report.json"
        dashboard_path = bundle_dir / "dashboard.json"
        claim_matrix_path = bundle_dir / "claim_matrix.json"
        experiment_matrix_path = bundle_dir / "experiment_matrix.json"
        manifest_path = bundle_dir / "manifest.json"
        project_path = bundle_dir / "project.json"

        readme_path.write_text(
            "\n".join(
                [
                    f"# Submission Package for {project.name}",
                    "",
                    f"- Generated at: {stamp}",
                    f"- Overall status: {closure['readiness']['overall_status']}",
                    f"- Completion score: {closure['readiness']['completion_score']}%",
                    f"- Ready for writing: {closure['readiness']['ready_for_writing']}",
                    f"- Ready for submission: {closure['readiness']['ready_for_submission']}",
                    f"- Ready for reproducibility: {closure['readiness']['ready_for_reproducibility']}",
                    "",
                    "## Included Reports",
                    "- project.json",
                    "- dashboard.json",
                    "- closure_report.json",
                    "- claim_matrix.json",
                    "- experiment_matrix.json",
                    "- manifest.json",
                ],
            )
            + "\n",
            encoding="utf-8",
        )
        project_path.write_text(
            json.dumps(project.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        dashboard_path.write_text(
            json.dumps(dashboard_json, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        closure_path.write_text(
            json.dumps(closure_json, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        claim_matrix_path.write_text(
            json.dumps(closure_json.get("claim_matrix", []), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        experiment_matrix_path.write_text(
            json.dumps(closure_json.get("experiment_matrix", []), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        included_files: list[dict[str, Any]] = []
        missing_files: list[dict[str, Any]] = []
        used_destinations: set[str] = set()
        base_dir = self._storage_root()
        file_candidates: list[dict[str, Any]] = []

        for artifact in state.artifacts:
            if artifact.project_id != project.id or not str(artifact.path or "").strip():
                continue
            file_candidates.append(
                {
                    "kind": "artifact",
                    "id": artifact.id,
                    "title": artifact.title,
                    "source_path": artifact.path,
                },
            )
        for experiment in state.experiments:
            if experiment.project_id != project.id:
                continue
            for output_file in list(experiment.output_files or []):
                if not str(output_file or "").strip():
                    continue
                file_candidates.append(
                    {
                        "kind": "experiment_output",
                        "id": experiment.id,
                        "title": experiment.name,
                        "source_path": output_file,
                    },
                )

        for candidate in file_candidates:
            source_path = self._resolve_existing_path(
                str(candidate.get("source_path", "") or ""),
                base_dir=base_dir,
            )
            if source_path is None:
                missing_files.append(candidate)
                continue
            dest_name = f"{self._slugify(str(candidate.get('kind', 'file') or 'file'))}-{self._slugify(str(candidate.get('id', 'item') or 'item'))}-{source_path.name}"
            if dest_name in used_destinations:
                dest_name = f"{self._slugify(str(candidate.get('kind', 'file') or 'file'))}-{self._slugify(str(candidate.get('id', 'item') or 'item'))}-{len(used_destinations)}-{source_path.name}"
            used_destinations.add(dest_name)
            destination = assets_dir / dest_name
            shutil.copy2(source_path, destination)
            included_files.append(
                {
                    **candidate,
                    "source_path": str(source_path),
                    "bundle_path": str(destination.relative_to(bundle_dir)),
                },
            )

        manifest_payload = {
            "package_type": "submission_repro_bundle",
            "project_id": project.id,
            "generated_at": stamp,
            "included_file_count": len(included_files),
            "missing_file_count": len(missing_files),
            "included_files": included_files,
            "missing_files": missing_files,
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        archive_path = bundle_dir.with_suffix(".zip")
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(bundle_dir.rglob("*")):
                if path.is_dir():
                    continue
                archive.write(path, arcname=str(path.relative_to(bundle_dir)))

        artifact = await self.upsert_artifact(
            project_id=project.id,
            title=f"{project.name} submission package {stamp}",
            artifact_type="experiment_result",
            description="Generated submission and reproducibility package archive.",
            path=str(archive_path),
            source_type="project_package",
            source_id=project.id,
            metadata={
                "package_dir": str(bundle_dir),
                "manifest_path": str(manifest_path),
                "package_type": "submission_repro_bundle",
            },
        )
        note = await self.create_note(
            project_id=project.id,
            title=f"Submission package generated · {stamp}",
            content=(
                f"Generated submission package at {archive_path}.\n\n"
                f"Included files: {len(included_files)}\n"
                f"Missing files: {len(missing_files)}"
            ),
            note_type="decision_log",
            artifact_ids=[artifact.id],
            tags=["submission", "reproducibility", "package"],
            metadata={
                "package_dir": str(bundle_dir),
                "archive_path": str(archive_path),
            },
        )
        return {
            "project": project.model_dump(mode="json"),
            "closure": closure_json,
            "package_dir": str(bundle_dir),
            "archive_path": str(archive_path),
            "manifest_path": str(manifest_path),
            "included_file_count": len(included_files),
            "missing_file_count": len(missing_files),
            "included_files": included_files[:50],
            "missing_files": missing_files[:50],
            "artifact": artifact.model_dump(mode="json"),
            "note": note.model_dump(mode="json"),
        }

    async def get_project_dashboard(self, project_id: str) -> dict[str, Any]:
        state = await self.load_state()
        project = self._project(state, project_id)
        workflow_limit = max(1, len(project.workflow_ids))
        experiment_limit = max(1, len(project.experiment_ids))
        artifact_limit = max(1, len(project.artifact_ids))
        workflows = self._project_recent_items(
            state.workflows,
            project.workflow_ids,
            limit=workflow_limit,
        )
        notes = self._project_recent_items(state.notes, project.note_ids, limit=5)
        experiments = self._project_recent_items(
            state.experiments,
            project.experiment_ids,
            limit=experiment_limit,
        )
        claims = self._project_recent_items(state.claims, project.claim_ids, limit=5)
        project_artifacts = self._project_recent_items(
            state.artifacts,
            project.artifact_ids,
            limit=artifact_limit,
        )
        drafts = [
            artifact for artifact in project_artifacts if artifact.artifact_type == "draft"
        ][:5]
        active_workflows = [
            workflow
            for workflow in workflows
            if workflow.status in {"queued", "running", "blocked", "paused"}
        ]
        now = datetime.now(timezone.utc)
        workflow_health = {
            "running": 0,
            "blocked": 0,
            "queued": 0,
            "paused": 0,
            "ready_for_retry": 0,
        }
        experiment_health = {
            "planned": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "contract_passed": 0,
            "contract_failed": 0,
            "bundle_passed": 0,
            "bundle_failed": 0,
            "bundle_pending": 0,
            "bundle_schema_missing": 0,
        }
        remediation_health = {
            "open_tasks": 0,
            "due_tasks": 0,
            "retry_exhausted": 0,
            "dispatch_attempts": 0,
            "execution_attempts": 0,
        }
        recent_blockers: list[dict[str, Any]] = []

        for workflow in workflows:
            if workflow.status in workflow_health:
                workflow_health[workflow.status] += 1
            remediation_context = self._workflow_contract_followup_context(state, workflow)
            if remediation_context.get("ready_for_retry"):
                workflow_health["ready_for_retry"] += 1
            remediation_tasks = list(remediation_context.get("remediation_tasks", []) or [])
            open_remediation_tasks = [
                task
                for task in remediation_tasks
                if str(task.get("status", "") or "").strip()
                not in {"completed", "cancelled"}
            ]
            remediation_health["open_tasks"] += len(open_remediation_tasks)
            remediation_health["retry_exhausted"] += int(
                remediation_context.get("retry_exhausted_count") or 0,
            )
            for task in open_remediation_tasks:
                remediation_health["dispatch_attempts"] += int(
                    task.get("dispatch_count") or 0,
                )
                remediation_health["execution_attempts"] += int(
                    task.get("execution_count") or 0,
                )
                due_at = _parse_iso(str(task.get("due_at") or "").strip() or None)
                if due_at is not None and due_at <= now:
                    remediation_health["due_tasks"] += 1
            blocker_row = self._project_blocker_row(
                state,
                workflow,
                remediation_context=remediation_context,
            )
            if blocker_row is not None:
                recent_blockers.append(blocker_row)

        for experiment in experiments:
            status = str(experiment.status or "").strip()
            if status in experiment_health:
                experiment_health[status] += 1
            contract_validation = self._evaluate_experiment_artifact_contract(
                state,
                experiment,
            )
            if contract_validation.get("enabled"):
                if contract_validation.get("passed", False):
                    experiment_health["contract_passed"] += 1
                else:
                    experiment_health["contract_failed"] += 1
            bundle_validation = dict(
                dict(getattr(experiment, "metadata", {}) or {}).get(
                    "result_bundle_validation",
                    {},
                )
                or {},
            )
            if bundle_validation.get("enabled"):
                if bundle_validation.get("passed", False):
                    experiment_health["bundle_passed"] += 1
                else:
                    experiment_health["bundle_failed"] += 1
                if bundle_validation.get("schema_found") is False:
                    experiment_health["bundle_schema_missing"] += 1
            elif str(getattr(experiment.execution, "result_bundle_schema", "") or "").strip():
                experiment_health["bundle_pending"] += 1

        recent_blockers.sort(
            key=lambda item: str(item.get("updated_at", "")),
            reverse=True,
        )
        return {
            "project": project,
            "counts": {
                "workflows": len(project.workflow_ids),
                "notes": len(project.note_ids),
                "experiments": len(project.experiment_ids),
                "claims": len(project.claim_ids),
                "artifacts": len(project.artifact_ids),
                "memory_entries": len(
                    [item for item in state.project_memory if item.project_id == project.id],
                ),
                "dataset_versions": len(
                    [item for item in state.dataset_versions if item.project_id == project.id],
                ),
                "checkpoints": len(
                    [item for item in state.checkpoints if item.project_id == project.id],
                ),
                "audit_events": len(
                    [item for item in state.audit_events if item.project_id == project.id],
                ),
                "drafts": len(
                    [item for item in state.artifacts if item.id in set(project.artifact_ids) and item.artifact_type == "draft"],
                ),
                "paper_refs": len(project.paper_refs),
                "paper_watches": len(project.paper_watches),
                "execution_catalog": len(project.execution_catalog),
                "result_bundle_schemas": len(project.result_bundle_schemas),
            },
            "health": {
                "workflows": workflow_health,
                "experiments": experiment_health,
                "remediation": remediation_health,
            },
            "active_workflows": active_workflows[:5],
            "recent_notes": notes,
            "recent_experiments": experiments[:5],
            "recent_claims": claims,
            "recent_drafts": drafts,
            "recent_blockers": recent_blockers[:5],
        }

    def _project_blocker_row(
        self,
        state: ResearchState,
        workflow: ResearchWorkflow,
        *,
        remediation_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        context = dict(
            remediation_context
            if remediation_context is not None
            else self._workflow_contract_followup_context(state, workflow),
        )
        remediation_tasks = list(context.get("remediation_tasks", []) or [])
        open_remediation_tasks = [
            task
            for task in remediation_tasks
            if str(task.get("status", "") or "").strip()
            not in {"completed", "cancelled"}
        ]
        ready_for_retry = bool(context.get("ready_for_retry", False))
        if not (
            workflow.status == "blocked"
            or open_remediation_tasks
            or ready_for_retry
        ):
            return None
        contract_failures = list(context.get("contract_failures", []) or [])
        actionable_tasks = [
            {
                "task_id": str(task.get("id", "") or ""),
                "title": str(task.get("title", "") or ""),
                "status": str(task.get("status", "") or ""),
                "assignee": str(task.get("assignee", "") or ""),
                "action_type": str(task.get("action_type", "") or ""),
                "target": str(task.get("target", "") or ""),
                "suggested_tool": str(task.get("suggested_tool", "") or ""),
                "can_dispatch": bool(task.get("can_dispatch", False)),
                "can_execute": bool(task.get("can_execute", False)),
                "dispatch_count": int(task.get("dispatch_count") or 0),
                "execution_count": int(task.get("execution_count") or 0),
                "last_dispatch_summary": str(
                    task.get("last_dispatch_summary", "") or "",
                ),
                "last_execution_summary": str(
                    task.get("last_execution_summary", "") or "",
                ),
            }
            for task in open_remediation_tasks[:3]
        ]
        return {
            "kind": "workflow_blocker",
            "workflow_id": workflow.id,
            "experiment_id": str(contract_failures[0].get("experiment_id", ""))
            if contract_failures
            else "",
            "title": workflow.title,
            "status": workflow.status,
            "stage": workflow.current_stage,
            "summary": str(
                context.get("remediation_summary")
                or f"{workflow.title} is blocked."
                or "",
            ).strip(),
            "blocked_task_id": str(context.get("blocked_task_id", "") or ""),
            "blocked_task_title": str(context.get("blocked_task_title", "") or ""),
            "open_remediation_tasks": len(open_remediation_tasks),
            "ready_for_retry": ready_for_retry,
            "contract_failure_count": len(contract_failures),
            "has_dispatchable_tasks": any(
                bool(task.get("can_dispatch", False)) for task in open_remediation_tasks
            ),
            "has_executable_tasks": any(
                bool(task.get("can_execute", False)) for task in open_remediation_tasks
            ),
            "actionable_tasks": actionable_tasks,
            "updated_at": workflow.updated_at,
        }

    async def list_project_blockers(
        self,
        project_id: str,
        *,
        kind: str = "",
        status: str = "",
        stage: str = "",
        workflow_id: str = "",
        ready_for_retry: bool | None = None,
        query: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        state = await self.load_state()
        project = self._project(state, project_id)
        workflows = self._project_recent_items(
            state.workflows,
            project.workflow_ids,
            limit=max(1, len(project.workflow_ids)),
        )
        rows: list[dict[str, Any]] = []
        for workflow in workflows:
            row = self._project_blocker_row(state, workflow)
            if row is None:
                continue
            rows.append(row)
        if kind:
            rows = [item for item in rows if str(item.get("kind", "") or "") == kind]
        if status:
            rows = [
                item for item in rows if str(item.get("status", "") or "") == status
            ]
        if stage:
            rows = [item for item in rows if str(item.get("stage", "") or "") == stage]
        if workflow_id:
            rows = [
                item
                for item in rows
                if str(item.get("workflow_id", "") or "") == workflow_id
            ]
        if ready_for_retry is not None:
            rows = [
                item
                for item in rows
                if bool(item.get("ready_for_retry", False)) is ready_for_retry
            ]
        if query:
            query_text = str(query).strip().lower()
            rows = [
                item
                for item in rows
                if query_text in str(item.get("title", "") or "").lower()
                or query_text in str(item.get("summary", "") or "").lower()
                or query_text in str(item.get("blocked_task_title", "") or "").lower()
                or query_text in str(item.get("status", "") or "").lower()
                or query_text in str(item.get("stage", "") or "").lower()
                or any(
                    query_text in str(task.get("title", "") or "").lower()
                    for task in list(item.get("actionable_tasks", []) or [])
                    if isinstance(task, dict)
                )
            ]
        rows.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return rows[: max(1, int(limit))]

    async def get_overview(self) -> dict[str, Any]:
        state = await self.load_state()
        active_workflows = [
            item
            for item in state.workflows
            if item.status in {"queued", "running", "blocked", "paused"}
        ]
        return {
            "counts": {
                "projects": len(state.projects),
                "workflows": len(state.workflows),
                "active_workflows": len(active_workflows),
                "notes": len(state.notes),
                "claims": len(state.claims),
                "evidences": len(state.evidences),
                "memory_entries": len(state.project_memory),
                "dataset_versions": len(state.dataset_versions),
                "checkpoints": len(state.checkpoints),
                "audit_events": len(state.audit_events),
                "experiments": len(state.experiments),
                "artifacts": len(state.artifacts),
            },
            "active_workflows": active_workflows[:10],
            "projects": state.projects[:10],
        }

    async def list_audit_events(
        self,
        *,
        project_id: str = "",
        workflow_id: str = "",
        entity_type: str = "",
        entity_id: str = "",
        limit: int = 100,
    ) -> list[AuditEvent]:
        state = await self.load_state()
        rows = list(state.audit_events)
        if project_id:
            rows = [item for item in rows if item.project_id == project_id]
        if workflow_id:
            rows = [item for item in rows if item.workflow_id == workflow_id]
        if entity_type:
            rows = [item for item in rows if item.entity_type == entity_type]
        if entity_id:
            rows = [item for item in rows if item.entity_id == entity_id]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(1, int(limit))]

    async def list_workflow_checkpoints(
        self,
        *,
        workflow_id: str,
        limit: int = 100,
    ) -> list[WorkflowCheckpoint]:
        state = await self.load_state()
        rows = [
            item
            for item in state.checkpoints
            if item.workflow_id == workflow_id
        ]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(1, int(limit))]

    async def restore_workflow_checkpoint(
        self,
        *,
        workflow_id: str,
        checkpoint_id: str = "",
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        candidates = [
            item
            for item in state.checkpoints
            if item.workflow_id == workflow_id
        ]
        if checkpoint_id:
            checkpoint = next(
                (item for item in candidates if item.id == checkpoint_id),
                None,
            )
        else:
            checkpoint = next(iter(sorted(candidates, key=lambda item: item.created_at, reverse=True)), None)
        if checkpoint is None:
            raise ValueError(f"No checkpoint found for workflow: {workflow_id}")
        workflow.current_stage = checkpoint.stage
        workflow.status = (
            checkpoint.workflow_status
            if checkpoint.workflow_status in {"paused", "completed", "cancelled"}
            else "running"
        )
        for task in workflow.tasks:
            if task.id not in checkpoint.task_statuses:
                continue
            task.status = checkpoint.task_statuses[task.id]  # type: ignore[assignment]
            if task.status in {"completed", "cancelled"} and not task.completed_at:
                task.completed_at = utc_now()
            task.updated_at = utc_now()
        snapshot = dict(checkpoint.snapshot or {})
        workflow.note_ids = list(snapshot.get("note_ids", workflow.note_ids))
        workflow.claim_ids = list(snapshot.get("claim_ids", workflow.claim_ids))
        workflow.artifact_ids = list(snapshot.get("artifact_ids", workflow.artifact_ids))
        workflow.experiment_ids = list(
            snapshot.get("experiment_ids", workflow.experiment_ids),
        )
        self._touch(workflow)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_restored",
            metadata={"source_checkpoint_id": checkpoint.id},
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="restore_checkpoint",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Restored workflow '{workflow.title}' from checkpoint '{checkpoint.id}'.",
            before=before,
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def create_project_memory(
        self,
        *,
        project_id: str,
        title: str,
        content: str,
        entry_kind: str = "fact",
        workflow_id: str = "",
        stage: str = "",
        status: str = "active",
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        experiment_ids: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectMemoryEntry:
        state = await self.load_state()
        self._project(state, project_id)
        if workflow_id:
            self._workflow(state, workflow_id)
        entry = ProjectMemoryEntry(
            project_id=project_id,
            title=title,
            content=content,
            entry_kind=entry_kind,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            workflow_id=workflow_id,
            stage=stage,
            note_ids=_remove_empty_strings(note_ids or []),
            claim_ids=_remove_empty_strings(claim_ids or []),
            artifact_ids=_remove_empty_strings(artifact_ids or []),
            experiment_ids=_remove_empty_strings(experiment_ids or []),
            tags=_remove_empty_strings(tags or []),
            metadata=dict(metadata or {}),
        )
        state.project_memory.append(entry)
        self._record_audit_event(
            state,
            entity_type="memory",
            entity_id=entry.id,
            action="create",
            project_id=entry.project_id,
            workflow_id=entry.workflow_id,
            summary=f"Created project memory entry '{entry.title}'.",
            after=self._model_payload(entry),
        )
        await self.save_state(state)
        return entry

    async def update_project_memory(
        self,
        *,
        project_id: str,
        memory_id: str,
        title: str | None = None,
        content: str | None = None,
        entry_kind: str | None = None,
        workflow_id: str | None = None,
        stage: str | None = None,
        status: str | None = None,
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        experiment_ids: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectMemoryEntry:
        state = await self.load_state()
        self._project(state, project_id)
        entry = self._memory_entry(state, memory_id)
        if entry.project_id != project_id:
            raise ValueError("Project memory entry does not belong to this project.")
        before = self._model_payload(entry)

        if title is not None:
            clean_title = str(title).strip()
            if not clean_title:
                raise ValueError("Project memory title cannot be empty.")
            entry.title = clean_title
        if content is not None:
            clean_content = str(content).strip()
            if not clean_content:
                raise ValueError("Project memory content cannot be empty.")
            entry.content = clean_content
        if entry_kind is not None:
            entry.entry_kind = entry_kind  # type: ignore[assignment]
        if status is not None:
            entry.status = status  # type: ignore[assignment]
        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != project_id:
                    raise ValueError("Project memory workflow must belong to the same project.")
            entry.workflow_id = clean_workflow_id
        if stage is not None:
            entry.stage = str(stage or "").strip()
        if note_ids is not None:
            cleaned_note_ids = _remove_empty_strings(note_ids)
            for note_id in cleaned_note_ids:
                note = self._note(state, note_id)
                if note.project_id != project_id:
                    raise ValueError("Project memory note references must stay within one project.")
            entry.note_ids = cleaned_note_ids
        if claim_ids is not None:
            cleaned_claim_ids = _remove_empty_strings(claim_ids)
            for claim_id in cleaned_claim_ids:
                claim = self._claim(state, claim_id)
                if claim.project_id != project_id:
                    raise ValueError("Project memory claim references must stay within one project.")
            entry.claim_ids = cleaned_claim_ids
        if artifact_ids is not None:
            cleaned_artifact_ids = _remove_empty_strings(artifact_ids)
            for artifact_id in cleaned_artifact_ids:
                artifact = self._artifact(state, artifact_id)
                if artifact.project_id != project_id:
                    raise ValueError("Project memory artifact references must stay within one project.")
            entry.artifact_ids = cleaned_artifact_ids
        if experiment_ids is not None:
            cleaned_experiment_ids = _remove_empty_strings(experiment_ids)
            for experiment_id in cleaned_experiment_ids:
                experiment = self._experiment(state, experiment_id)
                if experiment.project_id != project_id:
                    raise ValueError("Project memory experiment references must stay within one project.")
            entry.experiment_ids = cleaned_experiment_ids
        if tags is not None:
            entry.tags = _remove_empty_strings(tags)
        if metadata is not None:
            entry.metadata = dict(metadata)

        self._touch(entry)
        self._record_audit_event(
            state,
            entity_type="memory",
            entity_id=entry.id,
            action="update",
            project_id=entry.project_id,
            workflow_id=entry.workflow_id,
            summary=f"Updated project memory entry '{entry.title}'.",
            before=before,
            after=self._model_payload(entry),
        )
        await self.save_state(state)
        return entry

    async def list_project_memory(
        self,
        *,
        project_id: str,
        workflow_id: str = "",
        entry_kind: str = "",
        status: str = "",
        stage: str = "",
        tag: str = "",
        query: str = "",
        limit: int = 100,
    ) -> list[ProjectMemoryEntry]:
        state = await self.load_state()
        rows = [
            item
            for item in state.project_memory
            if item.project_id == project_id
        ]
        if workflow_id:
            rows = [item for item in rows if item.workflow_id == workflow_id]
        if entry_kind:
            rows = [item for item in rows if item.entry_kind == entry_kind]
        if status:
            rows = [item for item in rows if item.status == status]
        if stage:
            rows = [item for item in rows if item.stage == stage]
        if tag:
            clean_tag = str(tag).strip()
            rows = [item for item in rows if clean_tag in set(item.tags)]
        if query:
            query_text = str(query).strip().lower()
            rows = [
                item
                for item in rows
                if query_text in item.title.lower()
                or query_text in item.content.lower()
                or query_text in item.stage.lower()
            ]
        rows.sort(key=lambda item: item.updated_at, reverse=True)
        return rows[: max(1, int(limit))]

    async def bulk_update_project_memory(
        self,
        *,
        project_id: str,
        memory_ids: list[str],
        status: str | None = None,
        entry_kind: str | None = None,
        workflow_id: str | None = None,
        stage: str | None = None,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_memory_ids = _remove_empty_strings(memory_ids)
        if not cleaned_memory_ids:
            raise ValueError("No project memory ids provided.")
        if (
            status is None
            and entry_kind is None
            and workflow_id is None
            and stage is None
            and not _remove_empty_strings(add_tags or [])
            and not _remove_empty_strings(remove_tags or [])
            and not dict(metadata_patch or {})
        ):
            raise ValueError("No project memory bulk update fields were provided.")

        updated_entries: list[ProjectMemoryEntry] = []
        add_tag_set = set(_remove_empty_strings(add_tags or []))
        remove_tag_set = set(_remove_empty_strings(remove_tags or []))
        metadata_patch_dict = dict(metadata_patch or {})
        for memory_id in cleaned_memory_ids:
            entry = self._memory_entry(state, memory_id)
            if entry.project_id != project_id:
                raise ValueError("Project memory bulk update must stay within one project.")
            next_tags = list(entry.tags)
            if add_tag_set or remove_tag_set:
                next_tags = [
                    tag_item
                    for tag_item in next_tags
                    if tag_item not in remove_tag_set
                ]
                for tag_item in add_tag_set:
                    _append_unique(next_tags, tag_item)
            next_metadata = dict(entry.metadata)
            if metadata_patch_dict:
                next_metadata.update(metadata_patch_dict)
            updated_entries.append(
                await self.update_project_memory(
                    project_id=project_id,
                    memory_id=memory_id,
                    status=status,
                    entry_kind=entry_kind,
                    workflow_id=workflow_id,
                    stage=stage,
                    tags=next_tags if (add_tag_set or remove_tag_set) else None,
                    metadata=next_metadata if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_entries),
            "entries": updated_entries,
        }

    async def create_artifact_relation(
        self,
        *,
        project_id: str,
        source_artifact_id: str,
        target_artifact_id: str,
        relation_type: str,
        workflow_id: str = "",
        experiment_id: str = "",
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRelation:
        state = await self.load_state()
        self._project(state, project_id)
        source_artifact = self._artifact(state, source_artifact_id)
        target_artifact = self._artifact(state, target_artifact_id)
        if source_artifact.project_id != project_id or target_artifact.project_id != project_id:
            raise ValueError("Artifact relation must stay within one project.")
        existing = next(
            (
                item
                for item in state.artifact_relations
                if item.project_id == project_id
                and item.source_artifact_id == source_artifact_id
                and item.target_artifact_id == target_artifact_id
                and item.relation_type == relation_type
            ),
            None,
        )
        if existing is not None:
            if summary:
                existing.summary = summary
            if metadata:
                merged_metadata = dict(existing.metadata)
                merged_metadata.update(dict(metadata))
                existing.metadata = merged_metadata
            self._record_audit_event(
                state,
                entity_type="relation",
                entity_id=existing.id,
                action="update",
                project_id=project_id,
                workflow_id=workflow_id,
                summary=f"Updated artifact relation {existing.relation_type}.",
                after=self._model_payload(existing),
            )
            await self.save_state(state)
            return existing
        relation = ArtifactRelation(
            project_id=project_id,
            relation_type=relation_type,  # type: ignore[arg-type]
            source_artifact_id=source_artifact_id,
            target_artifact_id=target_artifact_id,
            workflow_id=workflow_id,
            experiment_id=experiment_id,
            summary=summary,
            metadata=dict(metadata or {}),
        )
        state.artifact_relations.append(relation)
        self._record_audit_event(
            state,
            entity_type="relation",
            entity_id=relation.id,
            action="create",
            project_id=project_id,
            workflow_id=workflow_id,
            summary=(
                f"Created artifact relation {relation.relation_type} "
                f"{source_artifact_id} -> {target_artifact_id}."
            ),
            after=self._model_payload(relation),
        )
        await self.save_state(state)
        return relation

    async def list_artifact_relations(
        self,
        *,
        project_id: str = "",
        artifact_id: str = "",
        relation_type: str = "",
        limit: int = 100,
    ) -> list[ArtifactRelation]:
        state = await self.load_state()
        rows = list(state.artifact_relations)
        if project_id:
            rows = [item for item in rows if item.project_id == project_id]
        if artifact_id:
            rows = [
                item
                for item in rows
                if item.source_artifact_id == artifact_id
                or item.target_artifact_id == artifact_id
            ]
        if relation_type:
            rows = [item for item in rows if item.relation_type == relation_type]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(1, int(limit))]

    async def get_artifact_lineage(
        self,
        artifact_id: str,
        *,
        direction: str = "both",
    ) -> dict[str, Any]:
        state = await self.load_state()
        artifact = self._artifact(state, artifact_id)
        incoming = [
            item
            for item in state.artifact_relations
            if item.source_artifact_id == artifact_id
        ]
        outgoing = [
            item
            for item in state.artifact_relations
            if item.target_artifact_id == artifact_id
        ]
        if direction == "upstream":
            wanted_relations = incoming
        elif direction == "downstream":
            wanted_relations = outgoing
        else:
            wanted_relations = [*incoming, *outgoing]
        related_ids = {
            relation.source_artifact_id
            for relation in wanted_relations
        } | {
            relation.target_artifact_id
            for relation in wanted_relations
        }
        related_artifacts = [
            item for item in state.artifacts if item.id in related_ids and item.id != artifact_id
        ]
        return {
            "artifact": artifact,
            "direction": direction,
            "relations": wanted_relations,
            "related_artifacts": related_artifacts,
        }

    async def create_dataset_version(
        self,
        *,
        project_id: str,
        name: str,
        version_label: str = "v1",
        description: str = "",
        workflow_id: str = "",
        path: str = "",
        source_paths: list[str] | None = None,
        parent_version_id: str = "",
        split_spec: dict[str, Any] | None = None,
        transform_steps: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchDatasetVersion:
        state = await self.load_state()
        self._project(state, project_id)
        if workflow_id:
            self._workflow(state, workflow_id)
        if parent_version_id:
            self._dataset_version(state, parent_version_id)
        clean_source_paths = _remove_empty_strings(source_paths or [])
        dataset_dir = self._storage_dir("datasets", project_id)
        file_hashes = self._hash_existing_paths(clean_source_paths, base_dir=self._storage_root())
        manifest_path = dataset_dir / f"{self._slugify(name)}-{self._slugify(version_label)}.json"
        dataset_artifact = next(
            (
                item
                for item in state.artifacts
                if item.project_id == project_id
                and item.artifact_type == "dataset"
                and item.path == (path or str(manifest_path))
            ),
            None,
        )
        if dataset_artifact is None:
            dataset_artifact = self._add_artifact_to_state(
                state,
                project_id=project_id,
                workflow_id=workflow_id,
                title=f"{name} {version_label}",
                artifact_type="dataset",
                description=description or f"Dataset version {version_label} for {name}.",
                path=path or str(manifest_path),
                source_type="dataset_version",
                source_id=f"{name}:{version_label}",
                metadata={
                    "dataset_name": name,
                    "version_label": version_label,
                },
            )
        dataset_version = ResearchDatasetVersion(
            project_id=project_id,
            name=name,
            version_label=version_label,
            description=description,
            workflow_id=workflow_id,
            path=path,
            manifest_path=str(manifest_path),
            source_paths=clean_source_paths,
            artifact_id=dataset_artifact.id,
            parent_version_id=parent_version_id,
            split_spec=dict(split_spec or {}),
            transform_steps=list(transform_steps or []),
            file_hashes=file_hashes,
            tags=_remove_empty_strings(tags or []),
            metadata=dict(metadata or {}),
        )
        manifest_payload = dataset_version.model_dump(mode="json")
        manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        state.dataset_versions.append(dataset_version)
        self._record_audit_event(
            state,
            entity_type="dataset_version",
            entity_id=dataset_version.id,
            action="create",
            project_id=project_id,
            workflow_id=workflow_id,
            summary=f"Registered dataset version '{name} {version_label}'.",
            after=self._model_payload(dataset_version),
        )
        await self.save_state(state)
        return dataset_version

    async def update_dataset_version(
        self,
        *,
        dataset_version_id: str,
        name: str | None = None,
        version_label: str | None = None,
        description: str | None = None,
        workflow_id: str | None = None,
        path: str | None = None,
        source_paths: list[str] | None = None,
        parent_version_id: str | None = None,
        split_spec: dict[str, Any] | None = None,
        transform_steps: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchDatasetVersion:
        state = await self.load_state()
        dataset_version = self._dataset_version(state, dataset_version_id)
        before = self._model_payload(dataset_version)

        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValueError("Dataset version name cannot be empty.")
            dataset_version.name = clean_name
        if version_label is not None:
            clean_version_label = str(version_label).strip()
            if not clean_version_label:
                raise ValueError("Dataset version label cannot be empty.")
            dataset_version.version_label = clean_version_label
        if description is not None:
            dataset_version.description = str(description or "").strip()
        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != dataset_version.project_id:
                    raise ValueError("Dataset version workflow must belong to the same project.")
            dataset_version.workflow_id = clean_workflow_id
        if path is not None:
            dataset_version.path = str(path or "").strip()
        if source_paths is not None:
            dataset_version.source_paths = _remove_empty_strings(source_paths)
        if parent_version_id is not None:
            clean_parent_version_id = str(parent_version_id or "").strip()
            if clean_parent_version_id:
                parent_version = self._dataset_version(state, clean_parent_version_id)
                if parent_version.project_id != dataset_version.project_id:
                    raise ValueError("Dataset version parent must belong to the same project.")
                if parent_version.id == dataset_version.id:
                    raise ValueError("Dataset version cannot derive from itself.")
            dataset_version.parent_version_id = clean_parent_version_id
        if split_spec is not None:
            dataset_version.split_spec = dict(split_spec)
        if transform_steps is not None:
            dataset_version.transform_steps = list(transform_steps)
        if tags is not None:
            dataset_version.tags = _remove_empty_strings(tags)
        if metadata is not None:
            dataset_version.metadata = dict(metadata)

        dataset_version.file_hashes = self._hash_existing_paths(
            dataset_version.source_paths,
            base_dir=self._storage_root(),
        )
        previous_manifest_path = (
            Path(dataset_version.manifest_path).expanduser()
            if dataset_version.manifest_path
            else None
        )
        next_manifest_path = self._storage_dir("datasets", dataset_version.project_id) / (
            f"{self._slugify(dataset_version.name)}-"
            f"{self._slugify(dataset_version.version_label)}.json"
        )
        dataset_version.manifest_path = str(next_manifest_path)
        self._touch(dataset_version)

        manifest_payload = dataset_version.model_dump(mode="json")
        next_manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if (
            previous_manifest_path is not None
            and previous_manifest_path != next_manifest_path
            and previous_manifest_path.exists()
        ):
            previous_manifest_path.unlink()

        artifact: ResearchArtifact | None = None
        if dataset_version.artifact_id:
            try:
                artifact = self._artifact(state, dataset_version.artifact_id)
            except ValueError:
                artifact = None
        if artifact is None:
            artifact = self._add_artifact_to_state(
                state,
                project_id=dataset_version.project_id,
                workflow_id=dataset_version.workflow_id,
                title=f"{dataset_version.name} {dataset_version.version_label}",
                artifact_type="dataset",
                description=(
                    dataset_version.description
                    or f"Dataset version {dataset_version.version_label} for {dataset_version.name}."
                ),
                path=dataset_version.path or dataset_version.manifest_path,
                source_type="dataset_version",
                source_id=f"{dataset_version.name}:{dataset_version.version_label}",
                metadata={
                    "dataset_name": dataset_version.name,
                    "version_label": dataset_version.version_label,
                },
            )
            dataset_version.artifact_id = artifact.id
        else:
            artifact.title = f"{dataset_version.name} {dataset_version.version_label}"
            artifact.workflow_id = dataset_version.workflow_id
            artifact.description = (
                dataset_version.description
                or f"Dataset version {dataset_version.version_label} for {dataset_version.name}."
            )
            artifact.path = dataset_version.path or dataset_version.manifest_path
            artifact.source_type = "dataset_version"
            artifact.source_id = f"{dataset_version.name}:{dataset_version.version_label}"
            merged_metadata = dict(artifact.metadata)
            merged_metadata.update(
                {
                    "dataset_name": dataset_version.name,
                    "version_label": dataset_version.version_label,
                },
            )
            artifact.metadata = merged_metadata
            project = self._project(state, dataset_version.project_id)
            _append_unique(project.artifact_ids, artifact.id)
            self._touch(project)
            if dataset_version.workflow_id:
                workflow = self._workflow(state, dataset_version.workflow_id)
                _append_unique(workflow.artifact_ids, artifact.id)
                stage = self._workflow_stage(workflow, workflow.current_stage)
                _append_unique(stage.artifact_ids, artifact.id)
                self._touch(workflow)
                stage.updated_at = utc_now()
            self._touch(artifact)

        self._record_audit_event(
            state,
            entity_type="dataset_version",
            entity_id=dataset_version.id,
            action="update",
            project_id=dataset_version.project_id,
            workflow_id=dataset_version.workflow_id,
            summary=(
                f"Updated dataset version '{dataset_version.name} "
                f"{dataset_version.version_label}'."
            ),
            before=before,
            after=self._model_payload(dataset_version),
        )
        await self.save_state(state)
        return dataset_version

    async def list_dataset_versions(
        self,
        *,
        project_id: str = "",
        workflow_id: str = "",
        name: str = "",
        name_query: str = "",
        tag: str = "",
        parent_version_id: str = "",
        limit: int = 100,
    ) -> list[ResearchDatasetVersion]:
        state = await self.load_state()
        rows = list(state.dataset_versions)
        if project_id:
            rows = [item for item in rows if item.project_id == project_id]
        if workflow_id:
            rows = [item for item in rows if item.workflow_id == workflow_id]
        if name:
            rows = [item for item in rows if item.name == name]
        if name_query:
            query_text = str(name_query).strip().lower()
            rows = [
                item
                for item in rows
                if query_text in item.name.lower()
                or query_text in item.version_label.lower()
                or query_text in item.description.lower()
            ]
        if tag:
            clean_tag = str(tag).strip()
            rows = [item for item in rows if clean_tag in set(item.tags)]
        if parent_version_id:
            rows = [
                item
                for item in rows
                if item.parent_version_id == parent_version_id
            ]
        rows.sort(key=lambda item: item.updated_at or item.created_at, reverse=True)
        return rows[: max(1, int(limit))]

    async def bulk_update_dataset_versions(
        self,
        *,
        project_id: str,
        dataset_version_ids: list[str],
        workflow_id: str | None = None,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_dataset_ids = _remove_empty_strings(dataset_version_ids)
        if not cleaned_dataset_ids:
            raise ValueError("No dataset version ids provided.")
        if (
            workflow_id is None
            and not _remove_empty_strings(add_tags or [])
            and not _remove_empty_strings(remove_tags or [])
            and not dict(metadata_patch or {})
        ):
            raise ValueError("No dataset version bulk update fields were provided.")

        updated_versions: list[ResearchDatasetVersion] = []
        add_tag_set = set(_remove_empty_strings(add_tags or []))
        remove_tag_set = set(_remove_empty_strings(remove_tags or []))
        metadata_patch_dict = dict(metadata_patch or {})
        for dataset_version_id in cleaned_dataset_ids:
            dataset_version = self._dataset_version(state, dataset_version_id)
            if dataset_version.project_id != project_id:
                raise ValueError("Dataset version bulk update must stay within one project.")
            next_tags = list(dataset_version.tags)
            if add_tag_set or remove_tag_set:
                next_tags = [
                    tag_item
                    for tag_item in next_tags
                    if tag_item not in remove_tag_set
                ]
                for tag_item in add_tag_set:
                    _append_unique(next_tags, tag_item)
            next_metadata = dict(dataset_version.metadata)
            if metadata_patch_dict:
                next_metadata.update(metadata_patch_dict)
            updated_versions.append(
                await self.update_dataset_version(
                    dataset_version_id=dataset_version_id,
                    workflow_id=workflow_id,
                    tags=next_tags if (add_tag_set or remove_tag_set) else None,
                    metadata=next_metadata if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_versions),
            "dataset_versions": updated_versions,
        }

    def _claim_validation(
        self,
        state: ResearchState,
        claim: ResearchClaim,
    ) -> dict[str, Any]:
        evidences = [
            item
            for item in state.evidences
            if item.id in set(claim.evidence_ids) or claim.id in set(item.claim_ids)
        ]
        strong_types = {
            "paper",
            "pdf_chunk",
            "citation",
            "experiment_result",
            "generated_table",
            "generated_figure",
        }
        strong_count = 0
        counter_count = 0
        missing_locator_count = 0
        for evidence in evidences:
            if evidence.evidence_type in strong_types:
                strong_count += 1
            evidence_metadata = {
                **dict(getattr(evidence, "metadata", {}) or {}),
                **dict(getattr(evidence.source, "metadata", {}) or {}),
            }
            if bool(evidence_metadata.get("counter")) or str(
                evidence_metadata.get("polarity", ""),
            ).strip() == "counter":
                counter_count += 1
            if evidence.evidence_type in {"paper", "pdf_chunk", "citation"} and not (
                str(evidence.source.locator or "").strip()
                or str(evidence.source.quote or "").strip()
            ):
                missing_locator_count += 1

        status = "draft"
        reasons: list[str] = []
        if not evidences:
            reasons.append("No evidence is linked to this claim.")
        elif counter_count > 0:
            status = "disputed"
            reasons.append("Counter-evidence is attached to this claim.")
        elif strong_count > 0 and missing_locator_count == 0:
            status = "supported"
            reasons.append("At least one strong evidence item is linked with traceable locators.")
        else:
            status = "needs_review"
            if strong_count == 0:
                reasons.append("Only lightweight evidence is linked; stronger evidence is required.")
            if missing_locator_count > 0:
                reasons.append("Some paper-like evidence is missing a locator or quote.")

        return {
            "claim_id": claim.id,
            "status": status,
            "evidence_count": len(evidences),
            "strong_evidence_count": strong_count,
            "counter_evidence_count": counter_count,
            "missing_locator_count": missing_locator_count,
            "reasons": reasons,
            "evidence_ids": [item.id for item in evidences],
        }

    async def validate_claim(
        self,
        claim_id: str,
        *,
        apply_status: bool = False,
    ) -> dict[str, Any]:
        state = await self.load_state()
        claim = self._claim(state, claim_id)
        validation = self._claim_validation(state, claim)
        if apply_status:
            before = self._model_payload(claim)
            claim.status = validation["status"]  # type: ignore[assignment]
            claim.metadata = {
                **dict(claim.metadata),
                "validation": validation,
            }
            self._touch(claim)
            self._record_audit_event(
                state,
                entity_type="claim",
                entity_id=claim.id,
                action="validate",
                project_id=claim.project_id,
                workflow_id=claim.workflow_id,
                summary=f"Validated claim '{claim.text[:72]}' as {claim.status}.",
                before=before,
                after=self._model_payload(claim),
            )
            await self.save_state(state)
        return validation

    async def validate_project_claims(
        self,
        *,
        project_id: str,
        workflow_id: str = "",
        apply_status: bool = False,
    ) -> list[dict[str, Any]]:
        state = await self.load_state()
        claims = [
            item for item in state.claims if item.project_id == project_id
        ]
        if workflow_id:
            claims = [item for item in claims if item.workflow_id == workflow_id]
        validations: list[dict[str, Any]] = []
        changed = False
        for claim in claims:
            validation = self._claim_validation(state, claim)
            validations.append(validation)
            if apply_status and claim.status != validation["status"]:
                claim.status = validation["status"]  # type: ignore[assignment]
                claim.metadata = {
                    **dict(claim.metadata),
                    "validation": validation,
                }
                self._touch(claim)
                changed = True
        if changed:
            await self.save_state(state)
        return validations

    # ---- workflow APIs ----

    async def list_workflows(
        self,
        *,
        project_id: str = "",
        status: str = "",
    ) -> list[ResearchWorkflow]:
        state = await self.load_state()
        rows = list(state.workflows)
        if project_id:
            rows = [item for item in rows if item.project_id == project_id]
        if status:
            rows = [item for item in rows if item.status == status]
        return rows

    async def create_workflow(
        self,
        *,
        project_id: str,
        title: str,
        goal: str = "",
        bindings: dict[str, Any] | None = None,
        execution_policy: dict[str, Any] | None = None,
        experiment_runner: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        auto_start: bool = True,
    ) -> ResearchWorkflow:
        state = await self.load_state()
        project = self._project(state, project_id)
        workflow = ResearchWorkflow(
            project_id=project_id,
            title=title,
            goal=goal,
            status="running" if auto_start else "draft",
            bindings=self._merge_binding(
                base=project.default_binding,
                patch=bindings,
            ),
            execution_policy=self._merge_execution_policy(
                base=WorkflowExecutionPolicy(),
                patch=execution_policy,
            ),
            experiment_runner=self._merge_runner_profile(
                base=project.default_experiment_runner,
                patch=experiment_runner,
            ),
            stages=[WorkflowStageState(name=stage) for stage in WORKFLOW_STAGES],
            metadata=dict(metadata or {}),
        )
        if auto_start:
            workflow.started_at = utc_now()
            workflow.last_transition_at = workflow.started_at
            stage = self._workflow_stage(workflow, workflow.current_stage)
            stage.status = "running"
            stage.started_at = workflow.started_at
            stage.updated_at = workflow.started_at
            self._seed_stage_task(workflow)
            self._recompute_workflow(workflow, now=workflow.started_at)
        state.workflows.append(workflow)
        _append_unique(project.workflow_ids, workflow.id)
        self._touch(project)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_created",
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="create",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Created workflow '{workflow.title}'.",
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def get_workflow(self, workflow_id: str) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        self._ensure_workflow_scaffold(workflow)
        return workflow

    async def get_workflow_task(
        self,
        *,
        workflow_id: str,
        task_id: str,
    ) -> WorkflowTask:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        self._ensure_workflow_scaffold(workflow)
        return self._workflow_task(workflow, task_id)

    async def tick_workflow(self, workflow_id: str) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        self._recompute_workflow(workflow)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_ticked",
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="tick",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Ticked workflow '{workflow.title}' into stage '{workflow.current_stage}'.",
            before=before,
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def update_workflow_binding(
        self,
        *,
        workflow_id: str,
        patch: dict[str, Any],
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.bindings = self._merge_binding(
            base=workflow.bindings,
            patch=patch,
        )
        self._touch(workflow)
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="binding_update",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Updated workflow binding for '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
            metadata={"patch": dict(patch)},
        )
        await self.save_state(state)
        return workflow

    async def update_workflow_execution_policy(
        self,
        *,
        workflow_id: str,
        patch: dict[str, Any],
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.execution_policy = self._merge_execution_policy(
            base=workflow.execution_policy,
            patch=patch,
        )
        self._touch(workflow)
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="execution_policy_update",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Updated execution policy for '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
            metadata={"patch": dict(patch)},
        )
        await self.save_state(state)
        return workflow

    async def update_workflow_experiment_runner(
        self,
        *,
        workflow_id: str,
        patch: dict[str, Any],
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.experiment_runner = self._merge_runner_profile(
            base=workflow.experiment_runner,
            patch=patch,
        )
        self._touch(workflow)
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="experiment_runner_update",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Updated experiment runner profile for '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
            metadata={"patch": dict(patch)},
        )
        await self.save_state(state)
        return workflow

    async def pause_workflow(self, workflow_id: str) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.status = "paused"
        workflow.paused_at = utc_now()
        self._touch(workflow)
        stage = self._workflow_stage(workflow, workflow.current_stage)
        if stage.status == "running":
            stage.status = "pending"
            stage.updated_at = workflow.paused_at or utc_now()
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_paused",
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="pause",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Paused workflow '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def resume_workflow(self, workflow_id: str) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.status = "running"
        workflow.paused_at = None
        stage = self._workflow_stage(workflow, workflow.current_stage)
        stage.status = "running"
        if not stage.started_at:
            stage.started_at = utc_now()
        self._recompute_workflow(workflow)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_resumed",
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="resume",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Resumed workflow '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def cancel_workflow(self, workflow_id: str) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.status = "cancelled"
        self._touch(workflow)
        for task in self._stage_task_list(workflow, workflow.current_stage):
            if task.status in {"pending", "running", "blocked"}:
                task.status = "cancelled"
                task.completed_at = utc_now()
                task.updated_at = task.completed_at
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_cancelled",
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="cancel",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Cancelled workflow '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def retry_workflow(self, workflow_id: str) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        workflow.status = "running"
        workflow.retry_count += 1
        workflow.error = ""
        stage = self._workflow_stage(workflow, workflow.current_stage)
        stage.status = "running"
        stage.blocked_reason = ""
        stage.updated_at = utc_now()
        for task in self._stage_task_list(workflow, workflow.current_stage):
            if task.status in {"failed", "blocked"}:
                task.status = "pending"
                task.summary = ""
                task.updated_at = utc_now()
        self._recompute_workflow(workflow)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="workflow_retried",
        )
        self._record_audit_event(
            state,
            entity_type="workflow",
            entity_id=workflow.id,
            action="retry",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Retried workflow '{workflow.title}'.",
            before=before,
            after=self._model_payload(workflow),
        )
        await self.save_state(state)
        return workflow

    async def add_workflow_task(
        self,
        *,
        workflow_id: str,
        title: str,
        description: str = "",
        stage: str | None = None,
        depends_on: list[str] | None = None,
        due_at: str | None = None,
        assignee: str = "agent",
        metadata: dict[str, Any] | None = None,
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        before = self._model_payload(workflow)
        stage_name = (stage or workflow.current_stage)
        if stage_name not in WORKFLOW_STAGES:
            raise ValueError(f"Unsupported workflow stage: {stage_name}")
        dependency_ids = _remove_empty_strings(depends_on or [])
        missing_dependencies = [
            dependency_id
            for dependency_id in dependency_ids
            if all(item.id != dependency_id for item in workflow.tasks)
        ]
        if missing_dependencies:
            raise ValueError(
                "Unknown workflow task dependencies: " + ", ".join(missing_dependencies),
            )
        task = WorkflowTask(
            stage=stage_name,  # type: ignore[arg-type]
            title=title,
            description=description,
            depends_on=dependency_ids,
            due_at=due_at,
            assignee=assignee,
            metadata=dict(metadata or {}),
        )
        workflow.tasks.append(task)
        stage_state = self._workflow_stage(workflow, task.stage)
        _append_unique(stage_state.task_ids, task.id)
        stage_state.updated_at = utc_now()
        self._touch(workflow)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="task_added",
            metadata={"task_id": task.id},
        )
        self._record_audit_event(
            state,
            entity_type="task",
            entity_id=task.id,
            action="create",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Added task '{task.title}' to workflow '{workflow.title}'.",
            before=before,
            after=self._model_payload(task),
        )
        await self.save_state(state)
        return workflow

    async def update_workflow_task(
        self,
        *,
        workflow_id: str,
        task_id: str,
        status: str | None = None,
        summary: str | None = None,
        due_at: str | None = None,
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        task = self._workflow_task(workflow, task_id)
        before = self._model_payload(task)
        if status in {"running", "completed"} and not self._task_dependencies_satisfied(
            workflow,
            task,
        ):
            raise ValueError(
                f"Task '{task.title}' cannot enter status '{status}' before dependencies complete.",
            )
        if status:
            task.status = status  # type: ignore[assignment]
            if status in {"completed", "cancelled"}:
                task.completed_at = utc_now()
        if summary is not None:
            task.summary = summary
        if due_at is not None:
            task.due_at = due_at
        for note_id in _remove_empty_strings(note_ids or []):
            _append_unique(task.note_ids, note_id)
            _append_unique(workflow.note_ids, note_id)
        for claim_id in _remove_empty_strings(claim_ids or []):
            _append_unique(task.claim_ids, claim_id)
            _append_unique(workflow.claim_ids, claim_id)
        for artifact_id in _remove_empty_strings(artifact_ids or []):
            _append_unique(task.artifact_ids, artifact_id)
            _append_unique(workflow.artifact_ids, artifact_id)
        task.updated_at = utc_now()
        self._recompute_workflow(workflow)
        self._record_workflow_checkpoint(
            state,
            workflow,
            reason="task_updated",
            metadata={"task_id": task.id},
        )
        self._record_audit_event(
            state,
            entity_type="task",
            entity_id=task.id,
            action="update",
            project_id=workflow.project_id,
            workflow_id=workflow.id,
            summary=f"Updated task '{task.title}' in workflow '{workflow.title}'.",
            before=before,
            after=self._model_payload(task),
        )
        await self.save_state(state)
        return workflow

    async def record_workflow_task_dispatch(
        self,
        *,
        workflow_id: str,
        task_id: str,
        summary: str,
        error: str = "",
    ) -> WorkflowTask:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        task = self._workflow_task(workflow, task_id)
        now = utc_now()
        task.dispatch_count += 1
        task.last_dispatch_at = now
        task.last_dispatch_summary = str(summary or "").strip()
        task.last_dispatch_error = str(error or "").strip()
        task.updated_at = now
        self._touch(workflow, now=now)
        await self.save_state(state)
        return task

    async def record_workflow_task_execution(
        self,
        *,
        workflow_id: str,
        task_id: str,
        summary: str,
        error: str = "",
    ) -> WorkflowTask:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        task = self._workflow_task(workflow, task_id)
        now = utc_now()
        task.execution_count += 1
        task.last_execution_at = now
        task.last_execution_summary = str(summary or "").strip()
        task.last_execution_error = str(error or "").strip()
        task.updated_at = now
        self._touch(workflow, now=now)
        await self.save_state(state)
        return task

    async def record_workflow_automation_run(
        self,
        *,
        workflow_id: str,
        run_id: str,
        summary: str = "",
        session_id: str = "",
        dispatches: list[dict[str, str]] | None = None,
    ) -> ResearchWorkflow:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        _append_unique(workflow.bindings.automation_run_ids, run_id)
        if session_id:
            workflow.bindings.session_id = session_id
        if dispatches:
            first = dispatches[0]
            workflow.bindings.channel = str(first.get("channel", "") or workflow.bindings.channel)
            workflow.bindings.user_id = str(first.get("user_id", "") or workflow.bindings.user_id)
            workflow.bindings.session_id = str(first.get("session_id", "") or workflow.bindings.session_id)
        if summary:
            workflow.bindings.last_summary = summary
        workflow.bindings.last_dispatch_at = utc_now()
        self._touch(workflow)
        await self.save_state(state)
        return workflow

    # ---- notes ----

    async def create_note(
        self,
        *,
        project_id: str,
        title: str,
        content: str,
        note_type: str = "idea_note",
        workflow_id: str = "",
        experiment_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        paper_refs: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchNote:
        state = await self.load_state()
        project = self._project(state, project_id)
        note = ResearchNote(
            project_id=project_id,
            title=title,
            content=content,
            note_type=note_type,  # type: ignore[arg-type]
            workflow_id=workflow_id,
            experiment_ids=_remove_empty_strings(experiment_ids or []),
            claim_ids=_remove_empty_strings(claim_ids or []),
            artifact_ids=_remove_empty_strings(artifact_ids or []),
            paper_refs=_remove_empty_strings(paper_refs or []),
            tags=_remove_empty_strings(tags or []),
            metadata=dict(metadata or {}),
        )
        state.notes.append(note)
        _append_unique(project.note_ids, note.id)
        for paper_ref in note.paper_refs:
            _append_unique(project.paper_refs, paper_ref)
        self._touch(project)

        if workflow_id:
            workflow = self._workflow(state, workflow_id)
            _append_unique(workflow.note_ids, note.id)
            self._touch(workflow)

        for experiment_id in note.experiment_ids:
            experiment = self._experiment(state, experiment_id)
            _append_unique(experiment.note_ids, note.id)
            self._touch(experiment)

        for claim_id in note.claim_ids:
            claim = self._claim(state, claim_id)
            _append_unique(claim.note_ids, note.id)
            self._touch(claim)

        for artifact_id in note.artifact_ids:
            artifact = self._artifact(state, artifact_id)
            _append_unique(artifact.note_ids, note.id)
            self._touch(artifact)

        if note.note_type == "decision_log":
            state.project_memory.append(
                ProjectMemoryEntry(
                    project_id=project_id,
                    workflow_id=workflow_id,
                    stage=workflow_id and self._workflow(state, workflow_id).current_stage or "",
                    title=note.title,
                    content=note.content,
                    entry_kind="decision",
                    note_ids=[note.id],
                    claim_ids=list(note.claim_ids),
                    artifact_ids=list(note.artifact_ids),
                    experiment_ids=list(note.experiment_ids),
                    tags=list(note.tags),
                    metadata={"source_note_type": note.note_type},
                ),
            )

        self._record_audit_event(
            state,
            entity_type="note",
            entity_id=note.id,
            action="create",
            project_id=note.project_id,
            workflow_id=note.workflow_id,
            summary=f"Created note '{note.title}'.",
            after=self._model_payload(note),
        )
        await self.save_state(state)
        return note

    async def update_note(
        self,
        *,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        note_type: str | None = None,
        workflow_id: str | None = None,
        experiment_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        paper_refs: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchNote:
        state = await self.load_state()
        note = self._note(state, note_id)
        before = self._model_payload(note)

        if title is not None:
            clean_title = str(title).strip()
            if not clean_title:
                raise ValueError("Note title cannot be empty.")
            note.title = clean_title
        if content is not None:
            clean_content = str(content).strip()
            if not clean_content:
                raise ValueError("Note content cannot be empty.")
            note.content = clean_content
        if note_type is not None:
            note.note_type = note_type  # type: ignore[assignment]
        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != note.project_id:
                    raise ValueError("Note workflow must belong to the same project.")
                _append_unique(workflow.note_ids, note.id)
                self._touch(workflow)
            note.workflow_id = clean_workflow_id
        if paper_refs is not None:
            note.paper_refs = _remove_empty_strings(paper_refs)
            project = self._project(state, note.project_id)
            for paper_ref in note.paper_refs:
                _append_unique(project.paper_refs, paper_ref)
            self._touch(project)
        if tags is not None:
            note.tags = _remove_empty_strings(tags)
        if metadata is not None:
            merged_metadata = dict(note.metadata)
            merged_metadata.update(dict(metadata))
            note.metadata = merged_metadata

        for experiment_id in _remove_empty_strings(experiment_ids or []):
            experiment = self._experiment(state, experiment_id)
            if experiment.project_id != note.project_id:
                raise ValueError("Note experiments must belong to the same project.")
            _append_unique(note.experiment_ids, experiment_id)
            _append_unique(experiment.note_ids, note.id)
            self._touch(experiment)

        for claim_id in _remove_empty_strings(claim_ids or []):
            claim = self._claim(state, claim_id)
            if claim.project_id != note.project_id:
                raise ValueError("Note claims must belong to the same project.")
            _append_unique(note.claim_ids, claim_id)
            _append_unique(claim.note_ids, note.id)
            self._touch(claim)

        for artifact_id in _remove_empty_strings(artifact_ids or []):
            artifact = self._artifact(state, artifact_id)
            if artifact.project_id != note.project_id:
                raise ValueError("Note artifacts must belong to the same project.")
            _append_unique(note.artifact_ids, artifact_id)
            _append_unique(artifact.note_ids, note.id)
            self._touch(artifact)

        self._touch(note)
        self._record_audit_event(
            state,
            entity_type="note",
            entity_id=note.id,
            action="update",
            project_id=note.project_id,
            workflow_id=note.workflow_id,
            summary=f"Updated note '{note.title}'.",
            before=before,
            after=self._model_payload(note),
        )
        await self.save_state(state)
        return note

    async def list_notes(
        self,
        *,
        query: str = "",
        note_type: str = "",
        tags: list[str] | None = None,
        project_id: str = "",
        workflow_id: str = "",
        claim_id: str = "",
        experiment_id: str = "",
        limit: int = 50,
    ) -> list[ResearchNote]:
        state = await self.load_state()
        notes = [
            note
            for note in state.notes
            if self._note_matches(
                note,
                query=query,
                note_type=note_type,
                tags=tags,
                project_id=project_id,
                workflow_id=workflow_id,
                claim_id=claim_id,
                experiment_id=experiment_id,
            )
        ]
        notes.sort(key=lambda item: item.updated_at, reverse=True)
        return notes[: max(1, int(limit))]

    async def bulk_update_notes(
        self,
        *,
        project_id: str,
        note_ids: list[str],
        workflow_id: str | None = None,
        note_type: str | None = None,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_note_ids = _remove_empty_strings(note_ids)
        add_tag_set = set(_remove_empty_strings(add_tags or []))
        remove_tag_set = set(_remove_empty_strings(remove_tags or []))
        metadata_patch_dict = dict(metadata_patch or {})
        if not cleaned_note_ids:
            raise ValueError("No note ids provided.")
        if (
            workflow_id is None
            and note_type is None
            and not add_tag_set
            and not remove_tag_set
            and not metadata_patch_dict
        ):
            raise ValueError("No note bulk update fields were provided.")

        updated_notes: list[ResearchNote] = []
        for note_id in cleaned_note_ids:
            note = self._note(state, note_id)
            if note.project_id != project_id:
                raise ValueError("Note bulk update must stay within one project.")
            next_tags = list(note.tags)
            if add_tag_set or remove_tag_set:
                next_tags = [
                    tag
                    for tag in next_tags
                    if tag not in remove_tag_set
                ]
                for tag in add_tag_set:
                    if tag not in next_tags:
                        next_tags.append(tag)
            next_metadata = dict(note.metadata)
            if metadata_patch_dict:
                next_metadata.update(metadata_patch_dict)
            updated_notes.append(
                await self.update_note(
                    note_id=note_id,
                    workflow_id=workflow_id,
                    note_type=note_type,
                    tags=next_tags if add_tag_set or remove_tag_set else None,
                    metadata=next_metadata if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_notes),
            "notes": updated_notes,
        }

    async def get_note_tag_counts(self, *, project_id: str = "") -> dict[str, int]:
        notes = await self.list_notes(project_id=project_id, limit=10_000)
        counts: dict[str, int] = {}
        for note in notes:
            for tag in note.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    # ---- artifacts ----

    async def list_artifacts(
        self,
        *,
        project_id: str = "",
        workflow_id: str = "",
        artifact_type: str = "",
        source_type: str = "",
        query: str = "",
        limit: int = 100,
    ) -> list[ResearchArtifact]:
        state = await self.load_state()
        artifacts = list(state.artifacts)
        if project_id:
            artifacts = [item for item in artifacts if item.project_id == project_id]
        if workflow_id:
            artifacts = [item for item in artifacts if item.workflow_id == workflow_id]
        if artifact_type:
            artifacts = [item for item in artifacts if item.artifact_type == artifact_type]
        if source_type:
            artifacts = [item for item in artifacts if item.source_type == source_type]
        if query:
            query_text = str(query).strip().lower()
            artifacts = [
                item
                for item in artifacts
                if query_text in item.title.lower()
                or query_text in item.description.lower()
                or query_text in item.source_type.lower()
                or query_text in item.source_id.lower()
            ]
        artifacts.sort(key=lambda item: item.updated_at or item.created_at, reverse=True)
        return artifacts[: max(1, int(limit))]

    async def update_artifact(
        self,
        *,
        artifact_id: str,
        title: str | None = None,
        artifact_type: str | None = None,
        workflow_id: str | None = None,
        description: str | None = None,
        path: str | None = None,
        uri: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        experiment_id: str | None = None,
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchArtifact:
        state = await self.load_state()
        artifact = self._artifact(state, artifact_id)
        before = self._model_payload(artifact)

        if title is not None:
            clean_title = str(title).strip()
            if not clean_title:
                raise ValueError("Artifact title cannot be empty.")
            artifact.title = clean_title
        if artifact_type is not None:
            artifact.artifact_type = artifact_type  # type: ignore[assignment]
        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != artifact.project_id:
                    raise ValueError("Artifact workflow must belong to the same project.")
                _append_unique(workflow.artifact_ids, artifact.id)
                stage = self._workflow_stage(workflow, workflow.current_stage)
                _append_unique(stage.artifact_ids, artifact.id)
                self._touch(workflow)
                stage.updated_at = utc_now()
            artifact.workflow_id = clean_workflow_id
        if description is not None:
            artifact.description = str(description or "").strip()
        if path is not None:
            artifact.path = str(path or "").strip()
        if uri is not None:
            artifact.uri = str(uri or "").strip()
        if source_type is not None:
            artifact.source_type = str(source_type or "").strip()
        if source_id is not None:
            artifact.source_id = str(source_id or "").strip()
        if experiment_id is not None:
            clean_experiment_id = str(experiment_id or "").strip()
            if clean_experiment_id:
                experiment = self._experiment(state, clean_experiment_id)
                if experiment.project_id != artifact.project_id:
                    raise ValueError("Artifact experiment must belong to the same project.")
                _append_unique(experiment.artifact_ids, artifact.id)
                self._touch(experiment)
            artifact.experiment_id = clean_experiment_id
        for note_id in _remove_empty_strings(note_ids or []):
            note = self._note(state, note_id)
            if note.project_id != artifact.project_id:
                raise ValueError("Artifact notes must belong to the same project.")
            _append_unique(artifact.note_ids, note_id)
            _append_unique(note.artifact_ids, artifact.id)
            self._touch(note)
        for claim_id in _remove_empty_strings(claim_ids or []):
            claim = self._claim(state, claim_id)
            if claim.project_id != artifact.project_id:
                raise ValueError("Artifact claims must belong to the same project.")
            _append_unique(artifact.claim_ids, claim_id)
            _append_unique(claim.artifact_ids, artifact.id)
            self._touch(claim)
        if metadata is not None:
            merged_metadata = dict(artifact.metadata)
            merged_metadata.update(dict(metadata))
            artifact.metadata = merged_metadata

        self._touch(artifact)
        self._record_audit_event(
            state,
            entity_type="artifact",
            entity_id=artifact.id,
            action="update",
            project_id=artifact.project_id,
            workflow_id=artifact.workflow_id,
            summary=f"Updated artifact '{artifact.title}'.",
            before=before,
            after=self._model_payload(artifact),
        )
        await self.save_state(state)
        return artifact

    async def bulk_update_artifacts(
        self,
        *,
        project_id: str,
        artifact_ids: list[str],
        workflow_id: str | None = None,
        source_type: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_artifact_ids = _remove_empty_strings(artifact_ids)
        if not cleaned_artifact_ids:
            raise ValueError("No artifact ids provided.")
        if workflow_id is None and source_type is None and not dict(metadata_patch or {}):
            raise ValueError("No artifact bulk update fields were provided.")

        updated_artifacts: list[ResearchArtifact] = []
        metadata_patch_dict = dict(metadata_patch or {})
        for artifact_id in cleaned_artifact_ids:
            artifact = self._artifact(state, artifact_id)
            if artifact.project_id != project_id:
                raise ValueError("Artifact bulk update must stay within one project.")
            updated_artifacts.append(
                await self.update_artifact(
                    artifact_id=artifact_id,
                    workflow_id=workflow_id,
                    source_type=source_type,
                    metadata=metadata_patch_dict if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_artifacts),
            "artifacts": updated_artifacts,
        }

    async def upsert_artifact(
        self,
        *,
        project_id: str,
        title: str,
        artifact_type: str,
        workflow_id: str = "",
        description: str = "",
        path: str = "",
        uri: str = "",
        source_type: str = "",
        source_id: str = "",
        experiment_id: str = "",
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchArtifact:
        state = await self.load_state()
        self._project(state, project_id)
        candidate: ResearchArtifact | None = None
        normalized_title = str(title or "").strip().lower()

        for item in state.artifacts:
            if item.project_id != project_id:
                continue
            if item.artifact_type != artifact_type:
                continue
            if source_id and item.source_type == source_type and item.source_id == source_id:
                candidate = item
                break
            if uri and item.uri == uri:
                candidate = item
                break
            if path and item.path == path:
                candidate = item
                break
            if (
                normalized_title
                and artifact_type == "paper"
                and item.title.strip().lower() == normalized_title
            ):
                candidate = item
                break

        if candidate is None:
            artifact = self._add_artifact_to_state(
                state,
                project_id=project_id,
                workflow_id=workflow_id,
                title=title,
                artifact_type=artifact_type,  # type: ignore[arg-type]
                description=description,
                path=path,
                uri=uri,
                source_type=source_type,
                source_id=source_id,
                experiment_id=experiment_id,
                note_ids=note_ids,
                claim_ids=claim_ids,
                metadata=metadata,
            )
            self._record_audit_event(
                state,
                entity_type="artifact",
                entity_id=artifact.id,
                action="create",
                project_id=artifact.project_id,
                workflow_id=artifact.workflow_id,
                summary=f"Created artifact '{artifact.title}'.",
                after=self._model_payload(artifact),
            )
            await self.save_state(state)
            return artifact

        before = self._model_payload(candidate)
        if title:
            candidate.title = title
        if description:
            candidate.description = description
        if path:
            candidate.path = path
        if uri:
            candidate.uri = uri
        if source_type:
            candidate.source_type = source_type
        if source_id:
            candidate.source_id = source_id
        if experiment_id:
            candidate.experiment_id = experiment_id
        if workflow_id and not candidate.workflow_id:
            candidate.workflow_id = workflow_id
        if metadata:
            merged_metadata = dict(candidate.metadata)
            merged_metadata.update(dict(metadata))
            candidate.metadata = merged_metadata

        project = self._project(state, project_id)
        _append_unique(project.artifact_ids, candidate.id)
        self._touch(project)

        if workflow_id:
            workflow = self._workflow(state, workflow_id)
            _append_unique(workflow.artifact_ids, candidate.id)
            stage = self._workflow_stage(workflow, workflow.current_stage)
            _append_unique(stage.artifact_ids, candidate.id)
            stage.updated_at = utc_now()
            self._touch(workflow)

        for note_id in _remove_empty_strings(note_ids or []):
            _append_unique(candidate.note_ids, note_id)
            note = self._note(state, note_id)
            _append_unique(note.artifact_ids, candidate.id)
            self._touch(note)

        for claim_id in _remove_empty_strings(claim_ids or []):
            _append_unique(candidate.claim_ids, claim_id)
            claim = self._claim(state, claim_id)
            _append_unique(claim.artifact_ids, candidate.id)
            self._touch(claim)

        self._touch(candidate)
        self._record_audit_event(
            state,
            entity_type="artifact",
            entity_id=candidate.id,
            action="update",
            project_id=candidate.project_id,
            workflow_id=candidate.workflow_id,
            summary=f"Updated artifact '{candidate.title}'.",
            before=before,
            after=self._model_payload(candidate),
        )
        await self.save_state(state)
        return candidate

    # ---- claims / evidences ----

    async def create_claim(
        self,
        *,
        project_id: str,
        text: str,
        workflow_id: str = "",
        status: str = "draft",
        confidence: float | None = None,
        note_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchClaim:
        state = await self.load_state()
        project = self._project(state, project_id)
        claim = ResearchClaim(
            project_id=project_id,
            text=text,
            workflow_id=workflow_id,
            status=status,  # type: ignore[arg-type]
            confidence=confidence,
            note_ids=_remove_empty_strings(note_ids or []),
            artifact_ids=_remove_empty_strings(artifact_ids or []),
            metadata=dict(metadata or {}),
        )
        state.claims.append(claim)
        _append_unique(project.claim_ids, claim.id)
        self._touch(project)

        if workflow_id:
            workflow = self._workflow(state, workflow_id)
            _append_unique(workflow.claim_ids, claim.id)
            self._touch(workflow)

        for note_id in claim.note_ids:
            note = self._note(state, note_id)
            _append_unique(note.claim_ids, claim.id)
            self._touch(note)

        for artifact_id in claim.artifact_ids:
            artifact = self._artifact(state, artifact_id)
            _append_unique(artifact.claim_ids, claim.id)
            self._touch(artifact)

        self._record_audit_event(
            state,
            entity_type="claim",
            entity_id=claim.id,
            action="create",
            project_id=claim.project_id,
            workflow_id=claim.workflow_id,
            summary=f"Created claim '{claim.text[:72]}'.",
            after=self._model_payload(claim),
        )
        await self.save_state(state)
        return claim

    async def list_claims(
        self,
        *,
        project_id: str = "",
        workflow_id: str = "",
        status: str = "",
        query: str = "",
        has_evidence: bool | None = None,
        limit: int = 100,
    ) -> list[ResearchClaim]:
        state = await self.load_state()
        claims = list(state.claims)
        if project_id:
            claims = [item for item in claims if item.project_id == project_id]
        if workflow_id:
            claims = [item for item in claims if item.workflow_id == workflow_id]
        if status:
            claims = [item for item in claims if item.status == status]
        if query:
            query_text = str(query).strip().lower()
            claims = [item for item in claims if query_text in item.text.lower()]
        if has_evidence is not None:
            claims = [
                item
                for item in claims
                if (len(item.evidence_ids) > 0) is bool(has_evidence)
            ]
        claims.sort(key=lambda item: item.updated_at, reverse=True)
        return claims[: max(1, int(limit))]

    async def update_claim(
        self,
        *,
        claim_id: str,
        text: str | None = None,
        status: str | None = None,
        workflow_id: str | None = None,
        confidence: float | None = None,
        note_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchClaim:
        state = await self.load_state()
        claim = self._claim(state, claim_id)
        before = self._model_payload(claim)

        if text is not None:
            claim.text = text
        if status:
            claim.status = status  # type: ignore[assignment]
        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != claim.project_id:
                    raise ValueError("Claim workflow must belong to the same project.")
                _append_unique(workflow.claim_ids, claim.id)
                self._touch(workflow)
            claim.workflow_id = clean_workflow_id
        if confidence is not None:
            claim.confidence = confidence
        if metadata:
            merged_metadata = dict(claim.metadata)
            merged_metadata.update(dict(metadata))
            claim.metadata = merged_metadata

        for note_id in _remove_empty_strings(note_ids or []):
            _append_unique(claim.note_ids, note_id)
            note = self._note(state, note_id)
            _append_unique(note.claim_ids, claim.id)
            self._touch(note)

        for artifact_id in _remove_empty_strings(artifact_ids or []):
            _append_unique(claim.artifact_ids, artifact_id)
            artifact = self._artifact(state, artifact_id)
            _append_unique(artifact.claim_ids, claim.id)
            self._touch(artifact)

        if claim.workflow_id:
            workflow = self._workflow(state, claim.workflow_id)
            _append_unique(workflow.claim_ids, claim.id)
            self._touch(workflow)

        self._touch(claim)
        self._record_audit_event(
            state,
            entity_type="claim",
            entity_id=claim.id,
            action="update",
            project_id=claim.project_id,
            workflow_id=claim.workflow_id,
            summary=f"Updated claim '{claim.text[:72]}'.",
            before=before,
            after=self._model_payload(claim),
        )
        await self.save_state(state)
        return claim

    async def bulk_update_claims(
        self,
        *,
        project_id: str,
        claim_ids: list[str],
        status: str | None = None,
        workflow_id: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_claim_ids = _remove_empty_strings(claim_ids)
        if not cleaned_claim_ids:
            raise ValueError("No claim ids provided.")
        if status is None and workflow_id is None and not dict(metadata_patch or {}):
            raise ValueError("No claim bulk update fields were provided.")

        updated_claims: list[ResearchClaim] = []
        metadata_patch_dict = dict(metadata_patch or {})
        for claim_id in cleaned_claim_ids:
            claim = self._claim(state, claim_id)
            if claim.project_id != project_id:
                raise ValueError("Claim bulk update must stay within one project.")
            updated_claims.append(
                await self.update_claim(
                    claim_id=claim_id,
                    status=status,
                    workflow_id=workflow_id,
                    metadata=metadata_patch_dict if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_claims),
            "claims": updated_claims,
        }

    async def attach_evidence(
        self,
        *,
        project_id: str,
        claim_ids: list[str],
        evidence_type: str,
        summary: str,
        source_type: str,
        source_id: str = "",
        title: str = "",
        locator: str = "",
        quote: str = "",
        url: str = "",
        workflow_id: str = "",
        artifact_id: str = "",
        note_id: str = "",
        experiment_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ResearchEvidence:
        state = await self.load_state()
        self._project(state, project_id)
        evidence = self._add_evidence_to_state(
            state,
            project_id=project_id,
            evidence_type=evidence_type,  # type: ignore[arg-type]
            summary=summary,
            claim_ids=_remove_empty_strings(claim_ids),
            workflow_id=workflow_id,
            artifact_id=artifact_id,
            note_id=note_id,
            experiment_id=experiment_id,
            source=EvidenceSource(
                source_type=source_type,  # type: ignore[arg-type]
                source_id=source_id,
                title=title,
                locator=locator,
                quote=quote,
                url=url,
                metadata=dict(metadata or {}),
            ),
            metadata=dict(metadata or {}),
        )
        self._record_audit_event(
            state,
            entity_type="evidence",
            entity_id=evidence.id,
            action="attach",
            project_id=evidence.project_id,
            workflow_id=evidence.workflow_id,
            summary=f"Attached evidence '{evidence.summary[:72]}' to {len(evidence.claim_ids)} claim(s).",
            after=self._model_payload(evidence),
        )
        await self.save_state(state)
        return evidence

    async def list_evidences(
        self,
        *,
        project_id: str = "",
        workflow_id: str = "",
        claim_id: str = "",
        evidence_type: str = "",
        source_type: str = "",
        query: str = "",
        limit: int = 100,
    ) -> list[ResearchEvidence]:
        state = await self.load_state()
        evidences = list(state.evidences)
        if project_id:
            evidences = [item for item in evidences if item.project_id == project_id]
        if workflow_id:
            evidences = [item for item in evidences if item.workflow_id == workflow_id]
        if claim_id:
            evidences = [item for item in evidences if claim_id in item.claim_ids]
        if evidence_type:
            evidences = [item for item in evidences if item.evidence_type == evidence_type]
        if source_type:
            evidences = [
                item
                for item in evidences
                if item.source.source_type == source_type
            ]
        if query:
            query_text = str(query).strip().lower()
            evidences = [
                item
                for item in evidences
                if query_text in item.summary.lower()
                or query_text in item.source.title.lower()
                or query_text in item.source.source_id.lower()
                or query_text in item.source.locator.lower()
                or query_text in item.source.quote.lower()
            ]
        evidences.sort(key=lambda item: item.updated_at, reverse=True)
        return evidences[: max(1, int(limit))]

    async def update_evidence(
        self,
        *,
        evidence_id: str,
        summary: str | None = None,
        evidence_type: str | None = None,
        workflow_id: str | None = None,
        claim_ids: list[str] | None = None,
        artifact_id: str | None = None,
        note_id: str | None = None,
        experiment_id: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        title: str | None = None,
        locator: str | None = None,
        quote: str | None = None,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResearchEvidence:
        state = await self.load_state()
        evidence = next(
            (item for item in state.evidences if item.id == evidence_id),
            None,
        )
        if evidence is None:
            raise ValueError(f"Evidence '{evidence_id}' not found.")
        before = self._model_payload(evidence)

        if summary is not None:
            clean_summary = str(summary).strip()
            if not clean_summary:
                raise ValueError("Evidence summary cannot be empty.")
            evidence.summary = clean_summary
        if evidence_type is not None:
            evidence.evidence_type = evidence_type  # type: ignore[assignment]
        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != evidence.project_id:
                    raise ValueError("Evidence workflow must belong to the same project.")
            evidence.workflow_id = clean_workflow_id

        for claim_id in _remove_empty_strings(claim_ids or []):
            claim = self._claim(state, claim_id)
            if claim.project_id != evidence.project_id:
                raise ValueError("Evidence claims must belong to the same project.")
            _append_unique(evidence.claim_ids, claim_id)
            _append_unique(claim.evidence_ids, evidence.id)
            self._touch(claim)

        if artifact_id is not None:
            clean_artifact_id = str(artifact_id or "").strip()
            if clean_artifact_id:
                artifact = self._artifact(state, clean_artifact_id)
                if artifact.project_id != evidence.project_id:
                    raise ValueError("Evidence artifact must belong to the same project.")
                _append_unique(artifact.evidence_ids, evidence.id)
                self._touch(artifact)
            evidence.artifact_id = clean_artifact_id

        if note_id is not None:
            clean_note_id = str(note_id or "").strip()
            if clean_note_id:
                note = self._note(state, clean_note_id)
                if note.project_id != evidence.project_id:
                    raise ValueError("Evidence note must belong to the same project.")
                _append_unique(note.evidence_ids, evidence.id)
                self._touch(note)
            evidence.note_id = clean_note_id

        if experiment_id is not None:
            clean_experiment_id = str(experiment_id or "").strip()
            if clean_experiment_id:
                experiment = self._experiment(state, clean_experiment_id)
                if experiment.project_id != evidence.project_id:
                    raise ValueError("Evidence experiment must belong to the same project.")
                _append_unique(experiment.evidence_ids, evidence.id)
                self._touch(experiment)
            evidence.experiment_id = clean_experiment_id

        if source_type is not None:
            evidence.source.source_type = source_type  # type: ignore[assignment]
        if source_id is not None:
            evidence.source.source_id = str(source_id or "").strip()
        if title is not None:
            evidence.source.title = str(title or "").strip()
        if locator is not None:
            evidence.source.locator = str(locator or "").strip()
        if quote is not None:
            evidence.source.quote = str(quote or "").strip()
        if url is not None:
            evidence.source.url = str(url or "").strip()
        if metadata is not None:
            merged_metadata = dict(evidence.metadata)
            merged_metadata.update(dict(metadata))
            evidence.metadata = merged_metadata
            source_metadata = dict(evidence.source.metadata)
            source_metadata.update(dict(metadata))
            evidence.source.metadata = source_metadata

        self._touch(evidence)
        self._record_audit_event(
            state,
            entity_type="evidence",
            entity_id=evidence.id,
            action="update",
            project_id=evidence.project_id,
            workflow_id=evidence.workflow_id,
            summary=f"Updated evidence '{evidence.summary[:72]}'.",
            before=before,
            after=self._model_payload(evidence),
        )
        await self.save_state(state)
        return evidence

    async def bulk_update_evidences(
        self,
        *,
        project_id: str,
        evidence_ids: list[str],
        workflow_id: str | None = None,
        evidence_type: str | None = None,
        source_type: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_evidence_ids = _remove_empty_strings(evidence_ids)
        metadata_patch_dict = dict(metadata_patch or {})
        if not cleaned_evidence_ids:
            raise ValueError("No evidence ids provided.")
        if (
            workflow_id is None
            and evidence_type is None
            and source_type is None
            and not metadata_patch_dict
        ):
            raise ValueError("No evidence bulk update fields were provided.")

        updated_evidences: list[ResearchEvidence] = []
        for evidence_id in cleaned_evidence_ids:
            evidence = next(
                (item for item in state.evidences if item.id == evidence_id),
                None,
            )
            if evidence is None:
                raise ValueError(f"Evidence '{evidence_id}' not found.")
            if evidence.project_id != project_id:
                raise ValueError("Evidence bulk update must stay within one project.")
            updated_evidences.append(
                await self.update_evidence(
                    evidence_id=evidence_id,
                    workflow_id=workflow_id,
                    evidence_type=evidence_type,
                    source_type=source_type,
                    metadata=metadata_patch_dict if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_evidences),
            "evidences": updated_evidences,
        }

    async def get_claim_graph(self, claim_id: str) -> dict[str, Any]:
        state = await self.load_state()
        claim = self._claim(state, claim_id)
        evidences = [
            item for item in state.evidences if item.id in set(claim.evidence_ids)
        ]
        notes = [item for item in state.notes if item.id in set(claim.note_ids)]
        artifacts = [
            item for item in state.artifacts if item.id in set(claim.artifact_ids)
        ]
        experiments = [
            item
            for item in state.experiments
            if claim.id in set(item.claim_ids) or any(
                evidence.experiment_id == item.id for evidence in evidences
            )
        ]
        workflow = (
            self._workflow(state, claim.workflow_id)
            if claim.workflow_id
            else None
        )
        project = self._project(state, claim.project_id)
        return {
            "project": project,
            "workflow": workflow,
            "claim": claim,
            "evidences": evidences,
            "notes": notes,
            "artifacts": artifacts,
            "experiments": experiments,
        }

    # ---- experiments ----

    async def get_experiment(self, experiment_id: str) -> ExperimentRun:
        state = await self.load_state()
        return self._experiment(state, experiment_id)

    async def capture_experiment_provenance(
        self,
        *,
        experiment_id: str,
        command: list[str] | None = None,
        working_dir: str = "",
        environment_keys: list[str] | None = None,
        dependency_fingerprint: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRun:
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        before = self._model_payload(experiment)
        base_dir = self._storage_root()
        effective_working_dir = (
            Path(working_dir).expanduser().resolve()
            if str(working_dir or "").strip()
            else (
                Path(str(experiment.execution.working_dir)).expanduser().resolve()
                if str(experiment.execution.working_dir or "").strip()
                else Path.cwd().resolve()
            )
        )
        dataset_paths: list[str] = []
        for dataset_version_id in experiment.dataset_version_ids:
            try:
                dataset_version = self._dataset_version(state, dataset_version_id)
            except ValueError:
                continue
            dataset_paths.extend(dataset_version.source_paths)
            if dataset_version.path:
                dataset_paths.append(dataset_version.path)
        output_hashes = self._hash_existing_paths(
            experiment.output_files,
            base_dir=base_dir,
        )
        input_hashes = self._hash_existing_paths(
            dataset_paths,
            base_dir=base_dir,
        )
        fingerprint = dict(dependency_fingerprint or {})
        if not fingerprint:
            fingerprint["python"] = os.sys.version.split()[0]
            for candidate_name in ["requirements.txt", "pyproject.toml", "poetry.lock", "uv.lock"]:
                candidate = effective_working_dir / candidate_name
                if candidate.is_file():
                    fingerprint[candidate_name] = self._hash_file(candidate)
        experiment.provenance = ExperimentProvenance(
            captured_at=utc_now(),
            git_commit=self._git_output("rev-parse", "HEAD", cwd=effective_working_dir),
            git_branch=self._git_output(
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                cwd=effective_working_dir,
            ),
            git_dirty=bool(
                self._git_output("status", "--porcelain", cwd=effective_working_dir),
            ),
            git_diff_summary=self._git_output(
                "diff",
                "--stat",
                cwd=effective_working_dir,
            ),
            cwd=str(effective_working_dir),
            command=list(command or experiment.execution.command or experiment.provenance.command),
            environment_keys=sorted(
                {
                    *list(environment_keys or []),
                    *list(experiment.execution.environment.keys()),
                    *list(experiment.provenance.environment_keys),
                },
            ),
            dependency_fingerprint=fingerprint,
            dataset_version_ids=list(experiment.dataset_version_ids),
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            replayable=bool(
                command
                or experiment.execution.command
                or experiment.execution.entrypoint
                or experiment.execution.notebook_path
            ),
            metadata={
                **dict(experiment.provenance.metadata),
                **dict(metadata or {}),
            },
        )
        self._touch(experiment)
        self._record_audit_event(
            state,
            entity_type="experiment",
            entity_id=experiment.id,
            action="capture_provenance",
            project_id=experiment.project_id,
            workflow_id=experiment.workflow_id,
            summary=f"Captured provenance for experiment '{experiment.name}'.",
            before=before,
            after=self._model_payload(experiment),
        )
        await self.save_state(state)
        return experiment

    async def get_experiment_replay_plan(self, experiment_id: str) -> dict[str, Any]:
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        if not experiment.provenance.replayable:
            raise ValueError(f"Experiment {experiment_id} is not replayable.")
        datasets = [
            self._dataset_version(state, dataset_version_id)
            for dataset_version_id in experiment.dataset_version_ids
            if any(item.id == dataset_version_id for item in state.dataset_versions)
        ]
        return {
            "experiment": experiment,
            "execution_mode": experiment.execution.mode,
            "command": list(experiment.provenance.command or experiment.execution.command),
            "entrypoint": experiment.execution.entrypoint,
            "notebook_path": experiment.execution.notebook_path,
            "working_dir": experiment.provenance.cwd or experiment.execution.working_dir,
            "environment_keys": list(experiment.provenance.environment_keys),
            "dataset_versions": datasets,
            "dependency_fingerprint": dict(experiment.provenance.dependency_fingerprint),
            "input_hashes": dict(experiment.provenance.input_hashes),
            "output_hashes": dict(experiment.provenance.output_hashes),
        }

    async def get_experiment_artifact_contract_validation(
        self,
        experiment_id: str,
    ) -> dict[str, Any]:
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        validation = self._evaluate_experiment_artifact_contract(state, experiment)
        existing = dict(experiment.metadata).get("contract_validation")
        existing_without_timestamp = (
            {
                key: value
                for key, value in dict(existing).items()
                if key != "validated_at"
            }
            if isinstance(existing, dict)
            else None
        )
        current_without_timestamp = {
            key: value
            for key, value in validation.items()
            if key != "validated_at"
        }
        if existing_without_timestamp == current_without_timestamp:
            return dict(existing)
        if dict(experiment.metadata).get("contract_validation") != validation:
            experiment.metadata = {
                **dict(experiment.metadata),
                "contract_validation": validation,
            }
            self._touch(experiment)
            await self.save_state(state)
        return validation

    async def get_experiment_contract_remediation(
        self,
        experiment_id: str,
    ) -> dict[str, Any]:
        validation = await self.get_experiment_artifact_contract_validation(
            experiment_id,
        )
        remediation = validation.get("remediation")
        if isinstance(remediation, dict):
            return remediation
        return {
            "required": False,
            "summary": "No remediation actions are required.",
            "actions": [],
            "action_count": 0,
        }

    async def get_workflow_contract_remediation_context(
        self,
        workflow_id: str,
    ) -> dict[str, Any]:
        state = await self.load_state()
        workflow = self._workflow(state, workflow_id)
        return self._workflow_contract_followup_context(state, workflow)

    async def configure_experiment_execution(
        self,
        *,
        experiment_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        before = self._model_payload(experiment)
        before_mode = experiment.execution.mode
        experiment.execution = self._merge_experiment_execution(
            base=experiment.execution,
            patch=patch,
        )
        schema_name = str(experiment.execution.result_bundle_schema or "").strip()
        if schema_name:
            schema_contract = self._result_bundle_schema_contract(
                self._project_result_bundle_schema(
                    state,
                    project_id=experiment.project_id,
                    schema_name=schema_name,
                ),
            )
            if schema_contract:
                execution_metadata = dict(experiment.execution.metadata)
                execution_metadata["artifact_contract"] = self._merge_contract_dicts(
                    schema_contract,
                    execution_metadata.get("artifact_contract")
                    if isinstance(execution_metadata.get("artifact_contract"), dict)
                    else None,
                )
                experiment.execution.metadata = execution_metadata
        now = utc_now()
        if experiment.execution.mode != "inline" and not experiment.execution.submitted_at:
            experiment.execution.submitted_at = now
        event = self._add_experiment_event_to_state(
            state,
            experiment=experiment,
            event_type="binding",
            summary=(
                f"Configured experiment execution mode "
                f"{before_mode} -> {experiment.execution.mode}."
            ),
            metadata={
                "patch": patch,
                "before_mode": before_mode,
                "after_mode": experiment.execution.mode,
                "external_run_id": experiment.execution.external_run_id,
            },
        )
        experiment.provenance.command = list(
            experiment.execution.command or experiment.provenance.command,
        )
        if experiment.execution.working_dir:
            experiment.provenance.cwd = experiment.execution.working_dir
        experiment.provenance.environment_keys = sorted(
            set(experiment.provenance.environment_keys)
            | set(experiment.execution.environment.keys()),
        )
        self._touch(experiment, now=now)
        self._record_audit_event(
            state,
            entity_type="experiment",
            entity_id=experiment.id,
            action="configure_execution",
            project_id=experiment.project_id,
            workflow_id=experiment.workflow_id,
            summary=(
                f"Configured experiment '{experiment.name}' execution "
                f"{before_mode} -> {experiment.execution.mode}."
            ),
            before=before,
            after=self._model_payload(experiment),
        )
        await self.save_state(state)
        return {
            "experiment": experiment,
            "event": event,
        }

    async def list_experiment_events(
        self,
        *,
        experiment_id: str,
        limit: int = 100,
    ) -> list[ExperimentEvent]:
        state = await self.load_state()
        rows = [
            item
            for item in state.experiment_events
            if item.experiment_id == experiment_id
        ]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows[: max(1, int(limit))]

    async def record_experiment_heartbeat(
        self,
        *,
        experiment_id: str,
        summary: str,
        status: str = "running",
        metrics: dict[str, Any] | None = None,
        output_files: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_status = str(status or "running").strip() or "running"
        experiment = await self.update_experiment(
            experiment_id=experiment_id,
            status=normalized_status,
            metrics=metrics,
            output_files=output_files,
            metadata=metadata,
        )
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        now = utc_now()
        if not experiment.execution.submitted_at:
            experiment.execution.submitted_at = now
        experiment.execution.last_heartbeat_at = now
        event = self._add_experiment_event_to_state(
            state,
            experiment=experiment,
            event_type="heartbeat",
            summary=summary,
            status=experiment.status,
            metrics=metrics,
            output_files=output_files,
            artifact_ids=experiment.artifact_ids,
            metadata=metadata,
        )
        self._touch(experiment, now=now)
        await self.save_state(state)
        return {
            "experiment": experiment,
            "event": event,
        }

    async def record_experiment_result(
        self,
        *,
        experiment_id: str,
        summary: str = "",
        status: str = "completed",
        metrics: dict[str, Any] | None = None,
        output_files: list[str] | None = None,
        notes: str | None = None,
        note_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_status = str(status or "completed").strip() or "completed"
        experiment = await self.update_experiment(
            experiment_id=experiment_id,
            status=normalized_status,
            metrics=metrics,
            output_files=output_files,
            notes=notes,
            note_ids=note_ids,
            claim_ids=claim_ids,
            metadata=metadata,
        )
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        now = utc_now()
        if not experiment.execution.submitted_at:
            experiment.execution.submitted_at = now
        experiment.execution.last_heartbeat_at = now
        contract_validation = self._store_experiment_artifact_contract_validation(
            state,
            experiment,
        )
        event_type = "completion"
        if experiment.status in {"failed", "cancelled"}:
            event_type = "failure"
        elif experiment.status not in {"completed"}:
            event_type = "status"
        event = self._add_experiment_event_to_state(
            state,
            experiment=experiment,
            event_type=event_type,
            summary=summary or f"Experiment {experiment.name} updated to {experiment.status}.",
            status=experiment.status,
            metrics=metrics,
            output_files=output_files,
            note_ids=note_ids,
            artifact_ids=experiment.artifact_ids,
            metadata={
                **dict(metadata or {}),
                "contract_validation": contract_validation,
            },
        )
        self._touch(experiment, now=now)
        await self.save_state(state)
        return {
            "experiment": experiment,
            "event": event,
        }

    @staticmethod
    def _experiment_summary_parts(experiment: ExperimentRun) -> list[str]:
        summary_parts: list[str] = []
        if experiment.metrics:
            metric_preview = ", ".join(
                f"{key}={value}" for key, value in sorted(experiment.metrics.items())
            )
            summary_parts.append(f"Metrics: {metric_preview}")
        if experiment.output_files:
            summary_parts.append(
                "Outputs: "
                + ", ".join(Path(path).name or path for path in experiment.output_files[:5]),
            )
        return summary_parts

    def _sync_experiment_output_artifacts(
        self,
        state: ResearchState,
        experiment: ExperimentRun,
    ) -> None:
        project = self._project(state, experiment.project_id)
        workflow = (
            self._workflow(state, experiment.workflow_id)
            if experiment.workflow_id
            else None
        )

        for output_file in experiment.output_files:
            artifact = next(
                (
                    item
                    for item in state.artifacts
                    if item.experiment_id == experiment.id and item.path == output_file
                ),
                None,
            )
            if artifact is None:
                artifact = self._add_artifact_to_state(
                    state,
                    project_id=experiment.project_id,
                    workflow_id=experiment.workflow_id,
                    title=Path(output_file).name or output_file,
                    artifact_type=_artifact_type_from_path(output_file),
                    description=f"Archived output for experiment {experiment.name}",
                    path=output_file,
                    source_type="experiment",
                    source_id=experiment.id,
                    experiment_id=experiment.id,
                    claim_ids=experiment.claim_ids,
                )
            else:
                artifact.title = Path(output_file).name or output_file
                artifact.description = f"Archived output for experiment {experiment.name}"
                artifact.path = output_file
                artifact.source_type = "experiment"
                artifact.source_id = experiment.id
                artifact.experiment_id = experiment.id
                if experiment.workflow_id and not artifact.workflow_id:
                    artifact.workflow_id = experiment.workflow_id
                _append_unique(project.artifact_ids, artifact.id)
                self._touch(project)
                if workflow is not None:
                    _append_unique(workflow.artifact_ids, artifact.id)
                    stage = self._workflow_stage(workflow, workflow.current_stage)
                    _append_unique(stage.artifact_ids, artifact.id)
                    stage.updated_at = utc_now()
                    self._touch(workflow)
                self._touch(artifact)

            for claim_id in experiment.claim_ids:
                claim = self._claim(state, claim_id)
                _append_unique(artifact.claim_ids, claim_id)
                _append_unique(claim.artifact_ids, artifact.id)
                self._touch(claim)
            _append_unique(experiment.artifact_ids, artifact.id)

    def _sync_experiment_completion_evidence(
        self,
        state: ResearchState,
        experiment: ExperimentRun,
    ) -> None:
        if experiment.status != "completed":
            return
        if not experiment.claim_ids:
            return
        summary_parts = self._experiment_summary_parts(experiment)
        if not summary_parts:
            return

        summary = f"{experiment.name}: {'; '.join(summary_parts)}"
        evidence = next(
            (
                item
                for item in state.evidences
                if item.experiment_id == experiment.id
                and item.source.source_type == "experiment_result"
                and item.source.source_id == experiment.id
            ),
            None,
        )
        if evidence is None:
            self._add_evidence_to_state(
                state,
                project_id=experiment.project_id,
                evidence_type="experiment_result",
                summary=summary,
                claim_ids=experiment.claim_ids,
                workflow_id=experiment.workflow_id,
                experiment_id=experiment.id,
                source=EvidenceSource(
                    source_type="experiment_result",
                    source_id=experiment.id,
                    title=experiment.name,
                    locator="metrics",
                    quote=experiment.notes[:280],
                    metadata={"metrics": experiment.metrics},
                ),
                metadata={"experiment_id": experiment.id},
            )
            return

        evidence.summary = summary
        evidence.workflow_id = evidence.workflow_id or experiment.workflow_id
        evidence.source.title = experiment.name
        evidence.source.locator = "metrics"
        evidence.source.quote = experiment.notes[:280]
        evidence.source.metadata = {"metrics": experiment.metrics}
        merged_metadata = dict(evidence.metadata)
        merged_metadata.update({"experiment_id": experiment.id})
        evidence.metadata = merged_metadata
        for claim_id in experiment.claim_ids:
            _append_unique(evidence.claim_ids, claim_id)
            claim = self._claim(state, claim_id)
            _append_unique(claim.evidence_ids, evidence.id)
            self._touch(claim)
        _append_unique(experiment.evidence_ids, evidence.id)
        self._touch(evidence)

    def _experiment_artifact_contract(
        self,
        state: ResearchState,
        experiment: ExperimentRun,
    ) -> dict[str, Any]:
        execution_metadata = dict(getattr(experiment.execution, "metadata", {}) or {})
        schema_name = str(
            getattr(experiment.execution, "result_bundle_schema", "")
            or execution_metadata.get("result_bundle_schema", ""),
        ).strip()
        schema_contract = self._result_bundle_schema_contract(
            self._project_result_bundle_schema(
                state,
                project_id=experiment.project_id,
                schema_name=schema_name,
            ),
        )
        execution_contract = execution_metadata.get("artifact_contract")
        experiment_metadata = dict(getattr(experiment, "metadata", {}) or {})
        experiment_contract = experiment_metadata.get("artifact_contract")
        return self._merge_contract_dicts(
            schema_contract,
            execution_contract if isinstance(execution_contract, dict) else None,
            experiment_contract if isinstance(experiment_contract, dict) else None,
        )

    def _evaluate_experiment_artifact_contract(
        self,
        state: ResearchState,
        experiment: ExperimentRun,
    ) -> dict[str, Any]:
        contract = self._experiment_artifact_contract(state, experiment)
        if not contract:
            return {
                "enabled": False,
                "passed": True,
                "summary": "No artifact contract configured.",
            }

        required_metrics = _remove_empty_strings(contract.get("required_metrics", []))
        required_outputs = _remove_empty_strings(contract.get("required_outputs", []))
        required_artifact_types = _remove_empty_strings(
            contract.get("required_artifact_types", []),
        )

        present_metrics = sorted(str(key) for key in dict(experiment.metrics or {}).keys())
        metric_set = set(present_metrics)
        missing_metrics = [key for key in required_metrics if key not in metric_set]

        present_outputs = [str(item).strip() for item in list(experiment.output_files or []) if str(item).strip()]
        present_output_candidates = set(present_outputs)
        present_output_candidates.update(Path(item).name for item in present_outputs)
        missing_outputs = [
            value for value in required_outputs if value not in present_output_candidates
        ]

        experiment_artifacts = [
            item
            for item in state.artifacts
            if item.id in set(experiment.artifact_ids)
        ]
        present_artifact_types = sorted(
            {
                str(item.artifact_type)
                for item in experiment_artifacts
                if str(item.artifact_type).strip()
            },
        )
        artifact_type_set = set(present_artifact_types)
        missing_artifact_types = [
            value for value in required_artifact_types if value not in artifact_type_set
        ]

        passed = not any([missing_metrics, missing_outputs, missing_artifact_types])
        if passed:
            summary = "Artifact contract satisfied."
        else:
            issues: list[str] = []
            if missing_metrics:
                issues.append(f"{len(missing_metrics)} missing metric(s)")
            if missing_outputs:
                issues.append(f"{len(missing_outputs)} missing output file(s)")
            if missing_artifact_types:
                issues.append(f"{len(missing_artifact_types)} missing artifact type(s)")
            summary = "Artifact contract failed: " + ", ".join(issues) + "."

        return {
            "enabled": True,
            "passed": passed,
            "summary": summary,
            "required_metrics": required_metrics,
            "present_metrics": present_metrics,
            "missing_metrics": missing_metrics,
            "required_outputs": required_outputs,
            "present_outputs": present_outputs,
            "missing_outputs": missing_outputs,
            "required_artifact_types": required_artifact_types,
            "present_artifact_types": present_artifact_types,
            "missing_artifact_types": missing_artifact_types,
            "catalog_entry": str(
                dict(getattr(experiment.execution, "metadata", {}) or {}).get(
                    "catalog_entry",
                    "",
                )
                or "",
            ).strip(),
            "validated_at": utc_now(),
            "remediation": self._build_experiment_contract_remediation(
                experiment,
                missing_metrics=missing_metrics,
                missing_outputs=missing_outputs,
                missing_artifact_types=missing_artifact_types,
            ),
        }

    @staticmethod
    def _artifact_contract_output_hint(artifact_type: str) -> str:
        normalized = str(artifact_type or "").strip()
        if normalized == "generated_table":
            return "contract-table.json"
        if normalized == "generated_figure":
            return "contract-figure.png"
        if normalized == "summary":
            return "contract-summary.md"
        if normalized == "experiment_result":
            return "contract-result.bin"
        if normalized == "draft":
            return "contract-draft.md"
        if normalized == "analysis":
            return "contract-analysis.md"
        return f"contract-{normalized or 'artifact'}.bin"

    @classmethod
    def _build_experiment_contract_remediation(
        cls,
        experiment: ExperimentRun,
        *,
        missing_metrics: list[str],
        missing_outputs: list[str],
        missing_artifact_types: list[str],
    ) -> dict[str, Any]:
        action_rows: list[dict[str, Any]] = []
        run_name = str(experiment.name or experiment.id).strip() or experiment.id
        for metric_name in missing_metrics:
            action_rows.append(
                {
                    "action_key": f"{experiment.id}:metric:{metric_name}",
                    "action_type": "record_metric",
                    "target_type": "metric",
                    "target": metric_name,
                    "experiment_id": experiment.id,
                    "workflow_id": experiment.workflow_id,
                    "blocking": True,
                    "assignee": "analyst",
                    "due_in_hours": 4,
                    "retry_policy": {
                        "max_attempts": 2,
                        "backoff_minutes": 30,
                    },
                    "title": f"Record metric '{metric_name}' for {run_name}",
                    "instructions": (
                        f"Backfill the missing metric '{metric_name}' on experiment "
                        f"{run_name} before leaving experiment_run."
                    ),
                    "suggested_tool": "research_experiment_update",
                    "payload_hint": {
                        "experiment_id": experiment.id,
                        "metrics": {
                            metric_name: "<value>",
                        },
                    },
                },
            )
        for output_name in missing_outputs:
            action_rows.append(
                {
                    "action_key": f"{experiment.id}:output:{output_name}",
                    "action_type": "archive_output",
                    "target_type": "output_file",
                    "target": output_name,
                    "experiment_id": experiment.id,
                    "workflow_id": experiment.workflow_id,
                    "blocking": True,
                    "assignee": "analyst",
                    "due_in_hours": 4,
                    "retry_policy": {
                        "max_attempts": 2,
                        "backoff_minutes": 30,
                    },
                    "title": f"Archive output '{output_name}' for {run_name}",
                    "instructions": (
                        f"Produce or register the missing output file '{output_name}' "
                        f"for experiment {run_name}."
                    ),
                    "suggested_tool": "research_experiment_update",
                    "payload_hint": {
                        "experiment_id": experiment.id,
                        "output_files": [output_name],
                    },
                },
            )
        for artifact_type in missing_artifact_types:
            expected_path = cls._artifact_contract_output_hint(artifact_type)
            action_rows.append(
                {
                    "action_key": f"{experiment.id}:artifact:{artifact_type}",
                    "action_type": "publish_artifact",
                    "target_type": "artifact_type",
                    "target": artifact_type,
                    "experiment_id": experiment.id,
                    "workflow_id": experiment.workflow_id,
                    "blocking": True,
                    "assignee": "agent",
                    "due_in_hours": 6,
                    "retry_policy": {
                        "max_attempts": 2,
                        "backoff_minutes": 60,
                    },
                    "title": f"Publish artifact type '{artifact_type}' for {run_name}",
                    "instructions": (
                        f"Create or archive a '{artifact_type}' artifact linked to "
                        f"experiment {run_name}. A typical file name would be "
                        f"'{expected_path}'."
                    ),
                    "suggested_tool": "research_artifact_upsert",
                    "payload_hint": {
                        "project_id": experiment.project_id,
                        "workflow_id": experiment.workflow_id,
                        "experiment_id": experiment.id,
                        "artifact_type": artifact_type,
                        "title": f"{run_name} {artifact_type}",
                        "path": expected_path,
                        "source_type": "experiment",
                        "source_id": experiment.id,
                        "claim_ids": list(experiment.claim_ids),
                    },
                },
            )
        if not action_rows:
            return {
                "required": False,
                "summary": "No remediation actions are required.",
                "actions": [],
                "action_count": 0,
            }
        issue_parts: list[str] = []
        if missing_metrics:
            issue_parts.append(f"{len(missing_metrics)} metric(s)")
        if missing_outputs:
            issue_parts.append(f"{len(missing_outputs)} output file(s)")
        if missing_artifact_types:
            issue_parts.append(f"{len(missing_artifact_types)} artifact type(s)")
        return {
            "required": True,
            "summary": (
                f"Resolve missing {', '.join(issue_parts)} "
                f"for experiment {run_name}."
            ),
            "actions": action_rows,
            "action_count": len(action_rows),
        }

    def _store_experiment_artifact_contract_validation(
        self,
        state: ResearchState,
        experiment: ExperimentRun,
    ) -> dict[str, Any]:
        validation = self._evaluate_experiment_artifact_contract(state, experiment)
        experiment.metadata = {
            **dict(experiment.metadata),
            "contract_validation": validation,
        }
        return validation

    async def log_experiment(
        self,
        *,
        project_id: str,
        name: str,
        workflow_id: str = "",
        status: str = "planned",
        parameters: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        notes: str = "",
        output_files: list[str] | None = None,
        dataset_version_ids: list[str] | None = None,
        baseline_of: str = "",
        ablation_of: str = "",
        comparison_group: str = "",
        related_run_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        provenance: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRun:
        state = await self.load_state()
        project = self._project(state, project_id)
        cleaned_dataset_version_ids = _remove_empty_strings(dataset_version_ids or [])
        for dataset_version_id in cleaned_dataset_version_ids:
            self._dataset_version(state, dataset_version_id)
        experiment_provenance = ExperimentProvenance.model_validate(
            dict(provenance or {}),
        )
        if cleaned_dataset_version_ids:
            experiment_provenance.dataset_version_ids = cleaned_dataset_version_ids
        experiment = ExperimentRun(
            project_id=project_id,
            name=name,
            workflow_id=workflow_id,
            status=status,  # type: ignore[arg-type]
            parameters=dict(parameters or {}),
            input_data=dict(input_data or {}),
            dataset_version_ids=cleaned_dataset_version_ids,
            metrics=dict(metrics or {}),
            notes=notes,
            output_files=_remove_empty_strings(output_files or []),
            baseline_of=baseline_of,
            ablation_of=ablation_of,
            comparison_group=comparison_group,
            related_run_ids=_remove_empty_strings(related_run_ids or []),
            claim_ids=_remove_empty_strings(claim_ids or []),
            provenance=experiment_provenance,
            metadata=dict(metadata or {}),
        )
        now = utc_now()
        if experiment.status in {"running", "completed", "failed"}:
            experiment.started_at = now
        if experiment.status in {"completed", "failed", "cancelled"}:
            experiment.finished_at = now
        if experiment.provenance.captured_at is None:
            experiment.provenance.captured_at = now
        experiment.provenance.replayable = bool(
            experiment.execution.mode in {"command", "notebook", "external", "file_watch"}
            or experiment.output_files
            or experiment.metrics
        )
        state.experiments.append(experiment)
        _append_unique(project.experiment_ids, experiment.id)
        self._touch(project)

        if workflow_id:
            workflow = self._workflow(state, workflow_id)
            _append_unique(workflow.experiment_ids, experiment.id)
            self._touch(workflow)

        for claim_id in experiment.claim_ids:
            claim = self._claim(state, claim_id)
            self._touch(claim)

        self._sync_experiment_output_artifacts(state, experiment)
        self._sync_experiment_completion_evidence(state, experiment)
        self._record_audit_event(
            state,
            entity_type="experiment",
            entity_id=experiment.id,
            action="create",
            project_id=experiment.project_id,
            workflow_id=experiment.workflow_id,
            summary=f"Logged experiment '{experiment.name}'.",
            after=self._model_payload(experiment),
        )

        await self.save_state(state)
        return experiment

    async def update_experiment(
        self,
        *,
        experiment_id: str,
        workflow_id: str | None = None,
        status: str | None = None,
        parameters: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
        dataset_version_ids: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        notes: str | None = None,
        output_files: list[str] | None = None,
        baseline_of: str | None = None,
        ablation_of: str | None = None,
        comparison_group: str | None = None,
        related_run_ids: list[str] | None = None,
        claim_ids: list[str] | None = None,
        note_ids: list[str] | None = None,
        provenance: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperimentRun:
        state = await self.load_state()
        experiment = self._experiment(state, experiment_id)
        before = self._model_payload(experiment)

        if workflow_id is not None:
            clean_workflow_id = str(workflow_id or "").strip()
            if clean_workflow_id:
                workflow = self._workflow(state, clean_workflow_id)
                if workflow.project_id != experiment.project_id:
                    raise ValueError("Experiment workflow must belong to the same project.")
                _append_unique(workflow.experiment_ids, experiment.id)
                self._touch(workflow)
            experiment.workflow_id = clean_workflow_id
        if status:
            experiment.status = status  # type: ignore[assignment]
        if parameters:
            merged_parameters = dict(experiment.parameters)
            merged_parameters.update(dict(parameters))
            experiment.parameters = merged_parameters
        if input_data:
            merged_input_data = dict(experiment.input_data)
            merged_input_data.update(dict(input_data))
            experiment.input_data = merged_input_data
        if dataset_version_ids is not None:
            cleaned_dataset_version_ids = _remove_empty_strings(dataset_version_ids)
            for dataset_version_id in cleaned_dataset_version_ids:
                self._dataset_version(state, dataset_version_id)
            experiment.dataset_version_ids = cleaned_dataset_version_ids
        if metrics:
            merged_metrics = dict(experiment.metrics)
            merged_metrics.update(dict(metrics))
            experiment.metrics = merged_metrics
        if notes is not None:
            experiment.notes = notes
        if baseline_of is not None:
            experiment.baseline_of = baseline_of
        if ablation_of is not None:
            experiment.ablation_of = ablation_of
        if comparison_group is not None:
            experiment.comparison_group = comparison_group

        for output_file in _remove_empty_strings(output_files or []):
            _append_unique(experiment.output_files, output_file)
        for run_id in _remove_empty_strings(related_run_ids or []):
            _append_unique(experiment.related_run_ids, run_id)
        for claim_id in _remove_empty_strings(claim_ids or []):
            _append_unique(experiment.claim_ids, claim_id)
            claim = self._claim(state, claim_id)
            self._touch(claim)
        for note_id in _remove_empty_strings(note_ids or []):
            _append_unique(experiment.note_ids, note_id)
            note = self._note(state, note_id)
            _append_unique(note.experiment_ids, experiment.id)
            self._touch(note)

        if provenance:
            merged_provenance = experiment.provenance.model_dump(mode="json")
            merged_provenance.update(dict(provenance))
            experiment.provenance = ExperimentProvenance.model_validate(merged_provenance)

        if metadata:
            merged_metadata = dict(experiment.metadata)
            merged_metadata.update(dict(metadata))
            experiment.metadata = merged_metadata

        now = utc_now()
        if experiment.status in {"running", "completed", "failed"} and not experiment.started_at:
            experiment.started_at = now
        if experiment.status in {"completed", "failed", "cancelled"}:
            experiment.finished_at = now
        if experiment.provenance.captured_at is None:
            experiment.provenance.captured_at = now
        if experiment.dataset_version_ids:
            experiment.provenance.dataset_version_ids = list(experiment.dataset_version_ids)
        experiment.provenance.replayable = bool(
            experiment.execution.mode in {"command", "notebook", "external", "file_watch"}
            or experiment.output_files
            or experiment.metrics
        )

        self._sync_experiment_output_artifacts(state, experiment)
        self._sync_experiment_completion_evidence(state, experiment)
        if experiment.status in {"completed", "failed", "cancelled"}:
            self._store_experiment_artifact_contract_validation(state, experiment)
        self._touch(experiment, now=now)
        self._record_audit_event(
            state,
            entity_type="experiment",
            entity_id=experiment.id,
            action="update",
            project_id=experiment.project_id,
            workflow_id=experiment.workflow_id,
            summary=f"Updated experiment '{experiment.name}' to status '{experiment.status}'.",
            before=before,
            after=self._model_payload(experiment),
        )
        await self.save_state(state)
        return experiment

    async def list_experiments(
        self,
        *,
        project_id: str = "",
        workflow_id: str = "",
        status: str = "",
        execution_mode: str = "",
        query: str = "",
        replayable: bool | None = None,
        limit: int = 100,
    ) -> list[ExperimentRun]:
        state = await self.load_state()
        runs = list(state.experiments)
        if project_id:
            runs = [item for item in runs if item.project_id == project_id]
        if workflow_id:
            runs = [item for item in runs if item.workflow_id == workflow_id]
        if status:
            runs = [item for item in runs if item.status == status]
        if execution_mode:
            runs = [item for item in runs if item.execution.mode == execution_mode]
        if replayable is not None:
            runs = [
                item
                for item in runs
                if bool(item.provenance.replayable) is bool(replayable)
            ]
        if query:
            query_text = str(query).strip().lower()
            runs = [
                item
                for item in runs
                if query_text in item.name.lower()
                or query_text in item.notes.lower()
                or query_text in item.comparison_group.lower()
                or query_text in " ".join(item.output_files).lower()
                or query_text in str(item.execution.result_bundle_schema or "").lower()
            ]
        runs.sort(
            key=lambda item: item.finished_at or item.started_at or item.created_at,
            reverse=True,
        )
        return runs[: max(1, int(limit))]

    async def bulk_update_experiments(
        self,
        *,
        project_id: str,
        experiment_ids: list[str],
        workflow_id: str | None = None,
        status: str | None = None,
        comparison_group: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = await self.load_state()
        self._project(state, project_id)
        cleaned_experiment_ids = _remove_empty_strings(experiment_ids)
        metadata_patch_dict = dict(metadata_patch or {})
        if not cleaned_experiment_ids:
            raise ValueError("No experiment ids provided.")
        if (
            workflow_id is None
            and status is None
            and comparison_group is None
            and not metadata_patch_dict
        ):
            raise ValueError("No experiment bulk update fields were provided.")

        updated_runs: list[ExperimentRun] = []
        for experiment_id in cleaned_experiment_ids:
            experiment = self._experiment(state, experiment_id)
            if experiment.project_id != project_id:
                raise ValueError("Experiment bulk update must stay within one project.")
            updated_runs.append(
                await self.update_experiment(
                    experiment_id=experiment_id,
                    workflow_id=workflow_id,
                    status=status,
                    comparison_group=comparison_group,
                    metadata=metadata_patch_dict if metadata_patch_dict else None,
                ),
            )
        return {
            "updated_count": len(updated_runs),
            "experiments": updated_runs,
        }

    async def compare_experiments(
        self,
        experiment_ids: list[str],
    ) -> dict[str, Any]:
        state = await self.load_state()
        selected = [
            item for item in state.experiments if item.id in set(experiment_ids)
        ]
        all_params: set[str] = set()
        all_metrics: set[str] = set()
        for run in selected:
            all_params.update(run.parameters.keys())
            all_metrics.update(run.metrics.keys())
        return {
            "experiment_ids": experiment_ids,
            "parameter_keys": sorted(all_params),
            "metric_keys": sorted(all_metrics),
            "runs": [
                {
                    "id": run.id,
                    "name": run.name,
                    "status": run.status,
                    "baseline_of": run.baseline_of,
                    "ablation_of": run.ablation_of,
                    "comparison_group": run.comparison_group,
                    "parameters": {
                        key: run.parameters.get(key) for key in sorted(all_params)
                    },
                    "metrics": {
                        key: run.metrics.get(key) for key in sorted(all_metrics)
                    },
                    "output_files": run.output_files,
                    "artifact_ids": run.artifact_ids,
                }
                for run in selected
            ],
        }

    # ---- proactive automation ----

    def _build_workflow_reminder(
        self,
        *,
        project: ResearchProject,
        workflow: ResearchWorkflow,
        reminder_type: str,
        title: str,
        summary: str,
        context: dict[str, Any] | None = None,
    ) -> ProactiveReminder:
        return ProactiveReminder(
            reminder_type=reminder_type,  # type: ignore[arg-type]
            project_id=project.id,
            workflow_id=workflow.id,
            stage=workflow.current_stage,
            title=title,
            summary=summary,
            binding=self._project_binding(project, workflow),
            context={
                "project_name": project.name,
                "workflow_title": workflow.title,
                "current_stage": workflow.current_stage,
                "goal": workflow.goal,
                **dict(context or {}),
            },
        )

    def _build_task_reminder(
        self,
        *,
        project: ResearchProject,
        workflow: ResearchWorkflow,
        task: WorkflowTask,
        reminder_type: str,
        title: str,
        summary: str,
        context: dict[str, Any] | None = None,
    ) -> ProactiveReminder:
        return ProactiveReminder(
            reminder_type=reminder_type,  # type: ignore[arg-type]
            project_id=project.id,
            workflow_id=workflow.id,
            task_id=task.id,
            stage=workflow.current_stage,
            title=title,
            summary=summary,
            binding=self._project_binding(project, workflow),
            context={
                "project_name": project.name,
                "workflow_title": workflow.title,
                "current_stage": workflow.current_stage,
                "goal": workflow.goal,
                "task_title": task.title,
                "task_assignee": task.assignee,
                "task_due_at": task.due_at,
                "task_status": task.status,
                "task_dispatch_count": task.dispatch_count,
                **dict(context or {}),
            },
        )

    def _workflow_contract_followup_context(
        self,
        state: ResearchState,
        workflow: ResearchWorkflow,
    ) -> dict[str, Any]:
        if workflow.current_stage != "experiment_run":
            return {}
        followup_task = next(
            (
                task
                for task in workflow.tasks
                if task.stage == "experiment_run"
                and str(task.metadata.get("task_kind", "") or "").strip()
                == "experiment_contract_followup"
            ),
            None,
        )
        remediation_tasks = [
            task
            for task in workflow.tasks
            if task.stage == "experiment_run"
            and str(task.metadata.get("task_kind", "") or "").strip()
            == "experiment_contract_remediation"
        ]
        if followup_task is None and workflow.status != "blocked":
            return {}
        preferred_run_ids = _remove_empty_strings(
            list(
                dict(getattr(followup_task, "metadata", {}) or {}).get(
                    "contract_failure_run_ids",
                    [],
                )
                or [],
            ),
        )
        experiments = [
            item
            for item in state.experiments
            if item.workflow_id == workflow.id
            and (
                not preferred_run_ids
                or item.id in set(preferred_run_ids)
            )
        ]
        contract_failures: list[dict[str, Any]] = []
        remediation_actions: list[dict[str, Any]] = []
        remediation_task_rows = [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "assignee": task.assignee,
                "action_type": str(task.metadata.get("action_type", "") or ""),
                "target": str(task.metadata.get("target", "") or ""),
                "suggested_tool": str(task.metadata.get("suggested_tool", "") or ""),
                "due_at": task.due_at,
                "dispatch_count": task.dispatch_count,
                "last_dispatch_at": task.last_dispatch_at,
                "last_dispatch_summary": task.last_dispatch_summary,
                "last_dispatch_error": task.last_dispatch_error,
                "execution_count": task.execution_count,
                "last_execution_at": task.last_execution_at,
                "last_execution_summary": task.last_execution_summary,
                "last_execution_error": task.last_execution_error,
                "max_attempts": self._task_retry_policy(task)[0],
                "can_dispatch": self._eligible_for_task_dispatch(task=task, now=datetime.now(timezone.utc)),
                "can_execute": (
                    str(task.assignee or "").strip() == "agent"
                    and task.status not in {"completed", "cancelled"}
                ),
                "summary": task.summary,
                "remediation_key": str(task.metadata.get("remediation_key", "") or ""),
            }
            for task in remediation_tasks
        ]
        exhausted_tasks = [
            task
            for task in remediation_task_rows
            if int(task.get("dispatch_count") or 0) >= int(task.get("max_attempts") or 1)
        ]
        missing_metric_count = 0
        missing_output_count = 0
        missing_artifact_type_count = 0
        for experiment in experiments:
            validation = self._evaluate_experiment_artifact_contract(state, experiment)
            if not validation.get("enabled") or validation.get("passed", True):
                continue
            remediation = dict(validation.get("remediation") or {})
            missing_metrics = list(validation.get("missing_metrics", []) or [])
            missing_outputs = list(validation.get("missing_outputs", []) or [])
            missing_artifact_types = list(
                validation.get("missing_artifact_types", []) or [],
            )
            missing_metric_count += len(missing_metrics)
            missing_output_count += len(missing_outputs)
            missing_artifact_type_count += len(missing_artifact_types)
            contract_failures.append(
                {
                    "experiment_id": experiment.id,
                    "experiment_name": experiment.name,
                    "summary": validation.get("summary", ""),
                    "missing_metrics": missing_metrics,
                    "missing_outputs": missing_outputs,
                    "missing_artifact_types": missing_artifact_types,
                    "remediation": remediation,
                },
            )
            for action in list(remediation.get("actions", []) or []):
                if not isinstance(action, dict):
                    continue
                remediation_actions.append(action)
        if not contract_failures:
            if not followup_task and not remediation_tasks:
                return {}
            ready = all(
                task.status in {"completed", "cancelled"}
                for task in remediation_tasks
            )
            remediation_summary = (
                "All experiment contract remediation items are resolved."
                if ready
                else "Contract remediation tasks remain open."
            )
            if exhausted_tasks and not ready:
                remediation_summary = " ".join(
                    [
                        remediation_summary,
                        f"{len(exhausted_tasks)} remediation task(s) exhausted retry budget.",
                    ],
                ).strip()
            return {
                "contract_failures": [],
                "remediation_summary": remediation_summary,
                "remediation_actions": [],
                "blocked_task_id": getattr(followup_task, "id", ""),
                "blocked_task_title": getattr(followup_task, "title", ""),
                "remediation_tasks": remediation_task_rows,
                "ready_for_retry": ready,
                "retry_exhausted_count": len(exhausted_tasks),
                "retry_exhausted_tasks": exhausted_tasks,
            }
        remediation_summary = (
            f"{len(contract_failures)} run(s) need remediation: "
            f"{missing_metric_count} missing metric(s), "
            f"{missing_output_count} missing output file(s), "
            f"{missing_artifact_type_count} missing artifact type(s)."
        )
        if exhausted_tasks:
            remediation_summary = " ".join(
                [
                    remediation_summary,
                    f"{len(exhausted_tasks)} remediation task(s) exhausted retry budget.",
                ],
            ).strip()
        return {
            "contract_failures": contract_failures,
            "remediation_summary": remediation_summary,
            "remediation_actions": remediation_actions[:10],
            "blocked_task_id": getattr(followup_task, "id", ""),
            "blocked_task_title": getattr(followup_task, "title", ""),
            "remediation_tasks": remediation_task_rows,
            "ready_for_retry": False,
            "retry_exhausted_count": len(exhausted_tasks),
            "retry_exhausted_tasks": exhausted_tasks,
        }

    @staticmethod
    def _eligible_for_reminder(
        *,
        last_reminder_at: str | None,
        now: datetime,
        cooldown_hours: int = 6,
    ) -> bool:
        hours = _hours_since(last_reminder_at, now=now)
        return hours is None or hours >= cooldown_hours

    @staticmethod
    def _task_retry_policy(task: WorkflowTask) -> tuple[int, int]:
        metadata = dict(getattr(task, "metadata", {}) or {})
        retry_policy = dict(metadata.get("retry_policy", {}) or {})
        try:
            max_attempts = int(retry_policy.get("max_attempts") or 1)
        except (TypeError, ValueError):
            max_attempts = 1
        try:
            backoff_minutes = int(retry_policy.get("backoff_minutes") or 60)
        except (TypeError, ValueError):
            backoff_minutes = 60
        return max(1, max_attempts), max(1, backoff_minutes)

    @classmethod
    def _eligible_for_task_dispatch(
        cls,
        *,
        task: WorkflowTask,
        now: datetime,
    ) -> bool:
        if task.status not in {"pending", "blocked", "running"}:
            return False
        max_attempts, backoff_minutes = cls._task_retry_policy(task)
        if int(getattr(task, "dispatch_count", 0) or 0) >= max_attempts:
            return False
        hours = _hours_since(getattr(task, "last_dispatch_at", None), now=now)
        if hours is None:
            return True
        return hours * 60 >= backoff_minutes

    async def preview_due_reminders(
        self,
        *,
        project_id: str = "",
        stale_hours: int = 24,
    ) -> list[ProactiveReminder]:
        state = await self.load_state()
        now = datetime.now(timezone.utc)
        reminders: list[ProactiveReminder] = []

        projects = state.projects
        if project_id:
            projects = [item for item in projects if item.id == project_id]

        for project in projects:
            workflows = [
                item
                for item in state.workflows
                if item.project_id == project.id
                and item.status in {"running", "blocked", "paused"}
            ]
            for workflow in workflows:
                stage_tasks = self._stage_task_list(workflow, workflow.current_stage)
                pending_tasks = [
                    task
                    for task in stage_tasks
                    if task.status in {"pending", "running", "blocked"}
                ]
                age_hours = _hours_since(
                    workflow.last_run_at or workflow.updated_at,
                    now=now,
                ) or 0.0
                if workflow.status == "blocked":
                    contract_context = self._workflow_contract_followup_context(
                        state,
                        workflow,
                    )
                    summary = (
                        f"Project {project.name} is blocked in "
                        f"{workflow.current_stage}. "
                        f"Reason: {workflow.error or 'manual follow-up needed'}."
                    )
                    if contract_context:
                        summary = " ".join(
                            [
                                summary,
                                str(
                                    contract_context.get(
                                        "remediation_summary",
                                        "",
                                    )
                                    or "",
                                ).strip(),
                            ],
                        ).strip()
                    reminders.append(
                        self._build_workflow_reminder(
                            project=project,
                            workflow=workflow,
                            reminder_type="stage_stuck_followup",
                            title=f"Stage stuck: {workflow.title}",
                            summary=summary,
                            context=contract_context,
                        ),
                    )
                    for task in stage_tasks:
                        if (
                            str(task.metadata.get("task_kind", "") or "").strip()
                            != "experiment_contract_remediation"
                        ):
                            continue
                        if not self._eligible_for_task_dispatch(task=task, now=now):
                            continue
                        metadata = dict(task.metadata or {})
                        payload_hint = dict(metadata.get("payload_hint", {}) or {})
                        suggested_tool = str(metadata.get("suggested_tool", "") or "").strip()
                        max_attempts, backoff_minutes = self._task_retry_policy(task)
                        task_summary = " ".join(
                            part
                            for part in [
                                (
                                    f"Assignee {task.assignee} should resolve "
                                    f"'{task.title}'."
                                ),
                                str(task.summary or task.description or "").strip(),
                                f"Use {suggested_tool}." if suggested_tool else "",
                                f"Dispatch attempt {task.dispatch_count + 1}/{max_attempts}.",
                            ]
                            if part
                        ).strip()
                        reminders.append(
                            self._build_task_reminder(
                                project=project,
                                workflow=workflow,
                                task=task,
                                reminder_type="remediation_task_followup",
                                title=f"Remediation task: {task.title}",
                                summary=task_summary,
                                context={
                                    "suggested_tool": suggested_tool,
                                    "payload_hint": payload_hint,
                                    "task_backoff_minutes": backoff_minutes,
                                    "task_max_attempts": max_attempts,
                                },
                            ),
                        )
                    continue
                if workflow.current_stage == "writing_tasks" and pending_tasks:
                    reminders.append(
                        self._build_workflow_reminder(
                            project=project,
                            workflow=workflow,
                            reminder_type="writing_todo",
                            title=f"Writing follow-up: {workflow.title}",
                            summary=(
                                f"{len(pending_tasks)} writing task(s) are still open "
                                f"for project {project.name}."
                            ),
                        ),
                    )
                    continue
                if age_hours >= stale_hours:
                    reminders.append(
                        self._build_workflow_reminder(
                            project=project,
                            workflow=workflow,
                            reminder_type="workflow_timeout",
                            title=f"Workflow idle: {workflow.title}",
                            summary=(
                                f"Project {project.name} has not advanced workflow "
                                f"{workflow.title} for about {int(age_hours)} hour(s)."
                            ),
                        ),
                    )

            experiments = [
                item
                for item in state.experiments
                if item.project_id == project.id and item.status == "completed"
            ]
            for experiment in experiments:
                validation = self._evaluate_experiment_artifact_contract(
                    state,
                    experiment,
                )
                if validation.get("enabled") and not validation.get("passed", True):
                    continue
                if not self._eligible_for_reminder(
                    last_reminder_at=experiment.last_reminder_at,
                    now=now,
                ):
                    continue
                reminders.append(
                    ProactiveReminder(
                        reminder_type="experiment_complete",
                        project_id=project.id,
                        experiment_id=experiment.id,
                        title=f"Experiment completed: {experiment.name}",
                        summary=(
                            f"Experiment {experiment.name} finished with "
                            f"{len(experiment.metrics)} metric(s) and "
                            f"{len(experiment.output_files)} archived output file(s)."
                        ),
                        binding=self._project_binding(project),
                        context={
                            "project_name": project.name,
                            "metrics": experiment.metrics,
                            "workflow_id": experiment.workflow_id,
                        },
                    ),
                )

        return reminders

    def _search_papers(
        self,
        *,
        source: str,
        query: str,
        max_results: int,
    ) -> list[dict[str, Any]]:
        if source == "semantic_scholar":
            from researchclaw.agents.tools.semantic_scholar import (
                semantic_scholar_search,
            )

            return semantic_scholar_search(query=query, max_results=max_results)

        from researchclaw.agents.skills.arxiv.tools import arxiv_search

        return arxiv_search(query=query, max_results=max_results)

    async def generate_proactive_reminders(
        self,
        *,
        project_id: str = "",
        stale_hours: int = 24,
    ) -> list[ProactiveReminder]:
        state = await self.load_state()
        now = datetime.now(timezone.utc)
        now_iso = utc_now()
        reminders = await self.preview_due_reminders(
            project_id=project_id,
            stale_hours=stale_hours,
        )

        projects = state.projects
        if project_id:
            projects = [item for item in projects if item.id == project_id]

        emitted_workflow_ids = {item.workflow_id for item in reminders if item.workflow_id}
        emitted_experiment_ids = {item.experiment_id for item in reminders if item.experiment_id}
        emitted_task_ids = {item.task_id for item in reminders if item.task_id}

        for project in projects:
            for workflow in state.workflows:
                if workflow.project_id != project.id:
                    continue
                if workflow.id in emitted_workflow_ids and self._eligible_for_reminder(
                    last_reminder_at=workflow.last_reminder_at,
                    now=now,
                ):
                    workflow.last_reminder_at = now_iso
                    self._touch(workflow, now=now_iso)
                for task in workflow.tasks:
                    if task.id not in emitted_task_ids:
                        continue
                    task.dispatch_count = max(0, int(task.dispatch_count or 0)) + 1
                    task.last_dispatch_at = now_iso
                    task.last_dispatch_summary = "Proactive remediation dispatch emitted."
                    task.last_dispatch_error = ""
                    task.updated_at = now_iso
                    self._touch(workflow, now=now_iso)

            for experiment in state.experiments:
                if experiment.project_id != project.id:
                    continue
                if experiment.id in emitted_experiment_ids:
                    experiment.last_reminder_at = now_iso
                    self._touch(experiment, now=now_iso)

            for watch in project.paper_watches:
                last_checked = _parse_iso(watch.last_checked_at)
                if (
                    last_checked is not None
                    and now - last_checked < timedelta(hours=max(1, watch.check_every_hours))
                ):
                    continue
                results = self._search_papers(
                    source=watch.source,
                    query=watch.query,
                    max_results=max(1, watch.max_results),
                )
                watch.last_checked_at = now_iso
                watch.last_error = ""
                watch.last_result_count = len(results)
                clean_results = [
                    item for item in results if isinstance(item, dict) and not item.get("error")
                ]
                seen = set(watch.seen_paper_ids)
                new_items: list[dict[str, Any]] = []
                for item in clean_results:
                    paper_id = str(
                        item.get("arxiv_id")
                        or item.get("paper_id")
                        or item.get("doi")
                        or item.get("title")
                        or ""
                    ).strip()
                    if not paper_id:
                        continue
                    if paper_id not in seen:
                        new_items.append(item)
                    seen.add(paper_id)
                if new_items:
                    watch.seen_paper_ids = list(seen)
                    for item in new_items:
                        paper_ref = str(
                            item.get("arxiv_id")
                            or item.get("paper_id")
                            or item.get("doi")
                            or ""
                        ).strip()
                        _append_unique(project.paper_refs, paper_ref)
                    preview = "; ".join(
                        str(item.get("title", "") or "").strip()
                        for item in new_items[:3]
                        if str(item.get("title", "") or "").strip()
                    )
                    reminders.append(
                        ProactiveReminder(
                            reminder_type="new_paper_tracking",
                            project_id=project.id,
                            title=f"New papers for {project.name}",
                            summary=(
                                f"Watch query '{watch.query}' found {len(new_items)} new paper(s). "
                                f"{preview}"
                            ).strip(),
                            binding=self._project_binding(project),
                            context={
                                "project_name": project.name,
                                "watch_query": watch.query,
                                "new_items": new_items[:10],
                            },
                        ),
                    )
                elif results and isinstance(results[0], dict) and results[0].get("error"):
                    watch.last_error = str(results[0].get("error", ""))
                self._touch(project, now=now_iso)

        await self.save_state(state)
        return reminders

    async def get_runtime_stats(self) -> dict[str, Any]:
        overview = await self.get_overview()
        preview = await self.preview_due_reminders()
        return {
            **overview["counts"],
            "due_reminders": len(preview),
            "state_path": str(self.path),
        }
