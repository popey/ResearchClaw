import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  Database,
  FileText,
  FolderOpen,
  GitBranch,
  RefreshCw,
  RotateCcw,
  Workflow,
} from "lucide-react";
import {
  applyResearchProjectBlockers,
  applyResearchProjectClosureActions,
  bulkUpdateResearchExperiments,
  bulkUpdateResearchEvidences,
  bulkUpdateResearchNotes,
  bulkUpdateResearchArtifacts,
  bulkUpdateResearchClaims,
  bulkUpdateResearchDatasetVersions,
  bulkUpdateResearchProjectMemory,
  createResearchDatasetVersion,
  createResearchProjectMemory,
  createResearchProjectPackage,
  dispatchResearchProjectBlockers,
  dispatchResearchWorkflowRemediation,
  dispatchResearchWorkflowTask,
  executeResearchProjectBlockers,
  executeResearchProjectClosureAction,
  executeResearchWorkflow,
  executeResearchWorkflowRemediation,
  executeResearchWorkflowTask,
  getResearchClaimGraph,
  getResearchArtifactLineage,
  getResearchExperimentReplayPlan,
  getResearchProjectClosure,
  getResearchOverview,
  getResearchProjectDashboard,
  getResearchWorkflowRemediation,
  listResearchProjectBlockers,
  listResearchProjectClosureActions,
  listResearchArtifactRelations,
  listResearchArtifacts,
  listResearchAuditEvents,
  listResearchClaims,
  listResearchDatasetVersions,
  listResearchEvidences,
  listResearchExperiments,
  listResearchNotes,
  listResearchProjectMemory,
  listResearchProjects,
  listResearchWorkflowCheckpoints,
  listResearchWorkflows,
  materializeResearchProjectClosure,
  previewResearchReminders,
  replayResearchExperiment,
  resumeResearchProjectBlockers,
  restoreResearchWorkflowCheckpoint,
  updateResearchDatasetVersion,
  updateResearchProjectMemory,
} from "../api";
import {
  Badge,
  DataRow,
  DetailModal,
  EmptyState,
  Loading,
  NoticeBanner,
  PageHeader,
  StatCard,
  SurfaceCard,
} from "../components/ui";
import { useI18n } from "../i18n";
import type {
  ResearchArtifactItem,
  ResearchArtifactBulkUpdateResult,
  ResearchArtifactLineage,
  ResearchArtifactRelation,
  ResearchAuditEvent,
  ResearchClaimGraph,
  ResearchClaimBulkUpdateResult,
  ResearchClaimItem,
  ResearchClosureActionBatchResult,
  ResearchClosureActionItem,
  ResearchClosureActionExecuteResult,
  ResearchClosureReport,
  ResearchDashboard,
  ResearchDatasetVersion,
  ResearchDatasetVersionBulkUpdateResult,
  ResearchEvidenceBulkUpdateResult,
  ResearchEvidenceItem,
  ResearchExperimentBulkUpdateResult,
  ResearchExperimentItem,
  ResearchExperimentReplayPlan,
  ResearchNoteBulkUpdateResult,
  ResearchNoteItem,
  ResearchOverview,
  ResearchProjectBlockerBatchResult,
  ResearchProjectBlockerItem,
  ResearchProjectMemoryEntry,
  ResearchProjectMemoryBulkUpdateResult,
  ResearchProjectPackageResult,
  ResearchProjectItem,
  ResearchReminderItem,
  ResearchWorkflowCheckpoint,
  ResearchWorkflowRemediationContext,
  ResearchWorkflowItem,
} from "../types";

function statusVariant(
  status: string,
): "success" | "warning" | "danger" | "info" | "neutral" {
  const normalized = String(status || "").toLowerCase();
  if (["high"].includes(normalized)) {
    return "danger";
  }
  if (["medium"].includes(normalized)) {
    return "warning";
  }
  if (["low", "in_progress"].includes(normalized)) {
    return "info";
  }
  if (["completed", "supported", "active"].includes(normalized)) {
    return "success";
  }
  if (["blocked", "failed", "disputed", "cancelled"].includes(normalized)) {
    return "danger";
  }
  if (["paused", "needs_review"].includes(normalized)) {
    return "warning";
  }
  if (["running", "queued", "draft"].includes(normalized)) {
    return "info";
  }
  return "neutral";
}

function createEmptyMemoryForm(workflowId = "") {
  return {
    title: "",
    content: "",
    entryKind: "fact",
    workflowId,
    stage: "",
    status: "active",
    tags: "",
    metadataText: "{}",
  };
}

function createEmptyDatasetForm(workflowId = "") {
  return {
    name: "",
    versionLabel: "v1",
    description: "",
    workflowId,
    parentVersionId: "",
    path: "",
    sourcePaths: "",
    splitSpecText: '{\n  "train": "train.jsonl"\n}',
    transformStepsText: "[]",
    primaryMetric: "accuracy",
    metadataText: "{}",
    tags: "",
  };
}

function createEmptyMemoryFilters() {
  return {
    workflowId: "",
    entryKind: "",
    status: "",
    stage: "",
    tag: "",
    query: "",
  };
}

function createEmptyBlockerFilters() {
  return {
    kind: "",
    workflowId: "",
    status: "",
    stage: "",
    readyForRetry: "",
    query: "",
  };
}

function createEmptyClosureActionFilters() {
  return {
    kind: "",
    severity: "",
    targetType: "",
    workflowId: "",
    autoExecutable: "",
    materializable: "",
    query: "",
  };
}

function createEmptyDatasetFilters() {
  return {
    workflowId: "",
    nameQuery: "",
    tag: "",
    parentVersionId: "",
  };
}

function createEmptyExperimentFilters() {
  return {
    workflowId: "",
    status: "",
    executionMode: "",
    replayable: "",
    query: "",
  };
}

function createEmptyNoteFilters() {
  return {
    workflowId: "",
    noteType: "",
    tag: "",
    query: "",
  };
}

function createEmptyClaimFilters() {
  return {
    workflowId: "",
    status: "",
    query: "",
    hasEvidence: "",
  };
}

function createEmptyArtifactFilters() {
  return {
    workflowId: "",
    artifactType: "",
    sourceType: "",
    query: "",
  };
}

function createEmptyEvidenceFilters() {
  return {
    workflowId: "",
    evidenceType: "",
    sourceType: "",
    query: "",
  };
}

function createEmptyMemoryBulkForm() {
  return {
    status: "",
    entryKind: "",
    workflowId: "",
    stage: "",
    addTags: "",
    removeTags: "",
  };
}

function createEmptyDatasetBulkForm() {
  return {
    workflowId: "",
    addTags: "",
    removeTags: "",
  };
}

function createEmptyExperimentBulkForm() {
  return {
    workflowId: "",
    status: "",
    comparisonGroup: "",
  };
}

function createEmptyNoteBulkForm() {
  return {
    workflowId: "",
    noteType: "",
    addTags: "",
    removeTags: "",
  };
}

function createEmptyClaimBulkForm() {
  return {
    status: "",
    workflowId: "",
  };
}

function createEmptyArtifactBulkForm() {
  return {
    workflowId: "",
    sourceType: "",
  };
}

function createEmptyEvidenceBulkForm() {
  return {
    workflowId: "",
    evidenceType: "",
    sourceType: "",
  };
}

function stringifyObjectInput(
  value: Record<string, unknown> | undefined,
  fallback = "{}",
) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return fallback;
  }
}

function stringifyArrayInput(
  value: Array<Record<string, unknown>> | undefined,
  fallback = "[]",
) {
  try {
    return JSON.stringify(value ?? [], null, 2);
  } catch {
    return fallback;
  }
}

function datasetMetadataInput(metadata: Record<string, unknown> | undefined) {
  if (!metadata) return "{}";
  const next = { ...metadata };
  delete next["primary_metric"];
  return stringifyObjectInput(next);
}

