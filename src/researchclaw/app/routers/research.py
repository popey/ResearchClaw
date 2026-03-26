"""Research workflow and project APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from researchclaw.constant import RESEARCH_WORKFLOW_STALE_HOURS

router = APIRouter()


def _get_research_service(req: Request):
    service = getattr(req.app.state, "research_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Research service not initialized")
    return service


def _get_research_runtime(req: Request):
    runtime = getattr(req.app.state, "research_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Research runtime not initialized")
    return runtime


def _translate_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    default_binding: dict[str, Any] = Field(default_factory=dict)
    execution_catalog: list[dict[str, Any]] = Field(default_factory=list)
    result_bundle_schemas: list[dict[str, Any]] = Field(default_factory=list)
    default_experiment_runner: dict[str, Any] = Field(default_factory=dict)
    paper_watches: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    description: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    default_binding: dict[str, Any] = Field(default_factory=dict)
    execution_catalog: list[dict[str, Any]] | None = None
    result_bundle_schemas: list[dict[str, Any]] | None = None
    default_experiment_runner: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaperWatchCreateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    source: str = "arxiv"
    max_results: int = 5
    check_every_hours: int = 12


class WorkflowCreateRequest(BaseModel):
    project_id: str
    title: str = Field(..., min_length=1)
    goal: str = ""
    bindings: dict[str, Any] = Field(default_factory=dict)
    execution_policy: dict[str, Any] = Field(default_factory=dict)
    experiment_runner: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_start: bool = True


class WorkflowTaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    stage: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    due_at: str | None = None
    assignee: str = "agent"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowTaskUpdateRequest(BaseModel):
    status: str | None = None
    summary: str | None = None
    due_at: str | None = None
    note_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)


class WorkflowRestoreRequest(BaseModel):
    checkpoint_id: str = ""


class NoteCreateRequest(BaseModel):
    project_id: str
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    note_type: str = "idea_note"
    workflow_id: str = ""
    experiment_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    paper_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NoteUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    note_type: str | None = None
    workflow_id: str | None = None
    experiment_ids: list[str] | None = None
    claim_ids: list[str] | None = None
    artifact_ids: list[str] | None = None
    paper_refs: list[str] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class NoteBulkUpdateRequest(BaseModel):
    project_id: str
    note_ids: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    note_type: str | None = None
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class ArtifactUpsertRequest(BaseModel):
    project_id: str
    title: str = Field(..., min_length=1)
    artifact_type: str
    workflow_id: str = ""
    description: str = ""
    path: str = ""
    uri: str = ""
    source_type: str = ""
    source_id: str = ""
    experiment_id: str = ""
    note_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactUpdateRequest(BaseModel):
    title: str | None = None
    artifact_type: str | None = None
    workflow_id: str | None = None
    description: str | None = None
    path: str | None = None
    uri: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    experiment_id: str | None = None
    note_ids: list[str] | None = None
    claim_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ArtifactBulkUpdateRequest(BaseModel):
    project_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    source_type: str | None = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class ArtifactRelationCreateRequest(BaseModel):
    project_id: str
    source_artifact_id: str = Field(..., min_length=1)
    target_artifact_id: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    workflow_id: str = ""
    experiment_id: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimCreateRequest(BaseModel):
    project_id: str
    text: str = Field(..., min_length=1)
    workflow_id: str = ""
    status: str = "draft"
    confidence: float | None = None
    note_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimUpdateRequest(BaseModel):
    text: str | None = None
    status: str | None = None
    workflow_id: str | None = None
    confidence: float | None = None
    note_ids: list[str] | None = None
    artifact_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ClaimBulkUpdateRequest(BaseModel):
    project_id: str
    claim_ids: list[str] = Field(default_factory=list)
    status: str | None = None
    workflow_id: str | None = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class ClaimValidationRequest(BaseModel):
    apply_status: bool = True


class EvidenceCreateRequest(BaseModel):
    project_id: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_type: str
    summary: str = Field(..., min_length=1)
    source_type: str
    source_id: str = ""
    title: str = ""
    locator: str = ""
    quote: str = ""
    url: str = ""
    workflow_id: str = ""
    artifact_id: str = ""
    note_id: str = ""
    experiment_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceUpdateRequest(BaseModel):
    summary: str | None = None
    evidence_type: str | None = None
    workflow_id: str | None = None
    claim_ids: list[str] | None = None
    artifact_id: str | None = None
    note_id: str | None = None
    experiment_id: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    title: str | None = None
    locator: str | None = None
    quote: str | None = None
    url: str | None = None
    metadata: dict[str, Any] | None = None


class EvidenceBulkUpdateRequest(BaseModel):
    project_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    evidence_type: str | None = None
    source_type: str | None = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class ExperimentCreateRequest(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1)
    workflow_id: str = ""
    status: str = "planned"
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_data: dict[str, Any] = Field(default_factory=dict)
    dataset_version_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    output_files: list[str] = Field(default_factory=list)
    baseline_of: str = ""
    ablation_of: str = ""
    comparison_group: str = ""
    related_run_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentUpdateRequest(BaseModel):
    workflow_id: str | None = None
    status: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_data: dict[str, Any] = Field(default_factory=dict)
    dataset_version_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    output_files: list[str] = Field(default_factory=list)
    baseline_of: str | None = None
    ablation_of: str | None = None
    comparison_group: str | None = None
    related_run_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    note_ids: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentBulkUpdateRequest(BaseModel):
    project_id: str
    experiment_ids: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    status: str | None = None
    comparison_group: str | None = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class ExperimentExecutionConfigureRequest(BaseModel):
    mode: str | None = None
    command: list[str] = Field(default_factory=list)
    entrypoint: str = ""
    working_dir: str = ""
    notebook_path: str = ""
    result_bundle_file: str = ""
    result_bundle_schema: str = ""
    environment: dict[str, str] = Field(default_factory=dict)
    external_run_id: str = ""
    requested_by: str = ""
    instructions: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentProvenanceCaptureRequest(BaseModel):
    command: list[str] = Field(default_factory=list)
    working_dir: str = ""
    environment_keys: list[str] = Field(default_factory=list)
    dependency_fingerprint: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentHeartbeatRequest(BaseModel):
    summary: str = Field(..., min_length=1)
    status: str = "running"
    metrics: dict[str, Any] = Field(default_factory=dict)
    output_files: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentResultRequest(BaseModel):
    summary: str = ""
    status: str = "completed"
    metrics: dict[str, Any] = Field(default_factory=dict)
    output_files: list[str] = Field(default_factory=list)
    notes: str | None = None
    note_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareExperimentsRequest(BaseModel):
    experiment_ids: list[str] = Field(default_factory=list)


class ProjectMemoryCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    entry_kind: str = "fact"
    workflow_id: str = ""
    stage: str = ""
    status: str = "active"
    note_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectMemoryUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    entry_kind: str | None = None
    workflow_id: str | None = None
    stage: str | None = None
    status: str | None = None
    note_ids: list[str] | None = None
    claim_ids: list[str] | None = None
    artifact_ids: list[str] | None = None
    experiment_ids: list[str] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ProjectMemoryBulkUpdateRequest(BaseModel):
    memory_ids: list[str] = Field(default_factory=list)
    status: str | None = None
    entry_kind: str | None = None
    workflow_id: str | None = None
    stage: str | None = None
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class DatasetVersionCreateRequest(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1)
    version_label: str = "v1"
    description: str = ""
    workflow_id: str = ""
    path: str = ""
    source_paths: list[str] = Field(default_factory=list)
    parent_version_id: str = ""
    split_spec: dict[str, Any] = Field(default_factory=dict)
    transform_steps: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetVersionUpdateRequest(BaseModel):
    name: str | None = None
    version_label: str | None = None
    description: str | None = None
    workflow_id: str | None = None
    path: str | None = None
    source_paths: list[str] | None = None
    parent_version_id: str | None = None
    split_spec: dict[str, Any] | None = None
    transform_steps: list[dict[str, Any]] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class DatasetVersionBulkUpdateRequest(BaseModel):
    project_id: str
    dataset_version_ids: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class ReminderRunRequest(BaseModel):
    project_id: str = ""
    stale_hours: int = RESEARCH_WORKFLOW_STALE_HOURS


class WorkflowExecuteRequest(BaseModel):
    agent_id: str = ""
    session_id: str = ""


class ClosureActionRequest(BaseModel):
    action_kind: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)


class ClosureActionBatchRequest(BaseModel):
    closure_keys: list[str] = Field(default_factory=list)
    mode: str = "execute"


class ProjectBlockerBatchRequest(BaseModel):
    workflow_ids: list[str] = Field(default_factory=list)
    mode: str = "dispatch"
    task_limit: int = 2


class ClosureMaterializeRequest(BaseModel):
    limit: int = 5
    action_kind: str = ""
    target_id: str = ""


class WorkflowExecutionPolicyUpdateRequest(BaseModel):
    enabled: bool | None = None
    mode: str | None = None
    stale_hours: int | None = None
    cooldown_minutes: int | None = None
    max_auto_runs_per_day: int | None = None
    allowed_stages: list[str] | None = None
    notify_after_execution: bool | None = None


class ExperimentRunnerProfileUpdateRequest(BaseModel):
    enabled: bool | None = None
    default: dict[str, Any] = Field(default_factory=dict)
    kind_overrides: dict[str, dict[str, Any] | None] = Field(default_factory=dict)
    rules: list[dict[str, Any]] | None = None


@router.get("/overview")
async def overview(req: Request):
    service = _get_research_service(req)
    return await service.get_overview()


@router.get("/projects")
async def list_projects(req: Request):
    service = _get_research_service(req)
    return await service.list_projects()


@router.post("/projects")
async def create_project(payload: ProjectCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.create_project(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}")
async def get_project(project_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_project(project_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectUpdateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.update_project(
            project_id=project_id,
            **payload.model_dump(
                mode="json",
                exclude_none=True,
                exclude_unset=True,
            ),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}/dashboard")
async def project_dashboard(project_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_project_dashboard(project_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}/closure")
async def project_closure(project_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_project_closure_report(project_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}/closure/actions")
async def list_project_closure_actions(
    project_id: str,
    req: Request,
    kind: str = "",
    severity: str = "",
    target_type: str = "",
    workflow_id: str = "",
    auto_executable: bool | None = Query(default=None),
    materializable: bool | None = Query(default=None),
    query: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_project_closure_actions(
            project_id,
            kind=kind,
            severity=severity,
            target_type=target_type,
            workflow_id=workflow_id,
            auto_executable=auto_executable,
            materializable=materializable,
            query=query,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}/memory")
async def list_project_memory(
    project_id: str,
    req: Request,
    workflow_id: str = "",
    entry_kind: str = "",
    status: str = "",
    stage: str = "",
    tag: str = "",
    query: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_project_memory(
            project_id=project_id,
            workflow_id=workflow_id,
            entry_kind=entry_kind,
            status=status,
            stage=stage,
            tag=tag,
            query=query,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/memory")
async def create_project_memory(
    project_id: str,
    payload: ProjectMemoryCreateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.create_project_memory(
            project_id=project_id,
            **payload.model_dump(
                mode="json",
                exclude={"project_id"},
            ),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/projects/{project_id}/memory/{memory_id}")
async def update_project_memory(
    project_id: str,
    memory_id: str,
    payload: ProjectMemoryUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_project_memory(
            project_id=project_id,
            memory_id=memory_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/memory/bulk-update")
async def bulk_update_project_memory(
    project_id: str,
    payload: ProjectMemoryBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_project_memory(
            project_id=project_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}/audit")
async def list_project_audit_events(
    project_id: str,
    req: Request,
    workflow_id: str = "",
    entity_type: str = "",
    entity_id: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_audit_events(
            project_id=project_id,
            workflow_id=workflow_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/closure/materialize")
async def materialize_project_closure(
    project_id: str,
    payload: ClosureMaterializeRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.materialize_project_closure_actions(
            project_id,
            limit=payload.limit,
            action_kind=payload.action_kind,
            target_id=payload.target_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/closure/execute")
async def execute_project_closure_action(
    project_id: str,
    payload: ClosureActionRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.execute_project_closure_action(
            project_id,
            action_kind=payload.action_kind,
            target_id=payload.target_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/closure/actions/apply")
async def apply_project_closure_actions(
    project_id: str,
    payload: ClosureActionBatchRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.apply_project_closure_actions(
            project_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/package")
async def create_project_package(project_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.create_project_submission_package(project_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/projects/{project_id}/blockers")
async def list_project_blockers(
    project_id: str,
    req: Request,
    kind: str = "",
    status: str = "",
    stage: str = "",
    workflow_id: str = "",
    ready_for_retry: bool | None = Query(default=None),
    query: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_project_blockers(
            project_id,
            kind=kind,
            status=status,
            stage=stage,
            workflow_id=workflow_id,
            ready_for_retry=ready_for_retry,
            query=query,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/blockers/apply")
async def apply_project_blockers(
    project_id: str,
    payload: ProjectBlockerBatchRequest,
    req: Request,
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.apply_project_blocker_tasks(
            project_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/blockers/dispatch")
async def dispatch_project_blockers(
    project_id: str,
    req: Request,
    workflow_limit: int = Query(3, ge=1, le=20),
    task_limit: int = Query(2, ge=1, le=10),
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.dispatch_project_blocker_tasks(
            project_id,
            workflow_limit=workflow_limit,
            task_limit=task_limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/blockers/execute")
async def execute_project_blockers(
    project_id: str,
    req: Request,
    workflow_limit: int = Query(3, ge=1, le=20),
    task_limit: int = Query(2, ge=1, le=10),
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.execute_project_blocker_tasks(
            project_id,
            workflow_limit=workflow_limit,
            task_limit=task_limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/blockers/resume")
async def resume_project_blockers(
    project_id: str,
    req: Request,
    workflow_limit: int = Query(3, ge=1, le=20),
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.resume_project_ready_workflows(
            project_id,
            workflow_limit=workflow_limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/projects/{project_id}/paper-watches")
async def add_project_paper_watch(
    project_id: str,
    payload: PaperWatchCreateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.add_project_paper_watch(project_id=project_id, **payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/workflows")
async def list_workflows(
    req: Request,
    project_id: str = Query("", description="Filter by project ID"),
    status: str = Query("", description="Filter by workflow status"),
):
    service = _get_research_service(req)
    return await service.list_workflows(project_id=project_id, status=status)


@router.post("/workflows")
async def create_workflow(payload: WorkflowCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.create_workflow(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_workflow(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/workflows/{workflow_id}/remediation")
async def get_workflow_contract_remediation(workflow_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_workflow_contract_remediation_context(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/remediation/dispatch")
async def dispatch_workflow_remediation(
    workflow_id: str,
    req: Request,
    limit: int = Query(3, ge=1, le=10),
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.dispatch_workflow_remediation_tasks(
            workflow_id,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/remediation/execute")
async def execute_workflow_remediation(
    workflow_id: str,
    req: Request,
    limit: int = Query(3, ge=1, le=10),
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.execute_workflow_remediation_tasks(
            workflow_id,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/tick")
async def tick_workflow(workflow_id: str, req: Request):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.tick_workflow(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    payload: WorkflowExecuteRequest,
    req: Request,
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.execute_workflow_step(
            workflow_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/workflows/{workflow_id}/execution-policy")
async def update_workflow_execution_policy(
    workflow_id: str,
    payload: WorkflowExecutionPolicyUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_workflow_execution_policy(
            workflow_id=workflow_id,
            patch=payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/workflows/{workflow_id}/experiment-runner")
async def update_workflow_experiment_runner(
    workflow_id: str,
    payload: ExperimentRunnerProfileUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_workflow_experiment_runner(
            workflow_id=workflow_id,
            patch=payload.model_dump(
                mode="json",
                exclude_none=True,
                exclude_unset=True,
            ),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/pause")
async def pause_workflow(workflow_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.pause_workflow(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/resume")
async def resume_workflow(workflow_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.resume_workflow(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.cancel_workflow(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/retry")
async def retry_workflow(workflow_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.retry_workflow(workflow_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/workflows/{workflow_id}/checkpoints")
async def list_workflow_checkpoints(
    workflow_id: str,
    req: Request,
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_workflow_checkpoints(
            workflow_id=workflow_id,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/restore")
async def restore_workflow_checkpoint(
    workflow_id: str,
    payload: WorkflowRestoreRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.restore_workflow_checkpoint(
            workflow_id=workflow_id,
            checkpoint_id=payload.checkpoint_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/tasks")
async def add_workflow_task(
    workflow_id: str,
    payload: WorkflowTaskCreateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.add_workflow_task(
            workflow_id=workflow_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/workflows/{workflow_id}/tasks/{task_id}")
async def get_workflow_task(
    workflow_id: str,
    task_id: str,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.get_workflow_task(
            workflow_id=workflow_id,
            task_id=task_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/workflows/{workflow_id}/tasks/{task_id}")
async def update_workflow_task(
    workflow_id: str,
    task_id: str,
    payload: WorkflowTaskUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_workflow_task(
            workflow_id=workflow_id,
            task_id=task_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/tasks/{task_id}/dispatch")
async def dispatch_workflow_task(
    workflow_id: str,
    task_id: str,
    req: Request,
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.dispatch_workflow_task_followup(
            workflow_id=workflow_id,
            task_id=task_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/workflows/{workflow_id}/tasks/{task_id}/execute")
async def execute_workflow_task(
    workflow_id: str,
    task_id: str,
    req: Request,
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.execute_workflow_task(
            workflow_id=workflow_id,
            task_id=task_id,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/notes")
async def list_notes(
    req: Request,
    query: str = "",
    note_type: str = "",
    tag: str = "",
    project_id: str = "",
    workflow_id: str = "",
    claim_id: str = "",
    experiment_id: str = "",
    limit: int = 50,
):
    service = _get_research_service(req)
    return await service.list_notes(
        query=query,
        note_type=note_type,
        tags=[tag] if tag else None,
        project_id=project_id,
        workflow_id=workflow_id,
        claim_id=claim_id,
        experiment_id=experiment_id,
        limit=limit,
    )


@router.get("/artifacts")
async def list_artifacts(
    req: Request,
    project_id: str = "",
    workflow_id: str = "",
    artifact_type: str = "",
    source_type: str = "",
    query: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    return await service.list_artifacts(
        project_id=project_id,
        workflow_id=workflow_id,
        artifact_type=artifact_type,
        source_type=source_type,
        query=query,
        limit=limit,
    )


@router.post("/artifacts")
async def upsert_artifact(payload: ArtifactUpsertRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.upsert_artifact(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/artifacts/{artifact_id}")
async def update_artifact(
    artifact_id: str,
    payload: ArtifactUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_artifact(
            artifact_id=artifact_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/artifacts/bulk-update")
async def bulk_update_artifacts(
    payload: ArtifactBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_artifacts(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/artifacts/{artifact_id}/lineage")
async def artifact_lineage(
    artifact_id: str,
    req: Request,
    direction: str = "both",
):
    service = _get_research_service(req)
    try:
        return await service.get_artifact_lineage(
            artifact_id,
            direction=direction,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/artifact-relations")
async def list_artifact_relations(
    req: Request,
    project_id: str = "",
    artifact_id: str = "",
    relation_type: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_artifact_relations(
            project_id=project_id,
            artifact_id=artifact_id,
            relation_type=relation_type,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/artifact-relations")
async def create_artifact_relation(
    payload: ArtifactRelationCreateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.create_artifact_relation(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/notes")
async def create_note(payload: NoteCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.create_note(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/notes/{note_id}")
async def update_note(
    note_id: str,
    payload: NoteUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_note(
            note_id=note_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/notes/bulk-update")
async def bulk_update_notes(
    payload: NoteBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_notes(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/claims")
async def list_claims(
    req: Request,
    project_id: str = "",
    workflow_id: str = "",
    status: str = "",
    query: str = "",
    has_evidence: bool | None = Query(default=None),
    limit: int = 100,
):
    service = _get_research_service(req)
    return await service.list_claims(
        project_id=project_id,
        workflow_id=workflow_id,
        status=status,
        query=query,
        has_evidence=has_evidence,
        limit=limit,
    )


@router.post("/claims")
async def create_claim(payload: ClaimCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.create_claim(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/claims/{claim_id}")
async def update_claim(
    claim_id: str,
    payload: ClaimUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_claim(
            claim_id=claim_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/claims/bulk-update")
async def bulk_update_claims(
    payload: ClaimBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_claims(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/claims/{claim_id}/graph")
async def claim_graph(claim_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_claim_graph(claim_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/claims/{claim_id}/validate")
async def validate_claim(
    claim_id: str,
    payload: ClaimValidationRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.validate_claim(
            claim_id,
            apply_status=payload.apply_status,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/evidences")
async def create_evidence(payload: EvidenceCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.attach_evidence(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/evidences")
async def list_evidences(
    req: Request,
    project_id: str = "",
    workflow_id: str = "",
    claim_id: str = "",
    evidence_type: str = "",
    source_type: str = "",
    query: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_evidences(
            project_id=project_id,
            workflow_id=workflow_id,
            claim_id=claim_id,
            evidence_type=evidence_type,
            source_type=source_type,
            query=query,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/evidences/{evidence_id}")
async def update_evidence(
    evidence_id: str,
    payload: EvidenceUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_evidence(
            evidence_id=evidence_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/evidences/bulk-update")
async def bulk_update_evidences(
    payload: EvidenceBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_evidences(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/dataset-versions")
async def list_dataset_versions(
    req: Request,
    project_id: str = "",
    workflow_id: str = "",
    name: str = "",
    name_query: str = "",
    tag: str = "",
    parent_version_id: str = "",
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_dataset_versions(
            project_id=project_id,
            workflow_id=workflow_id,
            name=name,
            name_query=name_query,
            tag=tag,
            parent_version_id=parent_version_id,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/dataset-versions")
async def create_dataset_version(payload: DatasetVersionCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.create_dataset_version(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/dataset-versions/{dataset_version_id}")
async def update_dataset_version(
    dataset_version_id: str,
    payload: DatasetVersionUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_dataset_version(
            dataset_version_id=dataset_version_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/dataset-versions/bulk-update")
async def bulk_update_dataset_versions(
    payload: DatasetVersionBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_dataset_versions(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/experiments")
async def list_experiments(
    req: Request,
    project_id: str = "",
    workflow_id: str = "",
    status: str = "",
    execution_mode: str = "",
    query: str = "",
    replayable: bool | None = Query(default=None),
    limit: int = 100,
):
    service = _get_research_service(req)
    return await service.list_experiments(
        project_id=project_id,
        workflow_id=workflow_id,
        status=status,
        execution_mode=execution_mode,
        query=query,
        replayable=replayable,
        limit=limit,
    )


@router.post("/experiments")
async def create_experiment(payload: ExperimentCreateRequest, req: Request):
    service = _get_research_service(req)
    try:
        return await service.log_experiment(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_experiment(experiment_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/experiments/{experiment_id}/contract")
async def get_experiment_artifact_contract(experiment_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_experiment_artifact_contract_validation(experiment_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/experiments/{experiment_id}/remediation")
async def get_experiment_contract_remediation(experiment_id: str, req: Request):
    service = _get_research_service(req)
    try:
        return await service.get_experiment_contract_remediation(experiment_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/experiments/{experiment_id}")
async def update_experiment(
    experiment_id: str,
    payload: ExperimentUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.update_experiment(
            experiment_id=experiment_id,
            **payload.model_dump(
                mode="json",
                exclude_none=True,
                exclude_unset=True,
            ),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/bulk-update")
async def bulk_update_experiments(
    payload: ExperimentBulkUpdateRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.bulk_update_experiments(**payload.model_dump(mode="json"))
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.patch("/experiments/{experiment_id}/execution")
async def configure_experiment_execution(
    experiment_id: str,
    payload: ExperimentExecutionConfigureRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.configure_experiment_execution(
            experiment_id=experiment_id,
            patch=payload.model_dump(
                mode="json",
                exclude_none=True,
                exclude_unset=True,
            ),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/{experiment_id}/provenance/capture")
async def capture_experiment_provenance(
    experiment_id: str,
    payload: ExperimentProvenanceCaptureRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.capture_experiment_provenance(
            experiment_id=experiment_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/experiments/{experiment_id}/replay-plan")
async def get_experiment_replay_plan(
    experiment_id: str,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.get_experiment_replay_plan(experiment_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.get("/experiments/{experiment_id}/events")
async def list_experiment_events(
    experiment_id: str,
    req: Request,
    limit: int = 100,
):
    service = _get_research_service(req)
    try:
        return await service.list_experiment_events(
            experiment_id=experiment_id,
            limit=limit,
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/{experiment_id}/heartbeat")
async def record_experiment_heartbeat(
    experiment_id: str,
    payload: ExperimentHeartbeatRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.record_experiment_heartbeat(
            experiment_id=experiment_id,
            **payload.model_dump(mode="json"),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/{experiment_id}/result")
async def record_experiment_result(
    experiment_id: str,
    payload: ExperimentResultRequest,
    req: Request,
):
    service = _get_research_service(req)
    try:
        return await service.record_experiment_result(
            experiment_id=experiment_id,
            **payload.model_dump(mode="json", exclude_none=True),
        )
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/{experiment_id}/launch")
async def launch_experiment(
    experiment_id: str,
    req: Request,
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.execute_experiment(experiment_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/{experiment_id}/replay")
async def replay_experiment(
    experiment_id: str,
    req: Request,
):
    runtime = _get_research_runtime(req)
    try:
        return await runtime.replay_experiment(experiment_id)
    except Exception as exc:
        raise _translate_errors(exc) from exc


@router.post("/experiments/compare")
async def compare_experiments(
    payload: CompareExperimentsRequest,
    req: Request,
):
    service = _get_research_service(req)
    return await service.compare_experiments(payload.experiment_ids)


@router.get("/reminders")
async def preview_reminders(
    req: Request,
    project_id: str = "",
    stale_hours: int = RESEARCH_WORKFLOW_STALE_HOURS,
):
    runtime = _get_research_runtime(req)
    return await runtime.preview_reminders(
        project_id=project_id,
        stale_hours=stale_hours,
    )


@router.post("/reminders/run")
async def run_reminders(payload: ReminderRunRequest, req: Request):
    runtime = _get_research_runtime(req)
    return await runtime.run_proactive_cycle(
        project_id=payload.project_id,
        stale_hours=payload.stale_hours,
    )