export default function ResearchPage() {
  const { t } = useI18n();
  const [overview, setOverview] = useState<ResearchOverview | null>(null);
  const [projects, setProjects] = useState<ResearchProjectItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [dashboard, setDashboard] = useState<ResearchDashboard | null>(null);
  const [closure, setClosure] = useState<ResearchClosureReport | null>(null);
  const [blockerRows, setBlockerRows] = useState<ResearchProjectBlockerItem[]>([]);
  const [closureActionRows, setClosureActionRows] = useState<
    ResearchClosureActionItem[]
  >([]);
  const [workflows, setWorkflows] = useState<ResearchWorkflowItem[]>([]);
  const [noteRows, setNoteRows] = useState<ResearchNoteItem[]>([]);
  const [, setClaims] = useState<ResearchClaimItem[]>([]);
  const [claimRows, setClaimRows] = useState<ResearchClaimItem[]>([]);
  const [evidenceRows, setEvidenceRows] = useState<ResearchEvidenceItem[]>([]);
  const [reminders, setReminders] = useState<ResearchReminderItem[]>([]);
  const [projectMemory, setProjectMemory] = useState<ResearchProjectMemoryEntry[]>(
    [],
  );
  const [auditEvents, setAuditEvents] = useState<ResearchAuditEvent[]>([]);
  const [datasetVersions, setDatasetVersions] = useState<ResearchDatasetVersion[]>(
    [],
  );
  const [experimentRows, setExperimentRows] = useState<ResearchExperimentItem[]>([]);
  const [artifacts, setArtifacts] = useState<ResearchArtifactItem[]>([]);
  const [artifactRows, setArtifactRows] = useState<ResearchArtifactItem[]>([]);
  const [artifactRelations, setArtifactRelations] = useState<
    ResearchArtifactRelation[]
  >([]);
  const [claimGraph, setClaimGraph] = useState<ResearchClaimGraph | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [claimLoadingId, setClaimLoadingId] = useState("");
  const [executingWorkflowId, setExecutingWorkflowId] = useState("");
  const [taskActionKey, setTaskActionKey] = useState("");
  const [projectActionKey, setProjectActionKey] = useState("");
  const [closureActionKey, setClosureActionKey] = useState("");
  const [packageResult, setPackageResult] =
    useState<ResearchProjectPackageResult | null>(null);
  const [notice, setNotice] = useState<{
    variant: "success" | "warning" | "danger" | "info";
    text: string;
  } | null>(null);
  const [remediationModal, setRemediationModal] = useState<{
    workflowId: string;
    title: string;
  } | null>(null);
  const [remediationContext, setRemediationContext] =
    useState<ResearchWorkflowRemediationContext | null>(null);
  const [remediationLoading, setRemediationLoading] = useState(false);
  const [checkpointModal, setCheckpointModal] = useState<{
    workflowId: string;
    title: string;
  } | null>(null);
  const [checkpoints, setCheckpoints] = useState<ResearchWorkflowCheckpoint[]>(
    [],
  );
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [checkpointActionKey, setCheckpointActionKey] = useState("");
  const [lineageModal, setLineageModal] = useState<{
    artifactId: string;
    title: string;
  } | null>(null);
  const [lineageData, setLineageData] = useState<ResearchArtifactLineage | null>(
    null,
  );
  const [lineageLoading, setLineageLoading] = useState(false);
  const [replayModal, setReplayModal] = useState<{
    experimentId: string;
    title: string;
  } | null>(null);
  const [replayPlan, setReplayPlan] = useState<ResearchExperimentReplayPlan | null>(
    null,
  );
  const [replayLoading, setReplayLoading] = useState(false);
  const [experimentActionKey, setExperimentActionKey] = useState("");
  const [editingMemoryId, setEditingMemoryId] = useState("");
  const [editingDatasetVersionId, setEditingDatasetVersionId] = useState("");
  const [memoryForm, setMemoryForm] = useState(createEmptyMemoryForm());
  const [datasetForm, setDatasetForm] = useState(createEmptyDatasetForm());
  const [memoryFormError, setMemoryFormError] = useState("");
  const [datasetFormError, setDatasetFormError] = useState("");
  const [memoryFilters, setMemoryFilters] = useState(createEmptyMemoryFilters());
  const [blockerFilters, setBlockerFilters] = useState(createEmptyBlockerFilters());
  const [closureActionFilters, setClosureActionFilters] = useState(
    createEmptyClosureActionFilters(),
  );
  const [datasetFilters, setDatasetFilters] = useState(createEmptyDatasetFilters());
  const [experimentFilters, setExperimentFilters] = useState(
    createEmptyExperimentFilters(),
  );
  const [noteFilters, setNoteFilters] = useState(createEmptyNoteFilters());
  const [claimFilters, setClaimFilters] = useState(createEmptyClaimFilters());
  const [artifactFilters, setArtifactFilters] = useState(createEmptyArtifactFilters());
  const [evidenceFilters, setEvidenceFilters] = useState(createEmptyEvidenceFilters());
  const [selectedMemoryIds, setSelectedMemoryIds] = useState<string[]>([]);
  const [selectedBlockerWorkflowIds, setSelectedBlockerWorkflowIds] = useState<
    string[]
  >([]);
  const [selectedClosureActionKeys, setSelectedClosureActionKeys] = useState<string[]>(
    [],
  );
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>([]);
  const [selectedExperimentIds, setSelectedExperimentIds] = useState<string[]>([]);
  const [selectedNoteIds, setSelectedNoteIds] = useState<string[]>([]);
  const [selectedClaimIds, setSelectedClaimIds] = useState<string[]>([]);
  const [selectedArtifactIds, setSelectedArtifactIds] = useState<string[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
  const [memoryBulkForm, setMemoryBulkForm] = useState(createEmptyMemoryBulkForm());
  const [datasetBulkForm, setDatasetBulkForm] = useState(createEmptyDatasetBulkForm());
  const [experimentBulkForm, setExperimentBulkForm] = useState(
    createEmptyExperimentBulkForm(),
  );
  const [noteBulkForm, setNoteBulkForm] = useState(createEmptyNoteBulkForm());
  const [claimBulkForm, setClaimBulkForm] = useState(createEmptyClaimBulkForm());
  const [artifactBulkForm, setArtifactBulkForm] = useState(
    createEmptyArtifactBulkForm(),
  );
  const [evidenceBulkForm, setEvidenceBulkForm] = useState(
    createEmptyEvidenceBulkForm(),
  );
  const [bulkActionKey, setBulkActionKey] = useState("");
  const [creationActionKey, setCreationActionKey] = useState("");

  const loadProjectMemoryRows = useCallback(
    async (projectId: string, filters = memoryFilters) => {
      const rows = await listResearchProjectMemory(projectId, {
        workflow_id: filters.workflowId,
        entry_kind: filters.entryKind,
        status: filters.status,
        stage: filters.stage,
        tag: filters.tag,
        query: filters.query,
        limit: 50,
      });
      setProjectMemory(rows);
      return rows;
    },
    [memoryFilters],
  );

  const loadProjectBlockerRows = useCallback(
    async (projectId: string, filters = blockerFilters) => {
      const rows = await listResearchProjectBlockers(projectId, {
        kind: filters.kind,
        workflow_id: filters.workflowId,
        status: filters.status,
        stage: filters.stage,
        ready_for_retry:
          filters.readyForRetry === ""
            ? undefined
            : filters.readyForRetry === "true",
        query: filters.query,
        limit: 50,
      });
      setBlockerRows(rows);
      return rows;
    },
    [blockerFilters],
  );

  const loadClosureActionRows = useCallback(
    async (projectId: string, filters = closureActionFilters) => {
      const rows = await listResearchProjectClosureActions(projectId, {
        kind: filters.kind,
        severity: filters.severity,
        target_type: filters.targetType,
        workflow_id: filters.workflowId,
        auto_executable:
          filters.autoExecutable === ""
            ? undefined
            : filters.autoExecutable === "true",
        materializable:
          filters.materializable === ""
            ? undefined
            : filters.materializable === "true",
        query: filters.query,
        limit: 50,
      });
      setClosureActionRows(rows);
      return rows;
    },
    [closureActionFilters],
  );

  const loadDatasetVersionRows = useCallback(
    async (projectId: string, filters = datasetFilters) => {
      const rows = await listResearchDatasetVersions(projectId, {
        workflow_id: filters.workflowId,
        name_query: filters.nameQuery,
        tag: filters.tag,
        parent_version_id: filters.parentVersionId,
        limit: 50,
      });
      setDatasetVersions(rows);
      return rows;
    },
    [datasetFilters],
  );

  const loadExperimentRows = useCallback(
    async (projectId: string, filters = experimentFilters) => {
      const rows = await listResearchExperiments(projectId, {
        workflow_id: filters.workflowId,
        status: filters.status,
        execution_mode: filters.executionMode,
        query: filters.query,
        replayable:
          filters.replayable === ""
            ? undefined
            : filters.replayable === "true",
        limit: 50,
      });
      setExperimentRows(rows);
      return rows;
    },
    [experimentFilters],
  );

  const loadNoteRows = useCallback(
    async (projectId: string, filters = noteFilters) => {
      const rows = await listResearchNotes({
        project_id: projectId,
        workflow_id: filters.workflowId,
        note_type: filters.noteType,
        tag: filters.tag,
        query: filters.query,
        limit: 50,
      });
      setNoteRows(rows);
      return rows;
    },
    [noteFilters],
  );

  const loadClaimRows = useCallback(
    async (projectId: string, filters = claimFilters) => {
      const rows = await listResearchClaims(projectId, {
        workflow_id: filters.workflowId,
        status: filters.status,
        query: filters.query,
        has_evidence:
          filters.hasEvidence === ""
            ? undefined
            : filters.hasEvidence === "true",
        limit: 50,
      });
      setClaimRows(rows);
      return rows;
    },
    [claimFilters],
  );

  const loadArtifactRows = useCallback(
    async (projectId: string, filters = artifactFilters) => {
      const rows = await listResearchArtifacts(projectId, {
        workflow_id: filters.workflowId,
        artifact_type: filters.artifactType,
        source_type: filters.sourceType,
        query: filters.query,
        limit: 50,
      });
      setArtifactRows(rows);
      return rows;
    },
    [artifactFilters],
  );

  const loadEvidenceRows = useCallback(
    async (projectId: string, filters = evidenceFilters) => {
      const rows = await listResearchEvidences({
        project_id: projectId,
        workflow_id: filters.workflowId,
        evidence_type: filters.evidenceType,
        source_type: filters.sourceType,
        query: filters.query,
        limit: 50,
      });
      setEvidenceRows(rows);
      return rows;
    },
    [evidenceFilters],
  );

  const loadProjectContext = useCallback(async (projectId: string) => {
    const [
      dashboardData,
      closureData,
      workflowData,
      claimData,
      reminderData,
      auditData,
      artifactData,
      relationData,
    ] = await Promise.all([
      getResearchProjectDashboard(projectId),
      getResearchProjectClosure(projectId),
      listResearchWorkflows(projectId),
      listResearchClaims(projectId, { limit: 40 }),
      previewResearchReminders(projectId),
      listResearchAuditEvents(projectId, { limit: 25 }),
      listResearchArtifacts(projectId, { limit: 40 }),
      listResearchArtifactRelations({ project_id: projectId, limit: 40 }),
    ]);
    setDashboard(dashboardData);
    setClosure(closureData);
    setWorkflows(workflowData);
    setClaims(claimData);
    setReminders(reminderData);
    setAuditEvents(auditData);
    setArtifacts(artifactData);
    setArtifactRelations(relationData);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewData, projectData] = await Promise.all([
        getResearchOverview(),
        listResearchProjects(),
      ]);
      setOverview(overviewData);
      setProjects(projectData);

      const nextProjectId =
        selectedProjectId || projectData[0]?.id || overviewData.projects[0]?.id;
      if (nextProjectId) {
        setSelectedProjectId(nextProjectId);
        await Promise.all([
          loadProjectContext(nextProjectId),
          loadProjectMemoryRows(nextProjectId),
          loadProjectBlockerRows(nextProjectId),
          loadClosureActionRows(nextProjectId),
          loadDatasetVersionRows(nextProjectId),
          loadExperimentRows(nextProjectId),
          loadNoteRows(nextProjectId),
          loadClaimRows(nextProjectId),
          loadArtifactRows(nextProjectId),
          loadEvidenceRows(nextProjectId),
        ]);
      } else {
        setDashboard(null);
        setClosure(null);
        setBlockerRows([]);
        setClosureActionRows([]);
        setWorkflows([]);
        setNoteRows([]);
        setClaims([]);
        setClaimRows([]);
        setEvidenceRows([]);
        setReminders([]);
        setProjectMemory([]);
        setAuditEvents([]);
        setDatasetVersions([]);
        setExperimentRows([]);
        setArtifacts([]);
        setArtifactRows([]);
        setArtifactRelations([]);
      }
    } finally {
      setLoading(false);
    }
  }, [
    loadArtifactRows,
    loadProjectBlockerRows,
    loadClaimRows,
    loadClosureActionRows,
    loadDatasetVersionRows,
    loadEvidenceRows,
    loadExperimentRows,
    loadNoteRows,
    loadProjectContext,
    loadProjectMemoryRows,
    selectedProjectId,
  ]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!selectedProjectId) return;
    void Promise.all([
      loadProjectContext(selectedProjectId),
      loadProjectMemoryRows(selectedProjectId, createEmptyMemoryFilters()),
      loadProjectBlockerRows(selectedProjectId, createEmptyBlockerFilters()),
      loadClosureActionRows(selectedProjectId, createEmptyClosureActionFilters()),
      loadDatasetVersionRows(selectedProjectId, createEmptyDatasetFilters()),
      loadExperimentRows(selectedProjectId, createEmptyExperimentFilters()),
      loadNoteRows(selectedProjectId, createEmptyNoteFilters()),
      loadClaimRows(selectedProjectId, createEmptyClaimFilters()),
      loadArtifactRows(selectedProjectId, createEmptyArtifactFilters()),
      loadEvidenceRows(selectedProjectId, createEmptyEvidenceFilters()),
    ]);
  }, [
    loadArtifactRows,
    loadProjectBlockerRows,
    loadClaimRows,
    loadClosureActionRows,
    loadDatasetVersionRows,
    loadEvidenceRows,
    loadExperimentRows,
    loadNoteRows,
    loadProjectContext,
    loadProjectMemoryRows,
    selectedProjectId,
  ]);

  useEffect(() => {
    setEditingMemoryId("");
    setEditingDatasetVersionId("");
    setMemoryForm(createEmptyMemoryForm());
    setDatasetForm(createEmptyDatasetForm());
    setMemoryFormError("");
    setDatasetFormError("");
    setMemoryFilters(createEmptyMemoryFilters());
    setBlockerFilters(createEmptyBlockerFilters());
    setClosureActionFilters(createEmptyClosureActionFilters());
    setDatasetFilters(createEmptyDatasetFilters());
    setExperimentFilters(createEmptyExperimentFilters());
    setNoteFilters(createEmptyNoteFilters());
    setClaimFilters(createEmptyClaimFilters());
    setArtifactFilters(createEmptyArtifactFilters());
    setEvidenceFilters(createEmptyEvidenceFilters());
    setSelectedMemoryIds([]);
    setSelectedBlockerWorkflowIds([]);
    setSelectedClosureActionKeys([]);
    setSelectedDatasetIds([]);
    setSelectedExperimentIds([]);
    setSelectedNoteIds([]);
    setSelectedClaimIds([]);
    setSelectedArtifactIds([]);
    setSelectedEvidenceIds([]);
    setMemoryBulkForm(createEmptyMemoryBulkForm());
    setDatasetBulkForm(createEmptyDatasetBulkForm());
    setExperimentBulkForm(createEmptyExperimentBulkForm());
    setNoteBulkForm(createEmptyNoteBulkForm());
    setClaimBulkForm(createEmptyClaimBulkForm());
    setArtifactBulkForm(createEmptyArtifactBulkForm());
    setEvidenceBulkForm(createEmptyEvidenceBulkForm());
  }, [selectedProjectId]);

  useEffect(() => {
    const workflowIds = new Set(workflows.map((workflow) => workflow.id));
    const defaultWorkflowId = workflows[0]?.id || "";
    setMemoryForm((current) =>
      current.workflowId && workflowIds.has(current.workflowId)
        ? current
        : { ...current, workflowId: defaultWorkflowId },
    );
    setDatasetForm((current) =>
      current.workflowId && workflowIds.has(current.workflowId)
        ? current
        : { ...current, workflowId: defaultWorkflowId },
    );
  }, [workflows]);

  useEffect(() => {
    if (!memoryFormError) return;
    setMemoryFormError("");
  }, [memoryForm]);

  useEffect(() => {
    if (!datasetFormError) return;
    setDatasetFormError("");
  }, [datasetForm]);

  useEffect(() => {
    setSelectedMemoryIds((current) =>
      current.filter((id) => projectMemory.some((item) => item.id === id)),
    );
  }, [projectMemory]);

  useEffect(() => {
    setSelectedBlockerWorkflowIds((current) =>
      current.filter((id) =>
        blockerRows.some((item) => item.workflow_id === id),
      ),
    );
  }, [blockerRows]);

  useEffect(() => {
    setSelectedClosureActionKeys((current) =>
      current.filter((id) =>
        closureActionRows.some((item) => item.closure_key === id),
      ),
    );
  }, [closureActionRows]);

  useEffect(() => {
    setSelectedDatasetIds((current) =>
      current.filter((id) => datasetVersions.some((item) => item.id === id)),
    );
  }, [datasetVersions]);

  useEffect(() => {
    setSelectedExperimentIds((current) =>
      current.filter((id) => experimentRows.some((item) => item.id === id)),
    );
  }, [experimentRows]);

  useEffect(() => {
    setSelectedNoteIds((current) =>
      current.filter((id) => noteRows.some((item) => item.id === id)),
    );
  }, [noteRows]);

  useEffect(() => {
    setSelectedClaimIds((current) =>
      current.filter((id) => claimRows.some((item) => item.id === id)),
    );
  }, [claimRows]);

  useEffect(() => {
    setSelectedArtifactIds((current) =>
      current.filter((id) => artifactRows.some((item) => item.id === id)),
    );
  }, [artifactRows]);

  useEffect(() => {
    setSelectedEvidenceIds((current) =>
      current.filter((id) => evidenceRows.some((item) => item.id === id)),
    );
  }, [evidenceRows]);

  function formatTimestamp(value?: string | null) {
    if (!value) return t("未记录");
    try {
      return new Date(value).toLocaleString();
    } catch {
      return value;
    }
  }

  function artifactTitle(artifactId?: string) {
    if (!artifactId) return "-";
    return (
      artifactRows.find((item) => item.id === artifactId)?.title
      || artifacts.find((item) => item.id === artifactId)?.title
      || artifactId
    );
  }

  function summarizeSplitSpec(splitSpec?: Record<string, unknown>) {
    const keys = Object.keys(splitSpec || {});
    if (!keys.length) return t("未声明 split");
    return keys.slice(0, 4).join(" / ");
  }

  function summarizeCommand(command?: string[]) {
    if (!command?.length) return t("无命令");
    return command.join(" ");
  }

  function datasetVersionLabel(datasetVersionId?: string) {
    if (!datasetVersionId) return t("无 parent");
    const dataset = datasetVersions.find((item) => item.id === datasetVersionId);
    if (!dataset) return datasetVersionId;
    return `${dataset.name} · ${dataset.version_label}`;
  }

  function mergeSelections(current: string[], nextIds: string[]) {
    return Array.from(new Set([...current, ...nextIds]));
  }

  function parseObjectInput(text: string, label: string) {
    const normalized = text.trim();
    if (!normalized) return {};
    try {
      const parsed = JSON.parse(normalized);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error(`${label} 需要是 JSON object。`);
      }
      return parsed as Record<string, unknown>;
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        throw new Error(
          `${label} 不是合法 JSON，请检查逗号、引号和括号。${error.message}`,
        );
      }
      throw error;
    }
  }

  function parseObjectArrayInput(text: string, label: string) {
    const normalized = text.trim();
    if (!normalized) return [];
    try {
      const parsed = JSON.parse(normalized);
      if (!Array.isArray(parsed)) {
        throw new Error(`${label} 需要是 JSON array。`);
      }
      for (const item of parsed) {
        if (!item || Array.isArray(item) || typeof item !== "object") {
          throw new Error(`${label} 的每一项都需要是 JSON object。`);
        }
      }
      return parsed as Array<Record<string, unknown>>;
    } catch (error: any) {
      if (error instanceof SyntaxError) {
        throw new Error(
          `${label} 不是合法 JSON，请检查逗号、引号和括号。${error.message}`,
        );
      }
      throw error;
    }
  }

  function parseTags(text: string) {
    return text
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function parseLines(text: string) {
    return text
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function toggleVisibleSelection(
    current: string[],
    visibleIds: string[],
  ) {
    if (!visibleIds.length) return current;
    const hasAll = visibleIds.every((id) => current.includes(id));
    if (hasAll) {
      return current.filter((id) => !visibleIds.includes(id));
    }
    return mergeSelections(current, visibleIds);
  }

  function resetMemoryEditor() {
    setEditingMemoryId("");
    setMemoryForm(createEmptyMemoryForm(workflows[0]?.id || ""));
    setMemoryFormError("");
  }

  function resetDatasetEditor() {
    setEditingDatasetVersionId("");
    setDatasetForm(createEmptyDatasetForm(workflows[0]?.id || ""));
    setDatasetFormError("");
  }

  function startMemoryEdit(entry: ResearchProjectMemoryEntry) {
    setEditingMemoryId(entry.id);
    setMemoryForm({
      title: entry.title || "",
      content: entry.content || "",
      entryKind: entry.entry_kind || "fact",
      workflowId: entry.workflow_id || workflows[0]?.id || "",
      stage: entry.stage || "",
      status: entry.status || "active",
      tags: (entry.tags || []).join(", "),
      metadataText: stringifyObjectInput(entry.metadata),
    });
    setMemoryFormError("");
    setNotice(null);
  }

  function startDatasetEdit(dataset: ResearchDatasetVersion) {
    setEditingDatasetVersionId(dataset.id);
    setDatasetForm({
      name: dataset.name || "",
      versionLabel: dataset.version_label || "v1",
      description: dataset.description || "",
      workflowId: dataset.workflow_id || workflows[0]?.id || "",
      parentVersionId: dataset.parent_version_id || "",
      path: dataset.path || "",
      sourcePaths: (dataset.source_paths || []).join("\n"),
      splitSpecText: stringifyObjectInput(
        dataset.split_spec,
        '{\n  "train": "train.jsonl"\n}',
      ),
      transformStepsText: stringifyArrayInput(dataset.transform_steps),
      primaryMetric: String(dataset.metadata?.["primary_metric"] || ""),
      metadataText: datasetMetadataInput(dataset.metadata),
      tags: (dataset.tags || []).join(", "),
    });
    setDatasetFormError("");
    setNotice(null);
  }

  async function applyMemoryFilters(filters = memoryFilters) {
    if (!selectedProjectId) return;
    await loadProjectMemoryRows(selectedProjectId, filters);
  }

  async function clearMemoryFilters() {
    const next = createEmptyMemoryFilters();
    setMemoryFilters(next);
    if (!selectedProjectId) return;
    await loadProjectMemoryRows(selectedProjectId, next);
  }

  async function applyBlockerFilters(filters = blockerFilters) {
    if (!selectedProjectId) return;
    await loadProjectBlockerRows(selectedProjectId, filters);
  }

  async function clearBlockerFilters() {
    const next = createEmptyBlockerFilters();
    setBlockerFilters(next);
    if (!selectedProjectId) return;
    await loadProjectBlockerRows(selectedProjectId, next);
  }

  async function applyDatasetFilters(filters = datasetFilters) {
    if (!selectedProjectId) return;
    await loadDatasetVersionRows(selectedProjectId, filters);
  }

  async function clearDatasetFilters() {
    const next = createEmptyDatasetFilters();
    setDatasetFilters(next);
    if (!selectedProjectId) return;
    await loadDatasetVersionRows(selectedProjectId, next);
  }

  async function applyClosureActionFilters(filters = closureActionFilters) {
    if (!selectedProjectId) return;
    await loadClosureActionRows(selectedProjectId, filters);
  }

  async function clearClosureActionFilters() {
    const next = createEmptyClosureActionFilters();
    setClosureActionFilters(next);
    if (!selectedProjectId) return;
    await loadClosureActionRows(selectedProjectId, next);
  }

  async function applyExperimentFilters(filters = experimentFilters) {
    if (!selectedProjectId) return;
    await loadExperimentRows(selectedProjectId, filters);
  }

  async function clearExperimentFilters() {
    const next = createEmptyExperimentFilters();
    setExperimentFilters(next);
    if (!selectedProjectId) return;
    await loadExperimentRows(selectedProjectId, next);
  }

  async function applyNoteFilters(filters = noteFilters) {
    if (!selectedProjectId) return;
    await loadNoteRows(selectedProjectId, filters);
  }

  async function clearNoteFilters() {
    const next = createEmptyNoteFilters();
    setNoteFilters(next);
    if (!selectedProjectId) return;
    await loadNoteRows(selectedProjectId, next);
  }

  async function applyClaimFilters(filters = claimFilters) {
    if (!selectedProjectId) return;
    await loadClaimRows(selectedProjectId, filters);
  }

  async function clearClaimFilters() {
    const next = createEmptyClaimFilters();
    setClaimFilters(next);
    if (!selectedProjectId) return;
    await loadClaimRows(selectedProjectId, next);
  }

  async function applyArtifactFilters(filters = artifactFilters) {
    if (!selectedProjectId) return;
    await loadArtifactRows(selectedProjectId, filters);
  }

  async function clearArtifactFilters() {
    const next = createEmptyArtifactFilters();
    setArtifactFilters(next);
    if (!selectedProjectId) return;
    await loadArtifactRows(selectedProjectId, next);
  }

  async function applyEvidenceFilters(filters = evidenceFilters) {
    if (!selectedProjectId) return;
    await loadEvidenceRows(selectedProjectId, filters);
  }

  async function clearEvidenceFilters() {
    const next = createEmptyEvidenceFilters();
    setEvidenceFilters(next);
    if (!selectedProjectId) return;
    await loadEvidenceRows(selectedProjectId, next);
  }

  async function openClaimGraph(claimId: string) {
    setClaimLoadingId(claimId);
    try {
      const graph = await getResearchClaimGraph(claimId);
      setClaimGraph(graph);
    } finally {
      setClaimLoadingId("");
    }
  }

  async function openWorkflowCheckpoints(workflowId: string, title: string) {
    setCheckpointModal({ workflowId, title });
    setCheckpointLoading(true);
    try {
      const rows = await listResearchWorkflowCheckpoints(workflowId, 30);
      setCheckpoints(rows);
    } finally {
      setCheckpointLoading(false);
    }
  }

  async function restoreCheckpoint(workflowId: string, checkpointId: string) {
    setCheckpointActionKey(checkpointId);
    setNotice(null);
    try {
      await restoreResearchWorkflowCheckpoint(workflowId, checkpointId);
      const rows = await listResearchWorkflowCheckpoints(workflowId, 30);
      setCheckpoints(rows);
      await refreshResearchViews(workflowId);
      setNotice({
        variant: "success",
        text: t("Workflow 已从 checkpoint 恢复。"),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Checkpoint 恢复失败"),
      });
    } finally {
      setCheckpointActionKey("");
    }
  }

  async function openArtifactLineage(artifactId: string, title: string) {
    setLineageModal({ artifactId, title });
    setLineageLoading(true);
    try {
      const data = await getResearchArtifactLineage(artifactId);
      setLineageData(data);
    } finally {
      setLineageLoading(false);
    }
  }

  async function openExperimentReplay(experimentId: string, title: string) {
    setReplayModal({ experimentId, title });
    setReplayLoading(true);
    try {
      const plan = await getResearchExperimentReplayPlan(experimentId);
      setReplayPlan(plan);
    } finally {
      setReplayLoading(false);
    }
  }

  async function triggerExperimentReplay(experimentId: string) {
    setExperimentActionKey(experimentId);
    setNotice(null);
    try {
      await replayResearchExperiment(experimentId);
      const plan = await getResearchExperimentReplayPlan(experimentId);
      setReplayPlan(plan);
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t("已触发 experiment replay。"),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Experiment replay 失败"),
      });
    } finally {
      setExperimentActionKey("");
    }
  }

  async function submitProjectMemory() {
    if (!selectedProjectId || !memoryForm.title.trim() || !memoryForm.content.trim()) {
      setMemoryFormError(t("请先填写 memory 标题和内容。"));
      setNotice({
        variant: "warning",
        text: t("请先填写 memory 标题和内容。"),
      });
      return;
    }
    setCreationActionKey("memory");
    setMemoryFormError("");
    setNotice(null);
    try {
      const metadata = parseObjectInput(memoryForm.metadataText, "metadata");
      const payload = {
        title: memoryForm.title.trim(),
        content: memoryForm.content.trim(),
        entry_kind: memoryForm.entryKind,
        workflow_id: memoryForm.workflowId,
        stage: memoryForm.stage.trim(),
        status: memoryForm.status,
        tags: parseTags(memoryForm.tags),
        metadata,
      };
      if (editingMemoryId) {
        await updateResearchProjectMemory(
          selectedProjectId,
          editingMemoryId,
          payload,
        );
      } else {
        await createResearchProjectMemory(selectedProjectId, payload);
      }
      resetMemoryEditor();
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: editingMemoryId ? t("项目记忆已更新。") : t("项目记忆已创建。"),
      });
    } catch (error: any) {
      setMemoryFormError(error?.message || t("项目记忆保存失败"));
      setNotice({
        variant: "danger",
        text: error?.message || t("项目记忆保存失败"),
      });
    } finally {
      setCreationActionKey("");
    }
  }

  async function submitDatasetVersion() {
    if (!selectedProjectId || !datasetForm.name.trim()) {
      setDatasetFormError(t("请先填写 dataset 名称。"));
      setNotice({
        variant: "warning",
        text: t("请先填写 dataset 名称。"),
      });
      return;
    }
    setCreationActionKey("dataset");
    setDatasetFormError("");
    setNotice(null);
    try {
      const splitSpec = parseObjectInput(datasetForm.splitSpecText, "split_spec");
      const transformSteps = parseObjectArrayInput(
        datasetForm.transformStepsText,
        "transform_steps",
      );
      const metadata = parseObjectInput(datasetForm.metadataText, "dataset metadata");
      if (datasetForm.primaryMetric.trim()) {
        metadata["primary_metric"] = datasetForm.primaryMetric.trim();
      }
      const payload = {
        name: datasetForm.name.trim(),
        version_label: datasetForm.versionLabel.trim() || "v1",
        description: datasetForm.description.trim(),
        workflow_id: datasetForm.workflowId,
        parent_version_id: datasetForm.parentVersionId,
        path: datasetForm.path.trim(),
        source_paths: parseLines(datasetForm.sourcePaths),
        split_spec: splitSpec,
        transform_steps: transformSteps,
        tags: parseTags(datasetForm.tags),
        metadata,
      };
      if (editingDatasetVersionId) {
        await updateResearchDatasetVersion(editingDatasetVersionId, payload);
      } else {
        await createResearchDatasetVersion({
          project_id: selectedProjectId,
          ...payload,
        });
      }
      resetDatasetEditor();
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: editingDatasetVersionId
          ? t("Dataset version 已更新。")
          : t("Dataset version 已创建。"),
      });
    } catch (error: any) {
      setDatasetFormError(error?.message || t("Dataset version 保存失败"));
      setNotice({
        variant: "danger",
        text: error?.message || t("Dataset version 保存失败"),
      });
    } finally {
      setCreationActionKey("");
    }
  }

  async function applyMemoryBulkUpdate() {
    if (!selectedProjectId || !selectedMemoryIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一条项目记忆。"),
      });
      return;
    }
    const payload = {
      memory_ids: selectedMemoryIds,
      status: memoryBulkForm.status || undefined,
      entry_kind: memoryBulkForm.entryKind || undefined,
      workflow_id: memoryBulkForm.workflowId || undefined,
      stage: memoryBulkForm.stage.trim() || undefined,
      add_tags: parseTags(memoryBulkForm.addTags),
      remove_tags: parseTags(memoryBulkForm.removeTags),
    };
    if (
      !payload.status
      && !payload.entry_kind
      && payload.workflow_id === undefined
      && !payload.stage
      && !payload.add_tags.length
      && !payload.remove_tags.length
    ) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 memory 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("memory");
    setNotice(null);
    try {
      const result: ResearchProjectMemoryBulkUpdateResult =
        await bulkUpdateResearchProjectMemory(selectedProjectId, payload);
      setSelectedMemoryIds([]);
      setMemoryBulkForm(createEmptyMemoryBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 条项目记忆。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("项目记忆批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function applyDatasetBulkUpdate() {
    if (!selectedProjectId || !selectedDatasetIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一个数据版本。"),
      });
      return;
    }
    const payload = {
      project_id: selectedProjectId,
      dataset_version_ids: selectedDatasetIds,
      workflow_id: datasetBulkForm.workflowId || undefined,
      add_tags: parseTags(datasetBulkForm.addTags),
      remove_tags: parseTags(datasetBulkForm.removeTags),
    };
    if (
      payload.workflow_id === undefined
      && !payload.add_tags.length
      && !payload.remove_tags.length
    ) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 dataset 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("dataset");
    setNotice(null);
    try {
      const result: ResearchDatasetVersionBulkUpdateResult =
        await bulkUpdateResearchDatasetVersions(payload);
      setSelectedDatasetIds([]);
      setDatasetBulkForm(createEmptyDatasetBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 个数据版本。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("数据版本批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function applyExperimentBulkUpdate() {
    if (!selectedProjectId || !selectedExperimentIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一个实验。"),
      });
      return;
    }
    const payload = {
      project_id: selectedProjectId,
      experiment_ids: selectedExperimentIds,
      workflow_id: experimentBulkForm.workflowId || undefined,
      status: experimentBulkForm.status || undefined,
      comparison_group: experimentBulkForm.comparisonGroup.trim() || undefined,
    };
    if (
      payload.workflow_id === undefined
      && payload.status === undefined
      && payload.comparison_group === undefined
    ) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 experiment 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("experiment");
    setNotice(null);
    try {
      const result: ResearchExperimentBulkUpdateResult =
        await bulkUpdateResearchExperiments(payload);
      setSelectedExperimentIds([]);
      setExperimentBulkForm(createEmptyExperimentBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 个实验。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Experiment 批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function applyNoteBulkUpdate() {
    if (!selectedProjectId || !selectedNoteIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一条 note。"),
      });
      return;
    }
    const payload = {
      project_id: selectedProjectId,
      note_ids: selectedNoteIds,
      workflow_id: noteBulkForm.workflowId || undefined,
      note_type: noteBulkForm.noteType || undefined,
      add_tags: parseTags(noteBulkForm.addTags),
      remove_tags: parseTags(noteBulkForm.removeTags),
    };
    if (
      payload.workflow_id === undefined
      && payload.note_type === undefined
      && !payload.add_tags.length
      && !payload.remove_tags.length
    ) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 note 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("note");
    setNotice(null);
    try {
      const result: ResearchNoteBulkUpdateResult =
        await bulkUpdateResearchNotes(payload);
      setSelectedNoteIds([]);
      setNoteBulkForm(createEmptyNoteBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 条 note。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Note 批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function applyClaimBulkUpdate() {
    if (!selectedProjectId || !selectedClaimIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一个 claim。"),
      });
      return;
    }
    const payload = {
      project_id: selectedProjectId,
      claim_ids: selectedClaimIds,
      status: claimBulkForm.status || undefined,
      workflow_id: claimBulkForm.workflowId || undefined,
    };
    if (!payload.status && payload.workflow_id === undefined) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 claim 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("claim");
    setNotice(null);
    try {
      const result: ResearchClaimBulkUpdateResult =
        await bulkUpdateResearchClaims(payload);
      setSelectedClaimIds([]);
      setClaimBulkForm(createEmptyClaimBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 条 claim。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Claim 批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function applyEvidenceBulkUpdate() {
    if (!selectedProjectId || !selectedEvidenceIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一条 evidence。"),
      });
      return;
    }
    const payload = {
      project_id: selectedProjectId,
      evidence_ids: selectedEvidenceIds,
      workflow_id: evidenceBulkForm.workflowId || undefined,
      evidence_type: evidenceBulkForm.evidenceType || undefined,
      source_type: evidenceBulkForm.sourceType || undefined,
    };
    if (
      payload.workflow_id === undefined
      && payload.evidence_type === undefined
      && payload.source_type === undefined
    ) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 evidence 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("evidence");
    setNotice(null);
    try {
      const result: ResearchEvidenceBulkUpdateResult =
        await bulkUpdateResearchEvidences(payload);
      setSelectedEvidenceIds([]);
      setEvidenceBulkForm(createEmptyEvidenceBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 条 evidence。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Evidence 批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function applyArtifactBulkUpdate() {
    if (!selectedProjectId || !selectedArtifactIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一个 artifact。"),
      });
      return;
    }
    const payload = {
      project_id: selectedProjectId,
      artifact_ids: selectedArtifactIds,
      workflow_id: artifactBulkForm.workflowId || undefined,
      source_type: artifactBulkForm.sourceType || undefined,
    };
    if (payload.workflow_id === undefined && payload.source_type === undefined) {
      setNotice({
        variant: "warning",
        text: t("请先设置至少一个 artifact 批量更新动作。"),
      });
      return;
    }
    setBulkActionKey("artifact");
    setNotice(null);
    try {
      const result: ResearchArtifactBulkUpdateResult =
        await bulkUpdateResearchArtifacts(payload);
      setSelectedArtifactIds([]);
      setArtifactBulkForm(createEmptyArtifactBulkForm());
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(`已批量更新 ${result.updated_count} 个 artifact。`),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Artifact 批量更新失败"),
      });
    } finally {
      setBulkActionKey("");
    }
  }

  async function executeWorkflow(workflowId: string) {
    setExecutingWorkflowId(workflowId);
    try {
      await executeResearchWorkflow(workflowId);
      await refreshResearchViews();
    } finally {
      setExecutingWorkflowId("");
    }
  }

  const refreshResearchViews = useCallback(
    async (workflowId?: string) => {
      const [overviewData] = await Promise.all([
        getResearchOverview(),
        selectedProjectId
          ? Promise.all([
              loadProjectContext(selectedProjectId),
              loadProjectMemoryRows(selectedProjectId),
              loadProjectBlockerRows(selectedProjectId),
              loadClosureActionRows(selectedProjectId),
              loadDatasetVersionRows(selectedProjectId),
              loadExperimentRows(selectedProjectId),
              loadNoteRows(selectedProjectId),
              loadClaimRows(selectedProjectId),
              loadArtifactRows(selectedProjectId),
              loadEvidenceRows(selectedProjectId),
            ])
          : Promise.resolve(),
      ]);
      setOverview(overviewData);
      if (workflowId) {
        const context = await getResearchWorkflowRemediation(workflowId);
        setRemediationContext(context);
      }
    },
    [
      loadArtifactRows,
      loadProjectBlockerRows,
      loadClaimRows,
      loadClosureActionRows,
      loadDatasetVersionRows,
      loadEvidenceRows,
      loadExperimentRows,
      loadNoteRows,
      loadProjectContext,
      loadProjectMemoryRows,
      selectedProjectId,
    ],
  );

  async function openRemediationDetails(workflowId: string, title: string) {
    setRemediationModal({ workflowId, title });
    setRemediationLoading(true);
    try {
      const context = await getResearchWorkflowRemediation(workflowId);
      setRemediationContext(context);
    } finally {
      setRemediationLoading(false);
    }
  }

  async function runBlockerTaskAction(
    workflowId: string,
    taskId: string,
    mode: "dispatch" | "execute",
  ) {
    const actionKey = `${mode}:${taskId}`;
    setTaskActionKey(actionKey);
    setNotice(null);
    try {
      const result =
        mode === "dispatch"
          ? await dispatchResearchWorkflowTask(workflowId, taskId)
          : await executeResearchWorkflowTask(workflowId, taskId);
      await refreshResearchViews(
        remediationModal?.workflowId === workflowId ? workflowId : undefined,
      );
      const summary =
        result.reason ||
        result.task?.last_execution_summary ||
        result.task?.last_dispatch_summary ||
        (mode === "dispatch" ? t("任务已派发。") : t("任务已执行。"));
      setNotice({
        variant: result.skipped ? "warning" : "success",
        text: summary,
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("任务操作失败"),
      });
    } finally {
      setTaskActionKey("");
    }
  }

  async function runRemediationBatchAction(
    workflowId: string,
    mode: "dispatch" | "execute",
  ) {
    const actionKey = `${mode}-remediation:${workflowId}`;
    setTaskActionKey(actionKey);
    setNotice(null);
    try {
      const result =
        mode === "dispatch"
          ? await dispatchResearchWorkflowRemediation(workflowId, 3)
          : await executeResearchWorkflowRemediation(workflowId, 3);
      await refreshResearchViews(workflowId);
      const summary =
        result.reason ||
        (mode === "dispatch"
          ? t(`已派发 ${result.dispatched_count || 0} 个 remediation task。`)
          : t(`已执行 ${result.executed_count || 0} 个 remediation task。`));
      setNotice({
        variant: result.skipped ? "warning" : "success",
        text: summary,
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("批量 remediation 操作失败"),
      });
    } finally {
      setTaskActionKey("");
    }
  }

  async function runProjectBlockerAction(
    projectId: string,
    mode: "dispatch" | "execute" | "resume",
  ) {
    const actionKey = `${mode}:${projectId}`;
    setProjectActionKey(actionKey);
    setNotice(null);
    try {
      const result =
        mode === "dispatch"
          ? await dispatchResearchProjectBlockers(projectId, 3, 2)
          : mode === "execute"
            ? await executeResearchProjectBlockers(projectId, 3, 2)
            : await resumeResearchProjectBlockers(projectId, 3);
      await refreshResearchViews(
        remediationModal?.workflowId && remediationContext
          ? remediationModal.workflowId
          : undefined,
      );
      const summary =
        result.reason ||
        (mode === "dispatch"
          ? t(`已为 project 派发 ${result.dispatched_count || 0} 个 blocker task。`)
          : mode === "execute"
            ? t(`已为 project 执行 ${result.executed_count || 0} 个 blocker task。`)
            : t(`已恢复推进 ${result.resumed_count || 0} 个 workflow。`));
      setNotice({
        variant: result.skipped ? "warning" : "success",
        text: summary,
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Project blocker 操作失败"),
      });
    } finally {
      setProjectActionKey("");
    }
  }

  async function applyProjectBlockersBatch(
    projectId: string,
    mode: "dispatch" | "execute" | "resume",
  ) {
    if (!selectedBlockerWorkflowIds.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一个 blocker workflow。"),
      });
      return;
    }
    const actionKey = `selected-${mode}:${projectId}`;
    setProjectActionKey(actionKey);
    setNotice(null);
    try {
      const result: ResearchProjectBlockerBatchResult =
        await applyResearchProjectBlockers(projectId, {
          workflow_ids: selectedBlockerWorkflowIds,
          mode,
          task_limit: 2,
        });
      setSelectedBlockerWorkflowIds([]);
      await refreshResearchViews(
        remediationModal?.workflowId && remediationContext
          ? remediationModal.workflowId
          : undefined,
      );
      const summary =
        result.reason ||
        (mode === "dispatch"
          ? t(
              `已处理 ${result.requested_count || selectedBlockerWorkflowIds.length} 个 blocker workflow，成功派发 ${result.dispatched_count || 0} 个 remediation task。`,
            )
          : mode === "execute"
            ? t(
                `已处理 ${result.requested_count || selectedBlockerWorkflowIds.length} 个 blocker workflow，成功执行 ${result.executed_count || 0} 个 remediation task。`,
              )
            : t(
                `已处理 ${result.requested_count || selectedBlockerWorkflowIds.length} 个 blocker workflow，恢复推进 ${result.resumed_count || 0} 个 workflow。`,
              ));
      setNotice({
        variant: result.skipped ? "warning" : "success",
        text: summary,
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("Blocker 批量处理失败"),
      });
    } finally {
      setProjectActionKey("");
    }
  }

  async function materializeClosureTasks(projectId: string) {
    setClosureActionKey(`materialize:${projectId}`);
    setNotice(null);
    try {
      const result = await materializeResearchProjectClosure(projectId, {
        limit: 6,
      });
      if (result.closure) {
        setClosure(result.closure);
      }
      await refreshResearchViews();
      setNotice({
        variant: result.created_count > 0 ? "success" : "warning",
        text:
          result.created_count > 0
            ? t(`已生成 ${result.created_count} 个闭环 follow-up task。`)
            : t("当前没有新的闭环 task 需要生成。"),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("闭环任务生成失败"),
      });
    } finally {
      setClosureActionKey("");
    }
  }

  async function executeClosureAction(
    projectId: string,
    action: { kind?: string; target_id?: string },
  ) {
    const actionKey = `execute-closure:${action.kind}:${action.target_id}`;
    setClosureActionKey(actionKey);
    setNotice(null);
    try {
      const result: ResearchClosureActionExecuteResult =
        await executeResearchProjectClosureAction(projectId, {
          action_kind: action.kind || "",
          target_id: action.target_id || "",
        });
      if (result.closure) {
        setClosure(result.closure);
      }
      await refreshResearchViews();
      setNotice({
        variant: result.executed ? "success" : result.materialized ? "info" : "warning",
        text:
          result.reason ||
          (result.executed
            ? t("闭环动作已自动补齐。")
            : t("该动作已转为 follow-up task。")),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("闭环动作执行失败"),
      });
    } finally {
      setClosureActionKey("");
    }
  }

  async function applyClosureActionsBatch(
    projectId: string,
    mode: "execute" | "materialize",
  ) {
    if (!selectedClosureActionKeys.length) {
      setNotice({
        variant: "warning",
        text: t("请先选择至少一个闭环 action。"),
      });
      return;
    }
    const actionKey = `batch-closure:${mode}:${projectId}`;
    setClosureActionKey(actionKey);
    setNotice(null);
    try {
      const result: ResearchClosureActionBatchResult =
        await applyResearchProjectClosureActions(projectId, {
          closure_keys: selectedClosureActionKeys,
          mode,
        });
      if (result.closure) {
        setClosure(result.closure);
      }
      setSelectedClosureActionKeys([]);
      await refreshResearchViews();
      setNotice({
        variant:
          result.executed_count > 0 || result.materialized_count > 0
            ? "success"
            : "warning",
        text:
          mode === "execute"
            ? t(
                `已处理 ${result.requested_count} 个 action，其中自动补齐 ${result.executed_count} 个，生成 follow-up task ${result.materialized_count} 个。`,
              )
            : t(
                `已尝试为 ${result.requested_count} 个 action 生成任务，新建 ${result.materialized_count} 个 follow-up task。`,
              ),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("闭环批量处理失败"),
      });
    } finally {
      setClosureActionKey("");
    }
  }

  async function generateProjectPackage(projectId: string) {
    setClosureActionKey(`package:${projectId}`);
    setNotice(null);
    try {
      const result = await createResearchProjectPackage(projectId);
      setPackageResult(result);
      if (result.closure) {
        setClosure(result.closure);
      }
      await refreshResearchViews();
      setNotice({
        variant: "success",
        text: t(
          `已生成投稿包，包含 ${result.included_file_count} 个文件，缺失 ${result.missing_file_count} 个文件。`,
        ),
      });
    } catch (error: any) {
      setNotice({
        variant: "danger",
        text: error?.message || t("投稿包生成失败"),
      });
    } finally {
      setClosureActionKey("");
    }
  }

  return (
    <div className="panel">
      <PageHeader
        eyebrow="Research OS"
        title={t("研究项目")}
        description={t(
          "按课题查看 workflow、claim、evidence、notes 和主动提醒。",
        )}
        actions={
          <button className="btn-ghost" onClick={() => void loadAll()}>
            <RefreshCw size={15} />
            {t("刷新")}
          </button>
        }
      />

      {loading && <Loading text={t("加载中...")} />}
      {notice && <NoticeBanner variant={notice.variant}>{notice.text}</NoticeBanner>}

      <div className="card-grid">
        <StatCard
          label={t("研究项目")}
          value={overview?.counts.projects ?? 0}
          icon={<FolderOpen size={18} />}
        />
        <StatCard
          label={t("活跃工作流")}
          value={overview?.counts.active_workflows ?? 0}
          icon={<Workflow size={18} />}
          variant="info"
        />
        <StatCard
          label={t("结构化笔记")}
          value={overview?.counts.notes ?? 0}
          icon={<FileText size={18} />}
          variant="success"
        />
        <StatCard
          label={t("证据项")}
          value={overview?.counts.evidences ?? 0}
          icon={<Activity size={18} />}
          variant="warning"
        />
      </div>

      <div className="card-grid">
        <SurfaceCard
          title={t("项目列表")}
          description={t("选择一个项目，下钻查看 workflow、claim 与提醒。")}
        >
          {projects.length === 0 ? (
            <EmptyState
              icon={<FolderOpen size={28} />}
              title={t("暂无研究项目")}
              description={t("先通过 API 创建 project，再在这里查看闭环进展。")}
            />
          ) : (
            projects.map((project) => (
              <DataRow
                key={project.id}
                title={project.name}
                meta={project.description || project.id}
                badge={
                  <Badge variant={statusVariant(project.status || "active")}>
                    {project.status || "active"}
                  </Badge>
                }
                actions={
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => setSelectedProjectId(project.id)}
                  >
                    {selectedProjectId === project.id ? t("查看") : t("加载")}
                  </button>
                }
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("项目概览")}
          description={
            dashboard
              ? `${dashboard.project.name} · ${dashboard.project.status || "active"}`
              : t("选择项目后显示聚合统计与近期活动。")
          }
        >
          {dashboard ? (
            <div className="page-header-meta-row">
              {Object.entries(dashboard.counts).map(([key, value]) => (
                <div key={key} className="metric-pill">
                  <span>{key}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Activity size={28} />}
              title={t("等待项目上下文")}
              description={t("选中一个 project 后，这里会显示聚合指标。")}
            />
          )}
        </SurfaceCard>
      </div>

      <div className="card-grid">
        <SurfaceCard
          title={editingMemoryId ? t("编辑项目记忆") : t("记录项目记忆")}
          description={
            editingMemoryId
              ? t("直接修订已有 memory，让项目状态保持最新。")
              : t("把 decision、fact 和 open question 直接沉淀进项目状态，而不是只留在聊天里。")
          }
          actions={
            editingMemoryId ? (
              <button className="btn-ghost btn-sm" onClick={resetMemoryEditor}>
                {t("取消编辑")}
              </button>
            ) : undefined
          }
        >
          <div className="form-stack">
            <input
              value={memoryForm.title}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  title: e.target.value,
                }))
              }
              placeholder={t("记忆标题")}
            />
            <textarea
              rows={4}
              value={memoryForm.content}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  content: e.target.value,
                }))
              }
              placeholder={t("记录关键结论、决策原因或开放问题")}
            />
            <select
              value={memoryForm.entryKind}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  entryKind: e.target.value,
                }))
              }
            >
              <option value="fact">fact</option>
              <option value="decision">decision</option>
              <option value="open_question">open_question</option>
              <option value="term_definition">term_definition</option>
              <option value="failure">failure</option>
              <option value="preference">preference</option>
            </select>
            <select
              value={memoryForm.status}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  status: e.target.value,
                }))
              }
            >
              <option value="active">active</option>
              <option value="resolved">resolved</option>
              <option value="archived">archived</option>
            </select>
            <select
              value={memoryForm.workflowId}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("不绑定 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <input
              value={memoryForm.stage}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  stage: e.target.value,
                }))
              }
              placeholder={t("阶段，例如 experiment_plan")}
            />
            <input
              value={memoryForm.tags}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  tags: e.target.value,
                }))
              }
              placeholder={t("标签，逗号分隔")}
            />
            <textarea
              rows={3}
              value={memoryForm.metadataText}
              onChange={(e) =>
                setMemoryForm((current) => ({
                  ...current,
                  metadataText: e.target.value,
                }))
              }
              placeholder='{"source":"console"}'
            />
            {memoryFormError ? (
              <p className="text-sm" style={{ color: "var(--danger)" }}>
                {memoryFormError}
              </p>
            ) : null}
            <button
              disabled={!selectedProjectId || creationActionKey === "memory"}
              onClick={() => void submitProjectMemory()}
            >
              {creationActionKey === "memory"
                ? t("保存中...")
                : editingMemoryId
                  ? t("更新项目记忆")
                  : t("创建项目记忆")}
            </button>
          </div>
        </SurfaceCard>

        <SurfaceCard
          title={editingDatasetVersionId ? t("编辑数据版本") : t("注册数据版本")}
          description={
            editingDatasetVersionId
              ? t("修订 split、source path 和 metadata，让 dataset state 与真实资产保持一致。")
              : t("先登记 dataset version，再让 experiment plan 与 provenance 真正绑定到数据资产。")
          }
          actions={
            editingDatasetVersionId ? (
              <button className="btn-ghost btn-sm" onClick={resetDatasetEditor}>
                {t("取消编辑")}
              </button>
            ) : undefined
          }
        >
          <div className="form-stack">
            <input
              value={datasetForm.name}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  name: e.target.value,
                }))
              }
              placeholder={t("数据集名称")}
            />
            <input
              value={datasetForm.versionLabel}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  versionLabel: e.target.value,
                }))
              }
              placeholder="v1"
            />
            <input
              value={datasetForm.description}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  description: e.target.value,
                }))
              }
              placeholder={t("版本描述")}
            />
            <select
              value={datasetForm.workflowId}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("不绑定 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <select
              value={datasetForm.parentVersionId}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  parentVersionId: e.target.value,
                }))
              }
            >
              <option value="">{t("无 parent version")}</option>
              {datasetVersions
                .filter((dataset) => dataset.id !== editingDatasetVersionId)
                .map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name} · {dataset.version_label}
                  </option>
                ))}
            </select>
            <input
              value={datasetForm.path}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  path: e.target.value,
                }))
              }
              placeholder={t("数据资产路径，可选")}
            />
            <textarea
              rows={3}
              value={datasetForm.sourcePaths}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  sourcePaths: e.target.value,
                }))
              }
              placeholder={t("每行一个 source path")}
            />
            <textarea
              rows={4}
              value={datasetForm.splitSpecText}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  splitSpecText: e.target.value,
                }))
              }
              placeholder='{"train":"train.jsonl","validation":"dev.jsonl"}'
            />
            <textarea
              rows={4}
              value={datasetForm.transformStepsText}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  transformStepsText: e.target.value,
                }))
              }
              placeholder='[{"name":"dedupe"},{"name":"normalize"}]'
            />
            <input
              value={datasetForm.primaryMetric}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  primaryMetric: e.target.value,
                }))
              }
              placeholder={t("primary metric，例如 accuracy")}
            />
            <textarea
              rows={3}
              value={datasetForm.metadataText}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  metadataText: e.target.value,
                }))
              }
              placeholder='{"license":"user-owned"}'
            />
            <input
              value={datasetForm.tags}
              onChange={(e) =>
                setDatasetForm((current) => ({
                  ...current,
                  tags: e.target.value,
                }))
              }
              placeholder={t("标签，逗号分隔")}
            />
            {datasetFormError ? (
              <p className="text-sm" style={{ color: "var(--danger)" }}>
                {datasetFormError}
              </p>
            ) : null}
            <button
              disabled={!selectedProjectId || creationActionKey === "dataset"}
              onClick={() => void submitDatasetVersion()}
            >
              {creationActionKey === "dataset"
                ? t("保存中...")
                : editingDatasetVersionId
                  ? t("更新数据版本")
                  : t("创建数据版本")}
            </button>
          </div>
        </SurfaceCard>
      </div>

      <div className="card-grid">
        <SurfaceCard
          title={t("项目记忆")}
          description={t("展示项目级 fact / decision / open question，避免上下文只活在聊天里。")}
          actions={
            <>
              <button className="btn-ghost btn-sm" onClick={() => void applyMemoryFilters()}>
                {t("应用筛选")}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => void clearMemoryFilters()}>
                {t("清空筛选")}
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() =>
                  setSelectedMemoryIds((current) =>
                    toggleVisibleSelection(
                      current,
                      projectMemory.map((item) => item.id),
                    ),
                  )
                }
              >
                {t("全选当前")}
              </button>
              {selectedMemoryIds.length ? (
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => setSelectedMemoryIds([])}
                >
                  {t("清空选择")}
                </button>
              ) : null}
            </>
          }
        >
          <div className="form-stack">
            <select
              value={memoryFilters.workflowId}
              onChange={(e) =>
                setMemoryFilters((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <select
              value={memoryFilters.entryKind}
              onChange={(e) =>
                setMemoryFilters((current) => ({
                  ...current,
                  entryKind: e.target.value,
                }))
              }
            >
              <option value="">{t("全部类型")}</option>
              <option value="fact">fact</option>
              <option value="decision">decision</option>
              <option value="open_question">open_question</option>
              <option value="term_definition">term_definition</option>
              <option value="failure">failure</option>
              <option value="preference">preference</option>
            </select>
            <select
              value={memoryFilters.status}
              onChange={(e) =>
                setMemoryFilters((current) => ({
                  ...current,
                  status: e.target.value,
                }))
              }
            >
              <option value="">{t("全部状态")}</option>
              <option value="active">active</option>
              <option value="resolved">resolved</option>
              <option value="archived">archived</option>
            </select>
            <input
              value={memoryFilters.stage}
              onChange={(e) =>
                setMemoryFilters((current) => ({
                  ...current,
                  stage: e.target.value,
                }))
              }
              placeholder={t("按 stage 筛选")}
            />
            <input
              value={memoryFilters.tag}
              onChange={(e) =>
                setMemoryFilters((current) => ({
                  ...current,
                  tag: e.target.value,
                }))
              }
              placeholder={t("按标签筛选")}
            />
            <input
              value={memoryFilters.query}
              onChange={(e) =>
                setMemoryFilters((current) => ({
                  ...current,
                  query: e.target.value,
                }))
              }
              placeholder={t("搜索标题或内容")}
            />
          </div>
          {selectedMemoryIds.length ? (
            <div className="form-stack" style={{ marginTop: 12 }}>
              <p className="muted text-sm">
                {t(`已选择 ${selectedMemoryIds.length} 条项目记忆`)}
              </p>
              <select
                value={memoryBulkForm.status}
                onChange={(e) =>
                  setMemoryBulkForm((current) => ({
                    ...current,
                    status: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持状态不变")}</option>
                <option value="active">active</option>
                <option value="resolved">resolved</option>
                <option value="archived">archived</option>
              </select>
              <select
                value={memoryBulkForm.entryKind}
                onChange={(e) =>
                  setMemoryBulkForm((current) => ({
                    ...current,
                    entryKind: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持类型不变")}</option>
                <option value="fact">fact</option>
                <option value="decision">decision</option>
                <option value="open_question">open_question</option>
                <option value="term_definition">term_definition</option>
                <option value="failure">failure</option>
                <option value="preference">preference</option>
              </select>
              <select
                value={memoryBulkForm.workflowId}
                onChange={(e) =>
                  setMemoryBulkForm((current) => ({
                    ...current,
                    workflowId: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 workflow 不变")}</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.title}
                  </option>
                ))}
              </select>
              <input
                value={memoryBulkForm.stage}
                onChange={(e) =>
                  setMemoryBulkForm((current) => ({
                    ...current,
                    stage: e.target.value,
                  }))
                }
                placeholder={t("批量设置 stage")}
              />
              <input
                value={memoryBulkForm.addTags}
                onChange={(e) =>
                  setMemoryBulkForm((current) => ({
                    ...current,
                    addTags: e.target.value,
                  }))
                }
                placeholder={t("批量新增标签，逗号分隔")}
              />
              <input
                value={memoryBulkForm.removeTags}
                onChange={(e) =>
                  setMemoryBulkForm((current) => ({
                    ...current,
                    removeTags: e.target.value,
                  }))
                }
                placeholder={t("批量移除标签，逗号分隔")}
              />
              <button
                disabled={bulkActionKey === "memory"}
                onClick={() => void applyMemoryBulkUpdate()}
              >
                {bulkActionKey === "memory" ? t("批量更新中...") : t("批量更新记忆")}
              </button>
            </div>
          ) : null}
          {projectMemory.length === 0 ? (
            <EmptyState
              icon={<FileText size={28} />}
              title={t("暂无项目记忆")}
              description={t("decision log、阶段结论和开放问题会在这里沉淀。")}
            />
          ) : (
            projectMemory.slice(0, 8).map((entry) => (
              <DataRow
                key={entry.id}
                title={entry.title}
                meta={`${entry.entry_kind}${entry.stage ? ` · ${entry.stage}` : ""} · notes=${entry.note_ids?.length || 0} · claims=${entry.claim_ids?.length || 0}`}
                badge={
                  <Badge variant={statusVariant(entry.status || entry.entry_kind)}>
                    {entry.status || entry.entry_kind}
                  </Badge>
                }
                actions={
                  <>
                    <label className="btn-ghost btn-sm">
                      <input
                        type="checkbox"
                        checked={selectedMemoryIds.includes(entry.id)}
                        onChange={(e) =>
                          setSelectedMemoryIds((current) =>
                            e.target.checked
                              ? mergeSelections(current, [entry.id])
                              : current.filter((id) => id !== entry.id),
                          )
                        }
                      />
                    </label>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => startMemoryEdit(entry)}
                    >
                      {t("编辑")}
                    </button>
                  </>
                }
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("数据版本")}
          description={t("追踪 dataset version、split spec 与数据资产入口，支撑后续 experiment plan。")}
          actions={
            <>
              <button className="btn-ghost btn-sm" onClick={() => void applyDatasetFilters()}>
                {t("应用筛选")}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => void clearDatasetFilters()}>
                {t("清空筛选")}
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() =>
                  setSelectedDatasetIds((current) =>
                    toggleVisibleSelection(
                      current,
                      datasetVersions.map((item) => item.id),
                    ),
                  )
                }
              >
                {t("全选当前")}
              </button>
              {selectedDatasetIds.length ? (
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => setSelectedDatasetIds([])}
                >
                  {t("清空选择")}
                </button>
              ) : null}
            </>
          }
        >
          <div className="form-stack">
            <select
              value={datasetFilters.workflowId}
              onChange={(e) =>
                setDatasetFilters((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <select
              value={datasetFilters.parentVersionId}
              onChange={(e) =>
                setDatasetFilters((current) => ({
                  ...current,
                  parentVersionId: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 parent")}</option>
              {datasetVersions.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name} · {dataset.version_label}
                </option>
              ))}
            </select>
            <input
              value={datasetFilters.tag}
              onChange={(e) =>
                setDatasetFilters((current) => ({
                  ...current,
                  tag: e.target.value,
                }))
              }
              placeholder={t("按标签筛选")}
            />
            <input
              value={datasetFilters.nameQuery}
              onChange={(e) =>
                setDatasetFilters((current) => ({
                  ...current,
                  nameQuery: e.target.value,
                }))
              }
              placeholder={t("搜索名称或描述")}
            />
          </div>
          {selectedDatasetIds.length ? (
            <div className="form-stack" style={{ marginTop: 12 }}>
              <p className="muted text-sm">
                {t(`已选择 ${selectedDatasetIds.length} 个数据版本`)}
              </p>
              <select
                value={datasetBulkForm.workflowId}
                onChange={(e) =>
                  setDatasetBulkForm((current) => ({
                    ...current,
                    workflowId: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 workflow 不变")}</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.title}
                  </option>
                ))}
              </select>
              <input
                value={datasetBulkForm.addTags}
                onChange={(e) =>
                  setDatasetBulkForm((current) => ({
                    ...current,
                    addTags: e.target.value,
                  }))
                }
                placeholder={t("批量新增标签，逗号分隔")}
              />
              <input
                value={datasetBulkForm.removeTags}
                onChange={(e) =>
                  setDatasetBulkForm((current) => ({
                    ...current,
                    removeTags: e.target.value,
                  }))
                }
                placeholder={t("批量移除标签，逗号分隔")}
              />
              <button
                disabled={bulkActionKey === "dataset"}
                onClick={() => void applyDatasetBulkUpdate()}
              >
                {bulkActionKey === "dataset" ? t("批量更新中...") : t("批量更新数据版本")}
              </button>
            </div>
          ) : null}
          {datasetVersions.length === 0 ? (
            <EmptyState
              icon={<Database size={28} />}
              title={t("暂无 dataset version")}
              description={t("实验计划现在要求先注册 dataset version。")}
            />
          ) : (
            datasetVersions.slice(0, 8).map((dataset) => (
              <DataRow
                key={dataset.id}
                title={`${dataset.name} · ${dataset.version_label}`}
                meta={`${summarizeSplitSpec(dataset.split_spec)} · files=${dataset.source_paths?.length || 0} · hashes=${Object.keys(dataset.file_hashes || {}).length} · transforms=${dataset.transform_steps?.length || 0}${dataset.parent_version_id ? ` · parent=${datasetVersionLabel(dataset.parent_version_id)}` : ""}`}
                badge={<Badge variant="info">{dataset.version_label}</Badge>}
                actions={
                  <>
                    <label className="btn-ghost btn-sm">
                      <input
                        type="checkbox"
                        checked={selectedDatasetIds.includes(dataset.id)}
                        onChange={(e) =>
                          setSelectedDatasetIds((current) =>
                            e.target.checked
                              ? mergeSelections(current, [dataset.id])
                              : current.filter((id) => id !== dataset.id),
                          )
                        }
                      />
                    </label>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => startDatasetEdit(dataset)}
                    >
                      {t("编辑")}
                    </button>
                    {dataset.artifact_id ? (
                      <button
                        className="btn-ghost btn-sm"
                        onClick={() =>
                          void openArtifactLineage(
                            dataset.artifact_id || "",
                            `${dataset.name} ${dataset.version_label}`,
                          )
                        }
                      >
                        {t("查看血缘")}
                      </button>
                    ) : null}
                  </>
                }
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("实验 Provenance")}
          description={t("按状态、执行模式和 replayability 管理实验，并保留 replay 入口。")}
          actions={
            <>
              <button className="btn-ghost btn-sm" onClick={() => void applyExperimentFilters()}>
                {t("应用筛选")}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => void clearExperimentFilters()}>
                {t("清空筛选")}
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() =>
                  setSelectedExperimentIds((current) =>
                    toggleVisibleSelection(
                      current,
                      experimentRows.map((item) => item.id),
                    ),
                  )
                }
              >
                {t("全选当前")}
              </button>
              {selectedExperimentIds.length ? (
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => setSelectedExperimentIds([])}
                >
                  {t("清空选择")}
                </button>
              ) : null}
            </>
          }
        >
          <div className="form-stack">
            <select
              value={experimentFilters.workflowId}
              onChange={(e) =>
                setExperimentFilters((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <select
              value={experimentFilters.status}
              onChange={(e) =>
                setExperimentFilters((current) => ({
                  ...current,
                  status: e.target.value,
                }))
              }
            >
              <option value="">{t("全部状态")}</option>
              <option value="planned">planned</option>
              <option value="running">running</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
              <option value="cancelled">cancelled</option>
            </select>
            <select
              value={experimentFilters.executionMode}
              onChange={(e) =>
                setExperimentFilters((current) => ({
                  ...current,
                  executionMode: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 execution mode")}</option>
              <option value="inline">inline</option>
              <option value="command">command</option>
              <option value="notebook">notebook</option>
              <option value="external">external</option>
              <option value="file_watch">file_watch</option>
            </select>
            <select
              value={experimentFilters.replayable}
              onChange={(e) =>
                setExperimentFilters((current) => ({
                  ...current,
                  replayable: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 replay 状态")}</option>
              <option value="true">{t("可 replay")}</option>
              <option value="false">{t("不可 replay")}</option>
            </select>
            <input
              value={experimentFilters.query}
              onChange={(e) =>
                setExperimentFilters((current) => ({
                  ...current,
                  query: e.target.value,
                }))
              }
              placeholder={t("搜索名称、notes、comparison group 或 bundle schema")}
            />
          </div>
          {selectedExperimentIds.length ? (
            <div className="form-stack" style={{ marginTop: 12 }}>
              <p className="muted text-sm">
                {t(`已选择 ${selectedExperimentIds.length} 个实验`)}
              </p>
              <select
                value={experimentBulkForm.workflowId}
                onChange={(e) =>
                  setExperimentBulkForm((current) => ({
                    ...current,
                    workflowId: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 workflow 不变")}</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.title}
                  </option>
                ))}
              </select>
              <select
                value={experimentBulkForm.status}
                onChange={(e) =>
                  setExperimentBulkForm((current) => ({
                    ...current,
                    status: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持状态不变")}</option>
                <option value="planned">planned</option>
                <option value="running">running</option>
                <option value="completed">completed</option>
                <option value="failed">failed</option>
                <option value="cancelled">cancelled</option>
              </select>
              <input
                value={experimentBulkForm.comparisonGroup}
                onChange={(e) =>
                  setExperimentBulkForm((current) => ({
                    ...current,
                    comparisonGroup: e.target.value,
                  }))
                }
                placeholder={t("批量设置 comparison group")}
              />
              <button
                disabled={bulkActionKey === "experiment"}
                onClick={() => void applyExperimentBulkUpdate()}
              >
                {bulkActionKey === "experiment"
                  ? t("批量更新中...")
                  : t("批量更新 experiment")}
              </button>
            </div>
          ) : null}
          {experimentRows.length === 0 ? (
            <EmptyState
              icon={<Activity size={28} />}
              title={t("暂无实验记录")}
              description={t("当前项目还没有结构化实验，或当前筛选条件下没有结果。")}
            />
          ) : (
            experimentRows.slice(0, 8).map((experiment) => {
              const contractStatus = String(
                (experiment.metadata?.["contract_validation"] as Record<string, unknown> | undefined)?.["status"]
                  || (experiment.metadata?.["result_bundle_validation"] as Record<string, unknown> | undefined)?.["status"]
                  || "",
              );
              return (
                <DataRow
                  key={experiment.id}
                  title={experiment.name}
                  meta={`${experiment.execution?.mode || "inline"} · datasets=${experiment.dataset_version_ids?.length || 0} · metrics=${Object.keys(experiment.metrics || {}).length}${experiment.comparison_group ? ` · group=${experiment.comparison_group}` : ""}${experiment.execution?.result_bundle_schema ? ` · bundle=${experiment.execution.result_bundle_schema}` : ""}${contractStatus ? ` · contract=${contractStatus}` : ""}`}
                  badge={
                    <Badge variant={statusVariant(experiment.status)}>
                      {experiment.provenance?.replayable
                        ? `${experiment.status} · replayable`
                        : experiment.status}
                    </Badge>
                  }
                  actions={
                    <>
                      <label className="btn-ghost btn-sm">
                        <input
                          type="checkbox"
                          checked={selectedExperimentIds.includes(experiment.id)}
                          onChange={(e) =>
                            setSelectedExperimentIds((current) =>
                              e.target.checked
                                ? mergeSelections(current, [experiment.id])
                                : current.filter((id) => id !== experiment.id),
                            )
                          }
                        />
                      </label>
                      {experiment.provenance?.replayable ? (
                        <button
                          className="btn-ghost btn-sm"
                          onClick={() =>
                            void openExperimentReplay(experiment.id, experiment.name)
                          }
                        >
                          {t("重放计划")}
                        </button>
                      ) : null}
                    </>
                  }
                />
              );
            })
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("结构化 Notes")}
          description={t("筛选 paper / experiment / writing / decision notes，并批量整理 workflow 与标签。")}
          actions={
            <>
              <button className="btn-ghost btn-sm" onClick={() => void applyNoteFilters()}>
                {t("应用筛选")}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => void clearNoteFilters()}>
                {t("清空筛选")}
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() =>
                  setSelectedNoteIds((current) =>
                    toggleVisibleSelection(
                      current,
                      noteRows.map((item) => item.id),
                    ),
                  )
                }
              >
                {t("全选当前")}
              </button>
              {selectedNoteIds.length ? (
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => setSelectedNoteIds([])}
                >
                  {t("清空选择")}
                </button>
              ) : null}
            </>
          }
        >
          <div className="form-stack">
            <select
              value={noteFilters.workflowId}
              onChange={(e) =>
                setNoteFilters((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <select
              value={noteFilters.noteType}
              onChange={(e) =>
                setNoteFilters((current) => ({
                  ...current,
                  noteType: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 note type")}</option>
              <option value="paper_note">paper_note</option>
              <option value="idea_note">idea_note</option>
              <option value="experiment_note">experiment_note</option>
              <option value="writing_note">writing_note</option>
              <option value="decision_log">decision_log</option>
            </select>
            <input
              value={noteFilters.tag}
              onChange={(e) =>
                setNoteFilters((current) => ({
                  ...current,
                  tag: e.target.value,
                }))
              }
              placeholder={t("按标签筛选")}
            />
            <input
              value={noteFilters.query}
              onChange={(e) =>
                setNoteFilters((current) => ({
                  ...current,
                  query: e.target.value,
                }))
              }
              placeholder={t("搜索标题、内容或 paper refs")}
            />
          </div>
          {selectedNoteIds.length ? (
            <div className="form-stack" style={{ marginTop: 12 }}>
              <p className="muted text-sm">
                {t(`已选择 ${selectedNoteIds.length} 条 note`)}
              </p>
              <select
                value={noteBulkForm.workflowId}
                onChange={(e) =>
                  setNoteBulkForm((current) => ({
                    ...current,
                    workflowId: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 workflow 不变")}</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.title}
                  </option>
                ))}
              </select>
              <select
                value={noteBulkForm.noteType}
                onChange={(e) =>
                  setNoteBulkForm((current) => ({
                    ...current,
                    noteType: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 note type 不变")}</option>
                <option value="paper_note">paper_note</option>
                <option value="idea_note">idea_note</option>
                <option value="experiment_note">experiment_note</option>
                <option value="writing_note">writing_note</option>
                <option value="decision_log">decision_log</option>
              </select>
              <input
                value={noteBulkForm.addTags}
                onChange={(e) =>
                  setNoteBulkForm((current) => ({
                    ...current,
                    addTags: e.target.value,
                  }))
                }
                placeholder={t("批量新增标签，逗号分隔")}
              />
              <input
                value={noteBulkForm.removeTags}
                onChange={(e) =>
                  setNoteBulkForm((current) => ({
                    ...current,
                    removeTags: e.target.value,
                  }))
                }
                placeholder={t("批量移除标签，逗号分隔")}
              />
              <button
                disabled={bulkActionKey === "note"}
                onClick={() => void applyNoteBulkUpdate()}
              >
                {bulkActionKey === "note" ? t("批量更新中...") : t("批量更新 note")}
              </button>
            </div>
          ) : null}
          {noteRows.length === 0 ? (
            <EmptyState
              icon={<FileText size={28} />}
              title={t("暂无 note")}
              description={t("当前项目还没有结构化 note，或当前筛选条件下没有结果。")}
            />
          ) : (
            noteRows.slice(0, 8).map((note) => (
              <DataRow
                key={note.id}
                title={note.title}
                meta={`${note.note_type} · tags=${note.tags?.length || 0} · claims=${note.claim_ids?.length || 0} · artifacts=${note.artifact_ids?.length || 0}${note.paper_refs?.length ? ` · refs=${note.paper_refs.length}` : ""}`}
                badge={<Badge variant="info">{note.note_type}</Badge>}
                actions={
                  <label className="btn-ghost btn-sm">
                    <input
                      type="checkbox"
                      checked={selectedNoteIds.includes(note.id)}
                      onChange={(e) =>
                        setSelectedNoteIds((current) =>
                          e.target.checked
                            ? mergeSelections(current, [note.id])
                            : current.filter((id) => id !== note.id),
                        )
                      }
                    />
                  </label>
                }
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("Evidence 目录")}
          description={t("筛选 evidence 类型、来源和摘要文本，批量维护 workflow 与 evidence/source 类型。")}
          actions={
            <>
              <button className="btn-ghost btn-sm" onClick={() => void applyEvidenceFilters()}>
                {t("应用筛选")}
              </button>
              <button className="btn-ghost btn-sm" onClick={() => void clearEvidenceFilters()}>
                {t("清空筛选")}
              </button>
              <button
                className="btn-ghost btn-sm"
                onClick={() =>
                  setSelectedEvidenceIds((current) =>
                    toggleVisibleSelection(
                      current,
                      evidenceRows.map((item) => item.id),
                    ),
                  )
                }
              >
                {t("全选当前")}
              </button>
              {selectedEvidenceIds.length ? (
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => setSelectedEvidenceIds([])}
                >
                  {t("清空选择")}
                </button>
              ) : null}
            </>
          }
        >
          <div className="form-stack">
            <select
              value={evidenceFilters.workflowId}
              onChange={(e) =>
                setEvidenceFilters((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 workflow")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <select
              value={evidenceFilters.evidenceType}
              onChange={(e) =>
                setEvidenceFilters((current) => ({
                  ...current,
                  evidenceType: e.target.value,
                }))
              }
            >
              <option value="">{t("全部 evidence type")}</option>
              <option value="paper">paper</option>
              <option value="note">note</option>
              <option value="artifact">artifact</option>
              <option value="experiment_result">experiment_result</option>
              <option value="generated_table">generated_table</option>
              <option value="generated_figure">generated_figure</option>
              <option value="dataset">dataset</option>
              <option value="code_snapshot">code_snapshot</option>
              <option value="config_snapshot">config_snapshot</option>
            </select>
            <input
              value={evidenceFilters.sourceType}
              onChange={(e) =>
                setEvidenceFilters((current) => ({
                  ...current,
                  sourceType: e.target.value,
                }))
              }
              placeholder={t("按 source_type 筛选")}
            />
            <input
              value={evidenceFilters.query}
              onChange={(e) =>
                setEvidenceFilters((current) => ({
                  ...current,
                  query: e.target.value,
                }))
              }
              placeholder={t("搜索 evidence 摘要或来源")}
            />
          </div>
          {selectedEvidenceIds.length ? (
            <div className="form-stack" style={{ marginTop: 12 }}>
              <p className="muted text-sm">
                {t(`已选择 ${selectedEvidenceIds.length} 条 evidence`)}
              </p>
              <select
                value={evidenceBulkForm.workflowId}
                onChange={(e) =>
                  setEvidenceBulkForm((current) => ({
                    ...current,
                    workflowId: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 workflow 不变")}</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.title}
                  </option>
                ))}
              </select>
              <select
                value={evidenceBulkForm.evidenceType}
                onChange={(e) =>
                  setEvidenceBulkForm((current) => ({
                    ...current,
                    evidenceType: e.target.value,
                  }))
                }
              >
                <option value="">{t("保持 evidence type 不变")}</option>
                <option value="paper">paper</option>
                <option value="note">note</option>
                <option value="artifact">artifact</option>
                <option value="experiment_result">experiment_result</option>
                <option value="generated_table">generated_table</option>
                <option value="generated_figure">generated_figure</option>
                <option value="dataset">dataset</option>
                <option value="code_snapshot">code_snapshot</option>
                <option value="config_snapshot">config_snapshot</option>
              </select>
              <input
                value={evidenceBulkForm.sourceType}
                onChange={(e) =>
                  setEvidenceBulkForm((current) => ({
                    ...current,
                    sourceType: e.target.value,
                  }))
                }
                placeholder={t("批量设置 source_type")}
              />
              <button
                disabled={bulkActionKey === "evidence"}
                onClick={() => void applyEvidenceBulkUpdate()}
              >
                {bulkActionKey === "evidence"
                  ? t("批量更新中...")
                  : t("批量更新 evidence")}
              </button>
            </div>
          ) : null}
          {evidenceRows.length === 0 ? (
            <EmptyState
              icon={<Activity size={28} />}
              title={t("暂无 evidence")}
              description={t("当前项目还没有结构化 evidence，或当前筛选条件下没有结果。")}
            />
          ) : (
            evidenceRows.slice(0, 8).map((evidence) => (
              <DataRow
                key={evidence.id}
                title={evidence.summary}
                meta={`${evidence.evidence_type} · ${evidence.source?.title || evidence.source?.source_id || t("无来源标题")} · claims=${evidence.claim_ids?.length || 0}${evidence.source?.locator ? ` · ${evidence.source.locator}` : ""}`}
                badge={<Badge variant="info">{evidence.evidence_type}</Badge>}
                actions={
                  <label className="btn-ghost btn-sm">
                    <input
                      type="checkbox"
                      checked={selectedEvidenceIds.includes(evidence.id)}
                      onChange={(e) =>
                        setSelectedEvidenceIds((current) =>
                          e.target.checked
                            ? mergeSelections(current, [evidence.id])
                            : current.filter((id) => id !== evidence.id),
                        )
                      }
                    />
                  </label>
                }
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("审计时间线")}
          description={t("所有 project / workflow / claim / experiment 变更都会留下 audit trail。")}
        >
          {auditEvents.length === 0 ? (
            <EmptyState
              icon={<RotateCcw size={28} />}
              title={t("暂无审计事件")}
              description={t("状态变更、checkpoint restore、provenance capture 会记录在这里。")}
            />
          ) : (
            auditEvents.slice(0, 8).map((event) => (
              <DataRow
                key={event.id}
                title={`${event.entity_type} · ${event.action}`}
                meta={`${event.summary} · ${formatTimestamp(event.created_at)}`}
                badge={<Badge variant="neutral">{event.entity_type}</Badge>}
              />
            ))
          )}
        </SurfaceCard>
      </div>

      <div className="card-grid">
        <SurfaceCard
          title={t("工作流")}
          description={t("聚焦当前 stage、状态以及是否已经进入阻塞或写作阶段。")}
        >
          {workflows.length === 0 ? (
            <EmptyState
              icon={<Workflow size={28} />}
              title={t("暂无工作流")}
              description={t("当前项目还没有 workflow。")}
            />
          ) : (
            workflows.slice(0, 8).map((workflow) => (
              <DataRow
                key={workflow.id}
                title={workflow.title}
                meta={`${workflow.current_stage} · ${workflow.bindings?.last_summary || workflow.goal || workflow.id}`}
                badge={
                  <Badge variant={statusVariant(workflow.status)}>
                    {workflow.status}
                  </Badge>
                }
                actions={
                  <>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() =>
                        void openWorkflowCheckpoints(
                          workflow.id,
                          workflow.title,
                        )
                      }
                    >
                      {t("检查点")}
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      disabled={executingWorkflowId === workflow.id}
                      onClick={() => void executeWorkflow(workflow.id)}
                    >
                      {executingWorkflowId === workflow.id ? t("执行中...") : t("推进")}
                    </button>
                  </>
                }
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("执行健康度")}
          description={t("汇总 project 下 experiment contract、bundle 校验和 remediation 压力。")}
        >
          {dashboard ? (
            <div className="form-stack">
              {Object.entries(dashboard.health).map(([section, values]) => (
                <div key={section}>
                  <h4>{section}</h4>
                  <div className="page-header-meta-row">
                    {Object.entries(values).map(([key, value]) => (
                      <div key={`${section}-${key}`} className="metric-pill">
                        <span>{key}</span>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Activity size={28} />}
              title={t("等待健康度统计")}
              description={t("选中一个 project 后，这里会显示 execution health。")}
            />
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("研究闭环")}
          description={t("检查 claim 覆盖、实验可复现性、分析产物和投稿准备度。")}
          actions={
            selectedProjectId && closure ? (
              <>
                <button
                  className="btn-ghost btn-sm"
                  disabled={closureActionKey === `materialize:${selectedProjectId}`}
                  onClick={() => void materializeClosureTasks(selectedProjectId)}
                >
                  {closureActionKey === `materialize:${selectedProjectId}`
                    ? t("生成中...")
                    : t("生成闭环任务")}
                </button>
                <button
                  className="btn-ghost btn-sm"
                  disabled={closureActionKey === `package:${selectedProjectId}`}
                  onClick={() => void generateProjectPackage(selectedProjectId)}
                >
                  {closureActionKey === `package:${selectedProjectId}`
                    ? t("打包中...")
                    : t("生成投稿包")}
                </button>
              </>
            ) : undefined
          }
        >
          {closure ? (
            <div className="form-stack">
              <div className="page-header-meta-row">
                <div className="metric-pill">
                  <span>{t("completion_score")}</span>
                  <strong>{closure.readiness.completion_score}%</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("blocking_issues")}</span>
                  <strong>{closure.readiness.blocking_issue_count}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("warnings")}</span>
                  <strong>{closure.readiness.warning_issue_count}</strong>
                </div>
              </div>
              <div className="page-header-meta-row">
                <Badge variant={statusVariant(closure.readiness.overall_status)}>
                  {closure.readiness.overall_status}
                </Badge>
                <Badge
                  variant={
                    closure.readiness.ready_for_writing ? "success" : "warning"
                  }
                >
                  {closure.readiness.ready_for_writing
                    ? t("writing_ready")
                    : t("writing_pending")}
                </Badge>
                <Badge
                  variant={
                    closure.readiness.ready_for_submission
                      ? "success"
                      : "warning"
                  }
                >
                  {closure.readiness.ready_for_submission
                    ? t("submission_ready")
                    : t("submission_pending")}
                </Badge>
                <Badge
                  variant={
                    closure.readiness.ready_for_reproducibility
                      ? "success"
                      : "warning"
                  }
                >
                  {closure.readiness.ready_for_reproducibility
                    ? t("repro_ready")
                    : t("repro_pending")}
                </Badge>
              </div>
              <div className="page-header-meta-row">
                {[
                  "supported_claims",
                  "claims_with_evidence",
                  "ready_for_writing_claims",
                  "completed_experiments",
                  "reproducibility_ready_experiments",
                  "drafts",
                  "analysis_artifacts",
                ].map((key) => (
                  <div key={key} className="metric-pill">
                    <span>{key}</span>
                    <strong>{closure.summary[key] ?? 0}</strong>
                  </div>
                ))}
              </div>
              <div className="page-header-actions">
                <button className="btn-ghost btn-sm" onClick={() => void applyClosureActionFilters()}>
                  {t("应用筛选")}
                </button>
                <button className="btn-ghost btn-sm" onClick={() => void clearClosureActionFilters()}>
                  {t("清空筛选")}
                </button>
                <button
                  className="btn-ghost btn-sm"
                  onClick={() =>
                    setSelectedClosureActionKeys((current) =>
                      toggleVisibleSelection(
                        current,
                        closureActionRows
                          .map((item) => item.closure_key || "")
                          .filter(Boolean),
                      ),
                    )
                  }
                >
                  {t("全选当前")}
                </button>
                {selectedClosureActionKeys.length ? (
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => setSelectedClosureActionKeys([])}
                  >
                    {t("清空选择")}
                  </button>
                ) : null}
              </div>
              <div className="form-stack">
                <select
                  value={closureActionFilters.kind}
                  onChange={(e) =>
                    setClosureActionFilters((current) => ({
                      ...current,
                      kind: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部 action kind")}</option>
                  <option value="claim_evidence_gap">claim_evidence_gap</option>
                  <option value="claim_review">claim_review</option>
                  <option value="claim_rigor_gap">claim_rigor_gap</option>
                  <option value="claim_writing_gap">claim_writing_gap</option>
                  <option value="experiment_contract">experiment_contract</option>
                  <option value="result_bundle">result_bundle</option>
                  <option value="result_bundle_pending">result_bundle_pending</option>
                  <option value="experiment_status">experiment_status</option>
                  <option value="workflow_blocker">workflow_blocker</option>
                  <option value="project_artifact_gap">project_artifact_gap</option>
                </select>
                <select
                  value={closureActionFilters.severity}
                  onChange={(e) =>
                    setClosureActionFilters((current) => ({
                      ...current,
                      severity: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部 severity")}</option>
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
                <select
                  value={closureActionFilters.targetType}
                  onChange={(e) =>
                    setClosureActionFilters((current) => ({
                      ...current,
                      targetType: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部 target type")}</option>
                  <option value="claim">claim</option>
                  <option value="experiment">experiment</option>
                  <option value="workflow">workflow</option>
                  <option value="project">project</option>
                </select>
                <select
                  value={closureActionFilters.workflowId}
                  onChange={(e) =>
                    setClosureActionFilters((current) => ({
                      ...current,
                      workflowId: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部 workflow")}</option>
                  {workflows.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.title}
                    </option>
                  ))}
                </select>
                <select
                  value={closureActionFilters.autoExecutable}
                  onChange={(e) =>
                    setClosureActionFilters((current) => ({
                      ...current,
                      autoExecutable: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部执行方式")}</option>
                  <option value="true">{t("可自动补齐")}</option>
                  <option value="false">{t("需生成任务")}</option>
                </select>
                <input
                  value={closureActionFilters.query}
                  onChange={(e) =>
                    setClosureActionFilters((current) => ({
                      ...current,
                      query: e.target.value,
                    }))
                  }
                  placeholder={t("搜索标题、摘要或 target id")}
                />
              </div>
              {selectedClosureActionKeys.length ? (
                <div className="form-stack">
                  <p className="muted text-sm">
                    {t(`已选择 ${selectedClosureActionKeys.length} 个闭环 action`)}
                  </p>
                  <div className="page-header-actions">
                    <button
                      className="btn-ghost btn-sm"
                      disabled={closureActionKey === `batch-closure:execute:${selectedProjectId}`}
                      onClick={() =>
                        selectedProjectId
                          ? void applyClosureActionsBatch(selectedProjectId, "execute")
                          : undefined
                      }
                    >
                      {closureActionKey === `batch-closure:execute:${selectedProjectId}`
                        ? t("处理中...")
                        : t("批量处理所选")}
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      disabled={closureActionKey === `batch-closure:materialize:${selectedProjectId}`}
                      onClick={() =>
                        selectedProjectId
                          ? void applyClosureActionsBatch(selectedProjectId, "materialize")
                          : undefined
                      }
                    >
                      {closureActionKey === `batch-closure:materialize:${selectedProjectId}`
                        ? t("生成中...")
                        : t("批量生成任务")}
                    </button>
                  </div>
                </div>
              ) : null}
              {closureActionRows.length === 0 ? (
                <p className="muted text-sm">
                  {t("当前没有明显的闭环缺口，或当前筛选条件下没有 action。")}
                </p>
              ) : (
                closureActionRows.slice(0, 8).map((item) => (
                  <DataRow
                    key={item.closure_key || `${item.kind}-${item.target_id}`}
                    title={item.title}
                    meta={`${item.summary}${item.stage ? ` · ${item.stage}` : ""}${item.suggested_tool ? ` · ${item.suggested_tool}` : ""}`}
                    badge={
                      <Badge variant={statusVariant(item.severity)}>
                        {item.severity}
                      </Badge>
                    }
                    actions={
                      selectedProjectId ? (
                        <>
                          <label className="btn-ghost btn-sm">
                            <input
                              type="checkbox"
                              checked={selectedClosureActionKeys.includes(item.closure_key || "")}
                              onChange={(e) =>
                                setSelectedClosureActionKeys((current) => {
                                  const key = item.closure_key || "";
                                  if (!key) return current;
                                  return e.target.checked
                                    ? mergeSelections(current, [key])
                                    : current.filter((id) => id !== key);
                                })
                              }
                            />
                          </label>
                          <button
                            className="btn-ghost btn-sm"
                            disabled={
                              closureActionKey ===
                              `execute-closure:${item.kind}:${item.target_id}`
                            }
                            onClick={() =>
                              void executeClosureAction(selectedProjectId, item)
                            }
                          >
                            {closureActionKey ===
                            `execute-closure:${item.kind}:${item.target_id}`
                              ? t("处理中...")
                              : item.auto_executable
                                ? t("自动补齐")
                                : t("生成任务")}
                          </button>
                        </>
                      ) : undefined
                    }
                  />
                ))
              )}
            </div>
          ) : (
            <EmptyState
              icon={<Activity size={28} />}
              title={t("等待闭环审计")}
              description={t("选中一个 project 后，这里会显示 claim 到投稿准备的闭环状态。")}
            />
          )}
        </SurfaceCard>
      </div>

      <div className="card-grid">
        <SurfaceCard
          title={t("近期阻塞")}
          description={t("优先显示 blocked workflow、未收口 remediation 和可重试实验。")}
          actions={
            selectedProjectId ? (
              <>
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => void applyBlockerFilters()}
                >
                  {t("应用筛选")}
                </button>
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => void clearBlockerFilters()}
                >
                  {t("清空筛选")}
                </button>
                <button
                  className="btn-ghost btn-sm"
                  onClick={() =>
                    setSelectedBlockerWorkflowIds((current) =>
                      toggleVisibleSelection(
                        current,
                        Array.from(
                          new Set(
                            blockerRows.flatMap((item) =>
                              item.workflow_id ? [item.workflow_id] : [],
                            ),
                          ),
                        ),
                      ),
                    )
                  }
                >
                  {t("全选当前")}
                </button>
                {selectedBlockerWorkflowIds.length ? (
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => setSelectedBlockerWorkflowIds([])}
                  >
                    {t("清空选择")}
                  </button>
                ) : null}
              </>
            ) : undefined
          }
        >
          {!selectedProjectId ? (
            <EmptyState
              icon={<AlertTriangle size={28} />}
              title={t("等待项目上下文")}
              description={t("选中一个 project 后，这里会显示可操作的 blocker 列表。")}
            />
          ) : (
            <>
              <div className="form-stack">
                <select
                  value={blockerFilters.kind}
                  onChange={(e) =>
                    setBlockerFilters((current) => ({
                      ...current,
                      kind: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部 blocker 类型")}</option>
                  <option value="workflow_blocker">workflow_blocker</option>
                </select>
                <select
                  value={blockerFilters.workflowId}
                  onChange={(e) =>
                    setBlockerFilters((current) => ({
                      ...current,
                      workflowId: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部 workflow")}</option>
                  {workflows.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.title}
                    </option>
                  ))}
                </select>
                <select
                  value={blockerFilters.status}
                  onChange={(e) =>
                    setBlockerFilters((current) => ({
                      ...current,
                      status: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部状态")}</option>
                  <option value="blocked">blocked</option>
                  <option value="running">running</option>
                  <option value="paused">paused</option>
                </select>
                <input
                  value={blockerFilters.stage}
                  onChange={(e) =>
                    setBlockerFilters((current) => ({
                      ...current,
                      stage: e.target.value,
                    }))
                  }
                  placeholder={t("按 stage 筛选")}
                />
                <select
                  value={blockerFilters.readyForRetry}
                  onChange={(e) =>
                    setBlockerFilters((current) => ({
                      ...current,
                      readyForRetry: e.target.value,
                    }))
                  }
                >
                  <option value="">{t("全部重试状态")}</option>
                  <option value="true">{t("可恢复重试")}</option>
                  <option value="false">{t("待 remediation")}</option>
                </select>
                <input
                  value={blockerFilters.query}
                  onChange={(e) =>
                    setBlockerFilters((current) => ({
                      ...current,
                      query: e.target.value,
                    }))
                  }
                  placeholder={t("搜索 blocker 标题、摘要或 remediation task")}
                />
              </div>
              {blockerRows.length ? (
                <div className="form-stack" style={{ marginTop: 12 }}>
                  <p className="muted text-sm">
                    {t(`当前筛出 ${blockerRows.length} 条 blocker`)}
                    {selectedBlockerWorkflowIds.length
                      ? t(`，已选择 ${selectedBlockerWorkflowIds.length} 个 workflow`)
                      : ""}
                  </p>
                  <div className="page-header-meta-row">
                    <button
                      className="btn-ghost btn-sm"
                      disabled={projectActionKey === `dispatch:${selectedProjectId}`}
                      onClick={() =>
                        void runProjectBlockerAction(selectedProjectId, "dispatch")
                      }
                    >
                      {projectActionKey === `dispatch:${selectedProjectId}`
                        ? t("项目派发中...")
                        : t("项目批量派发")}
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      disabled={projectActionKey === `execute:${selectedProjectId}`}
                      onClick={() =>
                        void runProjectBlockerAction(selectedProjectId, "execute")
                      }
                    >
                      {projectActionKey === `execute:${selectedProjectId}`
                        ? t("项目执行中...")
                        : t("项目批量执行")}
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      disabled={projectActionKey === `resume:${selectedProjectId}`}
                      onClick={() =>
                        void runProjectBlockerAction(selectedProjectId, "resume")
                      }
                    >
                      {projectActionKey === `resume:${selectedProjectId}`
                        ? t("恢复中...")
                        : t("恢复可重试")}
                    </button>
                  </div>
                  {selectedBlockerWorkflowIds.length ? (
                    <div className="page-header-meta-row">
                      <button
                        className="btn-ghost btn-sm"
                        disabled={
                          projectActionKey === `selected-dispatch:${selectedProjectId}`
                        }
                        onClick={() =>
                          void applyProjectBlockersBatch(selectedProjectId, "dispatch")
                        }
                      >
                        {projectActionKey === `selected-dispatch:${selectedProjectId}`
                          ? t("派发中...")
                          : t("派发所选")}
                      </button>
                      <button
                        className="btn-ghost btn-sm"
                        disabled={
                          projectActionKey === `selected-execute:${selectedProjectId}`
                        }
                        onClick={() =>
                          void applyProjectBlockersBatch(selectedProjectId, "execute")
                        }
                      >
                        {projectActionKey === `selected-execute:${selectedProjectId}`
                          ? t("执行中...")
                          : t("执行所选")}
                      </button>
                      <button
                        className="btn-ghost btn-sm"
                        disabled={
                          projectActionKey === `selected-resume:${selectedProjectId}`
                        }
                        onClick={() =>
                          void applyProjectBlockersBatch(selectedProjectId, "resume")
                        }
                      >
                        {projectActionKey === `selected-resume:${selectedProjectId}`
                          ? t("恢复中...")
                          : t("恢复所选")}
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {blockerRows.length === 0 ? (
                <EmptyState
                  icon={<AlertTriangle size={28} />}
                  title={t("暂无显著阻塞")}
                  description={t("当前 project 没有需要优先处理的 contract 或 workflow blocker。")}
                />
              ) : (
                blockerRows.slice(0, 8).map((blocker) => {
                  const primaryTask = blocker.actionable_tasks?.[0];
                  const workflowSelectionId = blocker.workflow_id || "";
                  return (
                    <DataRow
                      key={`${blocker.kind}-${blocker.workflow_id || blocker.experiment_id || blocker.title}`}
                      title={blocker.title}
                      meta={`${blocker.stage || blocker.kind} · ${blocker.summary}${blocker.open_remediation_tasks ? ` · open=${blocker.open_remediation_tasks}` : ""}${blocker.contract_failure_count ? ` · contract=${blocker.contract_failure_count}` : ""}${primaryTask?.title ? ` · ${primaryTask.title}` : ""}`}
                      badge={
                        <Badge
                          variant={
                            blocker.ready_for_retry
                              ? "info"
                              : statusVariant(blocker.status || "blocked")
                          }
                        >
                          {blocker.ready_for_retry ? t("ready_for_retry") : blocker.status}
                        </Badge>
                      }
                      actions={
                        workflowSelectionId ? (
                          <>
                            <label className="btn-ghost btn-sm">
                              <input
                                type="checkbox"
                                checked={selectedBlockerWorkflowIds.includes(
                                  workflowSelectionId,
                                )}
                                onChange={(e) =>
                                  setSelectedBlockerWorkflowIds((current) =>
                                    e.target.checked
                                      ? mergeSelections(current, [workflowSelectionId])
                                      : current.filter((id) => id !== workflowSelectionId),
                                  )
                                }
                              />
                            </label>
                            <button
                              className="btn-ghost btn-sm"
                              onClick={() =>
                                void openRemediationDetails(
                                  workflowSelectionId,
                                  blocker.title,
                                )
                              }
                            >
                              {t("详情")}
                            </button>
                            {primaryTask ? (
                              <>
                                <button
                                  className="btn-ghost btn-sm"
                                  disabled={
                                    !primaryTask.can_dispatch
                                    || taskActionKey === `dispatch:${primaryTask.task_id}`
                                  }
                                  onClick={() =>
                                    void runBlockerTaskAction(
                                      workflowSelectionId,
                                      primaryTask.task_id,
                                      "dispatch",
                                    )
                                  }
                                >
                                  {taskActionKey === `dispatch:${primaryTask.task_id}`
                                    ? t("派发中...")
                                    : t("派发")}
                                </button>
                                <button
                                  className="btn-ghost btn-sm"
                                  disabled={
                                    !primaryTask.can_execute
                                    || taskActionKey === `execute:${primaryTask.task_id}`
                                  }
                                  onClick={() =>
                                    void runBlockerTaskAction(
                                      workflowSelectionId,
                                      primaryTask.task_id,
                                      "execute",
                                    )
                                  }
                                >
                                  {taskActionKey === `execute:${primaryTask.task_id}`
                                    ? t("执行中...")
                                    : t("执行")}
                                </button>
                              </>
                            ) : null}
                          </>
                        ) : undefined
                      }
                    />
                  );
                })
              )}
            </>
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("主动提醒")}
          description={t("这里展示当前到期的 follow-up、写作待办和实验回看提醒。")}
        >
          {reminders.length === 0 ? (
            <EmptyState
              icon={<Bell size={28} />}
              title={t("暂无到期提醒")}
              description={t("当前没有需要主动推进的研究提醒。")}
            />
          ) : (
            reminders.map((reminder) => (
              <DataRow
                key={reminder.id}
                title={reminder.title}
                meta={reminder.summary}
                badge={<Badge variant="warning">{reminder.reminder_type}</Badge>}
              />
            ))
          )}
        </SurfaceCard>

        <SurfaceCard
          title={t("Artifact 血缘")}
          description={t("查看 derived_from / uses / produces 等关系，确认研究资产的追溯链。")}
        >
          {artifactRelations.length === 0 ? (
            <EmptyState
              icon={<GitBranch size={28} />}
              title={t("暂无 artifact relation")}
              description={t("当 artifact 之间形成结构化关系后，这里会显示血缘边。")}
            />
          ) : (
            artifactRelations.slice(0, 8).map((relation) => (
              <DataRow
                key={relation.id}
                title={relation.summary || relation.relation_type}
                meta={`${artifactTitle(relation.source_artifact_id)} → ${artifactTitle(relation.target_artifact_id)}`}
                badge={<Badge variant="info">{relation.relation_type}</Badge>}
                actions={
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() =>
                      void openArtifactLineage(
                        relation.source_artifact_id,
                        artifactTitle(relation.source_artifact_id),
                      )
                    }
                  >
                    {t("查看链路")}
                  </button>
                }
              />
            ))
          )}
        </SurfaceCard>
      </div>

      <SurfaceCard
        title={t("Claim 与证据链")}
        description={t("按状态、workflow 和 evidence 覆盖筛选 claim，并批量推进它们进入下一阶段。")}
        actions={
          <>
            <button className="btn-ghost btn-sm" onClick={() => void applyClaimFilters()}>
              {t("应用筛选")}
            </button>
            <button className="btn-ghost btn-sm" onClick={() => void clearClaimFilters()}>
              {t("清空筛选")}
            </button>
            <button
              className="btn-ghost btn-sm"
              onClick={() =>
                setSelectedClaimIds((current) =>
                  toggleVisibleSelection(
                    current,
                    claimRows.map((item) => item.id),
                  ),
                )
              }
            >
              {t("全选当前")}
            </button>
            {selectedClaimIds.length ? (
              <button
                className="btn-ghost btn-sm"
                onClick={() => setSelectedClaimIds([])}
              >
                {t("清空选择")}
              </button>
            ) : null}
          </>
        }
      >
        <div className="form-stack">
          <select
            value={claimFilters.workflowId}
            onChange={(e) =>
              setClaimFilters((current) => ({
                ...current,
                workflowId: e.target.value,
              }))
            }
          >
            <option value="">{t("全部 workflow")}</option>
            {workflows.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.title}
              </option>
            ))}
          </select>
          <select
            value={claimFilters.status}
            onChange={(e) =>
              setClaimFilters((current) => ({
                ...current,
                status: e.target.value,
              }))
            }
          >
            <option value="">{t("全部状态")}</option>
            <option value="draft">draft</option>
            <option value="supported">supported</option>
            <option value="needs_review">needs_review</option>
            <option value="disputed">disputed</option>
          </select>
          <select
            value={claimFilters.hasEvidence}
            onChange={(e) =>
              setClaimFilters((current) => ({
                ...current,
                hasEvidence: e.target.value,
              }))
            }
          >
            <option value="">{t("全部 evidence 状态")}</option>
            <option value="true">{t("有 evidence")}</option>
            <option value="false">{t("无 evidence")}</option>
          </select>
          <input
            value={claimFilters.query}
            onChange={(e) =>
              setClaimFilters((current) => ({
                ...current,
                query: e.target.value,
              }))
            }
            placeholder={t("搜索 claim 文本")}
          />
        </div>
        {selectedClaimIds.length ? (
          <div className="form-stack" style={{ marginTop: 12 }}>
            <p className="muted text-sm">
              {t(`已选择 ${selectedClaimIds.length} 条 claim`)}
            </p>
            <select
              value={claimBulkForm.status}
              onChange={(e) =>
                setClaimBulkForm((current) => ({
                  ...current,
                  status: e.target.value,
                }))
              }
            >
              <option value="">{t("保持状态不变")}</option>
              <option value="draft">draft</option>
              <option value="supported">supported</option>
              <option value="needs_review">needs_review</option>
              <option value="disputed">disputed</option>
            </select>
            <select
              value={claimBulkForm.workflowId}
              onChange={(e) =>
                setClaimBulkForm((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("保持 workflow 不变")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <button
              disabled={bulkActionKey === "claim"}
              onClick={() => void applyClaimBulkUpdate()}
            >
              {bulkActionKey === "claim" ? t("批量更新中...") : t("批量更新 claim")}
            </button>
          </div>
        ) : null}
        {claimRows.length === 0 ? (
          <EmptyState
            icon={<Activity size={28} />}
            title={t("暂无 claim")}
            description={t("当前项目还没有结构化 claim，或当前筛选条件下没有结果。")}
          />
        ) : (
          claimRows.slice(0, 10).map((claim) => (
            <DataRow
              key={claim.id}
              title={claim.text}
              meta={`evidence=${claim.evidence_ids?.length || 0} · notes=${claim.note_ids?.length || 0} · artifacts=${claim.artifact_ids?.length || 0}`}
              badge={
                <Badge variant={statusVariant(claim.status)}>{claim.status}</Badge>
              }
              actions={
                <>
                  <label className="btn-ghost btn-sm">
                    <input
                      type="checkbox"
                      checked={selectedClaimIds.includes(claim.id)}
                      onChange={(e) =>
                        setSelectedClaimIds((current) =>
                          e.target.checked
                            ? mergeSelections(current, [claim.id])
                            : current.filter((id) => id !== claim.id),
                        )
                      }
                    />
                  </label>
                  <button
                    className="btn-ghost btn-sm"
                    disabled={claimLoadingId === claim.id}
                    onClick={() => void openClaimGraph(claim.id)}
                  >
                    {claimLoadingId === claim.id ? t("加载中...") : t("查看")}
                  </button>
                </>
              }
            />
          ))
        )}
      </SurfaceCard>

      <SurfaceCard
        title={t("Artifacts 目录")}
        description={t("筛选 paper / analysis / draft / dataset 等 artifact，并批量维护 workflow 与来源类型。")}
        actions={
          <>
            <button className="btn-ghost btn-sm" onClick={() => void applyArtifactFilters()}>
              {t("应用筛选")}
            </button>
            <button className="btn-ghost btn-sm" onClick={() => void clearArtifactFilters()}>
              {t("清空筛选")}
            </button>
            <button
              className="btn-ghost btn-sm"
              onClick={() =>
                setSelectedArtifactIds((current) =>
                  toggleVisibleSelection(
                    current,
                    artifactRows.map((item) => item.id),
                  ),
                )
              }
            >
              {t("全选当前")}
            </button>
            {selectedArtifactIds.length ? (
              <button
                className="btn-ghost btn-sm"
                onClick={() => setSelectedArtifactIds([])}
              >
                {t("清空选择")}
              </button>
            ) : null}
          </>
        }
      >
        <div className="form-stack">
          <select
            value={artifactFilters.workflowId}
            onChange={(e) =>
              setArtifactFilters((current) => ({
                ...current,
                workflowId: e.target.value,
              }))
            }
          >
            <option value="">{t("全部 workflow")}</option>
            {workflows.map((workflow) => (
              <option key={workflow.id} value={workflow.id}>
                {workflow.title}
              </option>
            ))}
          </select>
          <select
            value={artifactFilters.artifactType}
            onChange={(e) =>
              setArtifactFilters((current) => ({
                ...current,
                artifactType: e.target.value,
              }))
            }
          >
            <option value="">{t("全部 artifact type")}</option>
            <option value="paper">paper</option>
            <option value="analysis">analysis</option>
            <option value="draft">draft</option>
            <option value="dataset">dataset</option>
            <option value="summary">summary</option>
            <option value="generated_table">generated_table</option>
            <option value="generated_figure">generated_figure</option>
            <option value="code_snapshot">code_snapshot</option>
            <option value="config_snapshot">config_snapshot</option>
          </select>
          <input
            value={artifactFilters.sourceType}
            onChange={(e) =>
              setArtifactFilters((current) => ({
                ...current,
                sourceType: e.target.value,
              }))
            }
            placeholder={t("按 source_type 筛选")}
          />
          <input
            value={artifactFilters.query}
            onChange={(e) =>
              setArtifactFilters((current) => ({
                ...current,
                query: e.target.value,
              }))
            }
            placeholder={t("搜索标题、描述或来源")}
          />
        </div>
        {selectedArtifactIds.length ? (
          <div className="form-stack" style={{ marginTop: 12 }}>
            <p className="muted text-sm">
              {t(`已选择 ${selectedArtifactIds.length} 个 artifact`)}
            </p>
            <select
              value={artifactBulkForm.workflowId}
              onChange={(e) =>
                setArtifactBulkForm((current) => ({
                  ...current,
                  workflowId: e.target.value,
                }))
              }
            >
              <option value="">{t("保持 workflow 不变")}</option>
              {workflows.map((workflow) => (
                <option key={workflow.id} value={workflow.id}>
                  {workflow.title}
                </option>
              ))}
            </select>
            <input
              value={artifactBulkForm.sourceType}
              onChange={(e) =>
                setArtifactBulkForm((current) => ({
                  ...current,
                  sourceType: e.target.value,
                }))
              }
              placeholder={t("批量设置 source_type")}
            />
            <button
              disabled={bulkActionKey === "artifact"}
              onClick={() => void applyArtifactBulkUpdate()}
            >
              {bulkActionKey === "artifact"
                ? t("批量更新中...")
                : t("批量更新 artifact")}
            </button>
          </div>
        ) : null}
        {artifactRows.length === 0 ? (
          <EmptyState
            icon={<FolderOpen size={28} />}
            title={t("暂无 artifact")}
            description={t("当前项目还没有结构化 artifact，或当前筛选条件下没有结果。")}
          />
        ) : (
          artifactRows.slice(0, 10).map((artifact) => (
            <DataRow
              key={artifact.id}
              title={artifact.title}
              meta={`${artifact.artifact_type} · ${artifact.source_type || t("无 source_type")} · notes=${artifact.note_ids?.length || 0} · claims=${artifact.claim_ids?.length || 0}${artifact.path ? ` · ${artifact.path}` : ""}`}
              badge={<Badge variant="info">{artifact.artifact_type}</Badge>}
              actions={
                <>
                  <label className="btn-ghost btn-sm">
                    <input
                      type="checkbox"
                      checked={selectedArtifactIds.includes(artifact.id)}
                      onChange={(e) =>
                        setSelectedArtifactIds((current) =>
                          e.target.checked
                            ? mergeSelections(current, [artifact.id])
                            : current.filter((id) => id !== artifact.id),
                        )
                      }
                    />
                  </label>
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => void openArtifactLineage(artifact.id, artifact.title)}
                  >
                    {t("查看血缘")}
                  </button>
                </>
              }
            />
          ))
        )}
      </SurfaceCard>

      {claimGraph && (
        <DetailModal
          title={t("Claim 证据详情")}
          onClose={() => setClaimGraph(null)}
        >
          <div className="form-stack">
            <div>
              <h4>{claimGraph.claim.text}</h4>
              <p className="muted text-sm">
                {claimGraph.project?.name || "-"} · {claimGraph.claim.status}
              </p>
            </div>
            <div>
              <h4>{t("Evidence")}</h4>
              {claimGraph.evidences.length === 0 ? (
                <p className="muted text-sm">{t("暂无证据")}</p>
              ) : (
                claimGraph.evidences.map((item) => (
                  <div key={item.id} className="pre">
                    <strong>{item.evidence_type}</strong>
                    <p>{item.summary}</p>
                    {item.source?.title && (
                      <p className="muted text-sm">
                        {item.source.title}
                        {item.source.locator ? ` · ${item.source.locator}` : ""}
                      </p>
                    )}
                    {item.source?.quote && (
                      <pre>{item.source.quote}</pre>
                    )}
                  </div>
                ))
              )}
            </div>
            <div>
              <h4>{t("关联对象")}</h4>
              <p className="muted text-sm">
                notes={claimGraph.notes.length} · artifacts={claimGraph.artifacts.length} · experiments=
                {claimGraph.experiments.length}
              </p>
            </div>
          </div>
        </DetailModal>
      )}

      {checkpointModal && (
        <DetailModal
          title={`${t("Workflow 检查点")} · ${checkpointModal.title}`}
          onClose={() => {
            setCheckpointModal(null);
            setCheckpoints([]);
          }}
        >
          {checkpointLoading ? (
            <Loading text={t("加载 checkpoint...")} />
          ) : checkpoints.length === 0 ? (
            <EmptyState
              icon={<RotateCcw size={28} />}
              title={t("暂无 checkpoint")}
              description={t("当前 workflow 还没有可恢复的 checkpoint。")}
            />
          ) : (
            <div className="form-stack">
              {checkpoints.map((checkpoint) => (
                <DataRow
                  key={checkpoint.id}
                  title={`${checkpoint.stage} · ${checkpoint.workflow_status}`}
                  meta={`${checkpoint.reason || t("自动记录")} · ${formatTimestamp(checkpoint.created_at)}`}
                  badge={<Badge variant={statusVariant(checkpoint.workflow_status)}>{checkpoint.workflow_status}</Badge>}
                  actions={
                    <button
                      className="btn-ghost btn-sm"
                      disabled={checkpointActionKey === checkpoint.id}
                      onClick={() =>
                        void restoreCheckpoint(
                          checkpointModal.workflowId,
                          checkpoint.id,
                        )
                      }
                    >
                      {checkpointActionKey === checkpoint.id
                        ? t("恢复中...")
                        : t("恢复")}
                    </button>
                  }
                />
              ))}
            </div>
          )}
        </DetailModal>
      )}

      {lineageModal && (
        <DetailModal
          title={`${t("Artifact 血缘详情")} · ${lineageModal.title}`}
          onClose={() => {
            setLineageModal(null);
            setLineageData(null);
          }}
        >
          {lineageLoading ? (
            <Loading text={t("加载 lineage...")} />
          ) : lineageData ? (
            <div className="form-stack">
              <div className="page-header-meta-row">
                <div className="metric-pill">
                  <span>{t("artifact_type")}</span>
                  <strong>{lineageData.artifact.artifact_type}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("relations")}</span>
                  <strong>{lineageData.relations.length}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("related_artifacts")}</span>
                  <strong>{lineageData.related_artifacts.length}</strong>
                </div>
              </div>
              <div className="pre">
                <strong>{lineageData.artifact.title}</strong>
                <p>{lineageData.artifact.path || lineageData.artifact.source_id || "-"}</p>
              </div>
              <div>
                <h4>{t("血缘关系")}</h4>
                {lineageData.relations.length === 0 ? (
                  <p className="muted text-sm">{t("暂无结构化关系")}</p>
                ) : (
                  lineageData.relations.map((relation) => (
                    <DataRow
                      key={relation.id}
                      title={relation.summary || relation.relation_type}
                      meta={`${artifactTitle(relation.source_artifact_id)} → ${artifactTitle(relation.target_artifact_id)}`}
                      badge={<Badge variant="info">{relation.relation_type}</Badge>}
                    />
                  ))
                )}
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<GitBranch size={28} />}
              title={t("暂无 lineage 数据")}
              description={t("当前 artifact 还没有可展示的血缘信息。")}
            />
          )}
        </DetailModal>
      )}

      {replayModal && (
        <DetailModal
          title={`${t("Experiment Replay")} · ${replayModal.title}`}
          onClose={() => {
            setReplayModal(null);
            setReplayPlan(null);
          }}
        >
          {replayLoading ? (
            <Loading text={t("加载 replay plan...")} />
          ) : replayPlan ? (
            <div className="form-stack">
              <div className="page-header-meta-row">
                <div className="metric-pill">
                  <span>{t("execution_mode")}</span>
                  <strong>{replayPlan.execution_mode || "-"}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("datasets")}</span>
                  <strong>{replayPlan.dataset_versions?.length || 0}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("env_keys")}</span>
                  <strong>{replayPlan.environment_keys?.length || 0}</strong>
                </div>
              </div>
              <div className="pre">
                <strong>{t("命令")}</strong>
                <p>{summarizeCommand(replayPlan.command)}</p>
                <p className="muted text-sm">{replayPlan.working_dir || t("未声明 working_dir")}</p>
              </div>
              <div>
                <h4>{t("Dataset Versions")}</h4>
                {replayPlan.dataset_versions?.length ? (
                  replayPlan.dataset_versions.map((dataset) => (
                    <DataRow
                      key={dataset.id}
                      title={`${dataset.name} · ${dataset.version_label}`}
                      meta={dataset.manifest_path || dataset.path || "-"}
                      badge={<Badge variant="info">{dataset.version_label}</Badge>}
                    />
                  ))
                ) : (
                  <p className="muted text-sm">{t("未绑定 dataset version")}</p>
                )}
              </div>
              <div>
                <h4>{t("Fingerprint")}</h4>
                <pre>
                  {JSON.stringify(
                    {
                      dependency_fingerprint: replayPlan.dependency_fingerprint,
                      input_hashes: replayPlan.input_hashes,
                      output_hashes: replayPlan.output_hashes,
                    },
                    null,
                    2,
                  )}
                </pre>
              </div>
              <div className="page-header-actions">
                <button
                  className="btn-ghost btn-sm"
                  disabled={experimentActionKey === replayModal.experimentId}
                  onClick={() =>
                    void triggerExperimentReplay(replayModal.experimentId)
                  }
                >
                  {experimentActionKey === replayModal.experimentId
                    ? t("重放中...")
                    : t("触发重放")}
                </button>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<Activity size={28} />}
              title={t("暂无 replay plan")}
              description={t("当前 experiment 还不能生成 replay plan。")}
            />
          )}
        </DetailModal>
      )}

      {packageResult && (
        <DetailModal
          title={t("投稿包详情")}
          onClose={() => setPackageResult(null)}
        >
          <div className="form-stack">
            <div className="page-header-meta-row">
              <div className="metric-pill">
                <span>{t("included_files")}</span>
                <strong>{packageResult.included_file_count}</strong>
              </div>
              <div className="metric-pill">
                <span>{t("missing_files")}</span>
                <strong>{packageResult.missing_file_count}</strong>
              </div>
            </div>
            <div>
              <h4>{t("输出路径")}</h4>
              <pre>{packageResult.archive_path}</pre>
              <pre>{packageResult.manifest_path}</pre>
            </div>
            <div>
              <h4>{t("Included")}</h4>
              {packageResult.included_files?.length ? (
                packageResult.included_files.slice(0, 10).map((item) => (
                  <div key={`${item.kind}-${item.id}-${item.bundle_path}`} className="pre">
                    <strong>{item.title || item.id || item.kind}</strong>
                    <p>{item.bundle_path}</p>
                  </div>
                ))
              ) : (
                <p className="muted text-sm">{t("暂无打包文件")}</p>
              )}
            </div>
            <div>
              <h4>{t("Missing")}</h4>
              {packageResult.missing_files?.length ? (
                packageResult.missing_files.slice(0, 10).map((item) => (
                  <div key={`${item.kind}-${item.id}-${item.source_path}`} className="pre">
                    <strong>{item.title || item.id || item.kind}</strong>
                    <p>{item.source_path}</p>
                  </div>
                ))
              ) : (
                <p className="muted text-sm">{t("没有缺失文件")}</p>
              )}
            </div>
          </div>
        </DetailModal>
      )}

      {remediationModal && (
        <DetailModal
          title={`${t("Remediation 详情")} · ${remediationModal.title}`}
          onClose={() => {
            setRemediationModal(null);
            setRemediationContext(null);
          }}
        >
          {remediationLoading ? (
            <Loading text={t("加载 remediation 上下文...")} />
          ) : remediationContext ? (
            <div className="form-stack">
              <div className="page-header-meta-row">
                <div className="metric-pill">
                  <span>{t("ready_for_retry")}</span>
                  <strong>{String(Boolean(remediationContext.ready_for_retry))}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("retry_exhausted")}</span>
                  <strong>{remediationContext.retry_exhausted_count || 0}</strong>
                </div>
                <div className="metric-pill">
                  <span>{t("open_tasks")}</span>
                  <strong>{remediationContext.remediation_tasks.length}</strong>
                </div>
              </div>
              <p className="muted text-sm">
                {remediationContext.remediation_summary || t("暂无 remediation 摘要")}
              </p>
              <div className="page-header-actions">
                <button
                  className="btn-ghost btn-sm"
                  disabled={
                    !remediationContext.ready_for_retry ||
                    executingWorkflowId === remediationModal.workflowId
                  }
                  onClick={() => void executeWorkflow(remediationModal.workflowId)}
                >
                  {executingWorkflowId === remediationModal.workflowId
                    ? t("恢复中...")
                    : t("继续推进")}
                </button>
                <button
                  className="btn-ghost btn-sm"
                  disabled={
                    taskActionKey ===
                    `dispatch-remediation:${remediationModal.workflowId}`
                  }
                  onClick={() =>
                    void runRemediationBatchAction(
                      remediationModal.workflowId,
                      "dispatch",
                    )
                  }
                >
                  {taskActionKey ===
                  `dispatch-remediation:${remediationModal.workflowId}`
                    ? t("批量派发中...")
                    : t("批量派发")}
                </button>
                <button
                  className="btn-ghost btn-sm"
                  disabled={
                    taskActionKey ===
                    `execute-remediation:${remediationModal.workflowId}`
                  }
                  onClick={() =>
                    void runRemediationBatchAction(
                      remediationModal.workflowId,
                      "execute",
                    )
                  }
                >
                  {taskActionKey ===
                  `execute-remediation:${remediationModal.workflowId}`
                    ? t("批量执行中...")
                    : t("批量执行")}
                </button>
              </div>
              <div>
                <h4>{t("Contract Failures")}</h4>
                {remediationContext.contract_failures.length === 0 ? (
                  <p className="muted text-sm">{t("暂无 contract failure")}</p>
                ) : (
                  remediationContext.contract_failures.map((failure) => (
                    <div
                      key={`${failure.experiment_id || failure.experiment_name}`}
                      className="pre"
                    >
                      <strong>{failure.experiment_name || failure.experiment_id}</strong>
                      <p>{failure.summary}</p>
                    </div>
                  ))
                )}
              </div>
              <div>
                <h4>{t("Remediation Tasks")}</h4>
                {remediationContext.remediation_tasks.length === 0 ? (
                  <p className="muted text-sm">{t("暂无 remediation task")}</p>
                ) : (
                  remediationContext.remediation_tasks.map((task) => (
                    <DataRow
                      key={task.id}
                      title={task.title}
                      meta={`${task.action_type || "generic"} · ${task.target || task.suggested_tool || task.assignee || "-"}`}
                      badge={
                        <Badge variant={statusVariant(task.status || "pending")}>
                          {task.status}
                        </Badge>
                      }
                      actions={
                        <>
                          <button
                            className="btn-ghost btn-sm"
                            disabled={
                              !task.can_dispatch ||
                              taskActionKey === `dispatch:${task.id}`
                            }
                            onClick={() =>
                              void runBlockerTaskAction(
                                remediationModal.workflowId,
                                task.id,
                                "dispatch",
                              )
                            }
                          >
                            {taskActionKey === `dispatch:${task.id}`
                              ? t("派发中...")
                              : t("派发")}
                          </button>
                          <button
                            className="btn-ghost btn-sm"
                            disabled={
                              !task.can_execute ||
                              taskActionKey === `execute:${task.id}`
                            }
                            onClick={() =>
                              void runBlockerTaskAction(
                                remediationModal.workflowId,
                                task.id,
                                "execute",
                              )
                            }
                          >
                            {taskActionKey === `execute:${task.id}`
                              ? t("执行中...")
                              : t("执行")}
                          </button>
                        </>
                      }
                    />
                  ))
                )}
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<AlertTriangle size={28} />}
              title={t("暂无 remediation 详情")}
              description={t("当前 workflow 没有可用的 remediation context。")}
            />
          )}
        </DetailModal>
      )}
    </div>
  );
}
