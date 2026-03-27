export type ChatMessage = {
  role: "user" | "assistant" | "tool";
  content: string;
  /** Thinking/reasoning content (from thinking models) */
  thinking?: string;
  /** Skill traces captured during this turn */
  skillTraces?: SkillTraceInfo[];
  /** Tool calls made in this turn */
  toolCalls?: ToolCallInfo[];
};

export type ToolCallInfo = {
  name: string;
  arguments?: string;
  result?: string;
  status?: "running" | "done" | "error";
  skillId?: string;
  skillName?: string;
};

export type SkillTraceInfo = {
  id: string;
  name: string;
  mode?: string;
  matched?: string[];
  availableTools?: string[];
  calledTools?: ToolCallInfo[];
};

/** SSE event from /api/agent/chat/stream */
export type StreamEvent = {
  type:
    | "heartbeat"
    | "thinking"
    | "content"
    | "content_replace"
    | "skill_call"
    | "tool_call"
    | "tool_result"
    | "done"
    | "error";
  content?: string;
  name?: string;
  arguments?: string;
  result?: string;
  skill_id?: string;
  skill_name?: string;
  skill_mode?: string;
  matched?: string[];
  available_tools?: string[];
  session_id?: string;
  agent_id?: string;
};

export type PaperItem = {
  title?: string;
  id?: string;
  published?: string;
  authors?: string[];
  summary?: string;
};

export type CronTaskType = "agent" | "text";

export type CronJobRequest = {
  input: unknown;
  session_id?: string | null;
  user_id?: string | null;
  [key: string]: unknown;
};

export type SessionItem = {
  agent_id?: string;
  session_id: string;
  title?: string;
  created_at?: number;
  updated_at?: number;
  message_count?: number;
};

export type SessionDeleteTarget = {
  session_id: string;
  agent_id?: string;
};

export type SessionBatchDeleteResult = {
  deleted: Array<{
    deleted: boolean;
    session_id: string;
    agent_id: string;
    memory_messages_deleted?: number;
  }>;
  deleted_count: number;
  not_found?: Array<{
    session_id: string;
    agent_id: string;
    detail?: string;
  }>;
};

export type CronJobItem = {
  id: string;
  name: string;
  enabled: boolean;
  task_type: CronTaskType;
  cron: string;
  timezone: string;
  channel: string;
  target_user_id: string;
  target_session_id: string;
  mode: "stream" | "final";
  text?: string | null;
  request?: CronJobRequest | null;
  schedule: {
    type: "cron";
    cron: string;
    timezone: string;
  };
  dispatch: {
    type: "channel";
    channel: string;
    target: {
      user_id: string;
      session_id: string;
    };
    mode: "stream" | "final";
    meta: Record<string, unknown>;
  };
  runtime: {
    max_concurrency: number;
    timeout_seconds: number;
    misfire_grace_seconds: number;
  };
  meta: Record<string, unknown>;
};

export type CronJobState = {
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_status?: "success" | "error" | "running" | "queued" | "skipped" | null;
  last_error?: string | null;
  pending_runs?: number;
  running_count?: number;
};

export type PushMessage = {
  id: string;
  text: string;
};

export type ChannelItem = {
  name: string;
  type: string;
};

export type EnvItem = {
  key: string;
  value: string;
};

export type SkillEnvRequirement = {
  name?: string;
  required?: boolean;
  secret?: boolean;
  description?: string;
  default?: string;
};

export type SkillRequirements = {
  env?: Array<SkillEnvRequirement | string>;
  [key: string]: unknown;
};

export type SkillItem = {
  id?: string;
  name?: string;
  enabled?: boolean;
  description?: string;
  source?: string;
  scope?: string;
  path?: string;
  location?: string;
  format?: string;
  diagnostics?: string[];
  triggers?: string[];
  requires?: SkillRequirements;
};

export type SkillRewriteSummary = {
  mirrored_files?: number;
  path_updates?: number;
  model_used?: boolean;
  model_name?: string;
  diagnostics?: string[];
};

export type ImportedSkillItem = {
  name: string;
  enabled: boolean;
  source_url: string;
  skill_root?: string;
  rewrite?: SkillRewriteSummary;
};

export type SkillRepositoryImportResult = {
  repo_url: string;
  source_url: string;
  ref: string;
  count: number;
  imported: ImportedSkillItem[];
  diagnostics?: string[];
};

export type SkillImportProgressEvent = {
  type:
    | "start"
    | "stage"
    | "discovered"
    | "skill_start"
    | "skill_done"
    | "warning"
    | "done"
    | "error";
  message?: string;
  phase?: string;
  repo_url?: string;
  requested_ref?: string;
  ref?: string;
  count?: number;
  roots?: string[];
  index?: number;
  total?: number;
  skill_root?: string;
  skill_name?: string;
  skill?: ImportedSkillItem;
  result?: SkillRepositoryImportResult;
};

export type SkillDeleteResult = {
  ok: boolean;
  skill: string;
  action: "deleted" | "hidden" | string;
  source?: string;
};

export type SkillBatchDeleteResult = {
  deleted: SkillDeleteResult[];
  deleted_count: number;
  not_found?: string[];
};

export type McpClientItem = {
  key: string;
  name?: string;
  transport?: string;
  enabled?: boolean;
  description?: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
};

export type AgentRunningConfig = {
  max_iters: number;
  max_input_length: number;
};

export type ProviderItem = {
  name: string;
  provider_type: string;
  model_name?: string;
  model_names?: string[];
  api_key?: string;
  base_url?: string;
  enabled?: boolean;
  extra?: Record<string, unknown>;
};

export type WorkspaceFileItem = {
  path: string;
  category: string;
  required?: boolean;
  exists: boolean;
  editable: boolean;
  size?: number;
  modified_at?: string | null;
};

export type WorkspaceFileContent = {
  exists: boolean;
  path: string;
  abs_path?: string;
  editable: boolean;
  size?: number;
  modified_at?: string;
  content: string;
};

export type WorkflowBinding = {
  agent_id?: string;
  channel?: string;
  user_id?: string;
  session_id?: string;
  cron_job_id?: string;
  automation_run_ids?: string[];
  last_dispatch_at?: string | null;
  last_summary?: string;
};

export type ResearchProjectItem = {
  id: string;
  name: string;
  description?: string;
  status?: string;
  tags?: string[];
  workflow_ids?: string[];
  note_ids?: string[];
  experiment_ids?: string[];
  claim_ids?: string[];
  artifact_ids?: string[];
  paper_refs?: string[];
  paper_watches?: unknown[];
  default_binding?: WorkflowBinding;
  updated_at?: string;
};

export type ResearchWorkflowTask = {
  id: string;
  stage: string;
  title: string;
  description?: string;
  status: string;
  summary?: string;
  due_at?: string | null;
};

export type ResearchWorkflowCheckpoint = {
  id: string;
  workflow_id: string;
  project_id: string;
  stage: string;
  workflow_status: string;
  reason?: string;
  task_statuses?: Record<string, string>;
  snapshot?: Record<string, unknown>;
  created_at?: string;
};

export type ResearchWorkflowItem = {
  id: string;
  project_id: string;
  title: string;
  goal?: string;
  status: string;
  current_stage: string;
  tasks?: ResearchWorkflowTask[];
  bindings?: WorkflowBinding;
  note_ids?: string[];
  claim_ids?: string[];
  experiment_ids?: string[];
  updated_at?: string;
};

export type ResearchNoteItem = {
  id: string;
  project_id: string;
  workflow_id?: string;
  title: string;
  content: string;
  note_type: string;
  experiment_ids?: string[];
  claim_ids?: string[];
  artifact_ids?: string[];
  evidence_ids?: string[];
  paper_refs?: string[];
  tags?: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchNoteBulkUpdateResult = {
  updated_count: number;
  notes: ResearchNoteItem[];
};

export type ResearchClaimItem = {
  id: string;
  project_id: string;
  workflow_id?: string;
  text: string;
  status: string;
  confidence?: number | null;
  note_ids?: string[];
  evidence_ids?: string[];
  artifact_ids?: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchClaimBulkUpdateResult = {
  updated_count: number;
  claims: ResearchClaimItem[];
};

export type ResearchProjectMemoryEntry = {
  id: string;
  project_id: string;
  workflow_id?: string;
  title: string;
  content: string;
  entry_kind: string;
  stage?: string;
  status?: string;
  note_ids?: string[];
  claim_ids?: string[];
  artifact_ids?: string[];
  experiment_ids?: string[];
  tags?: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchProjectMemoryBulkUpdateResult = {
  updated_count: number;
  entries: ResearchProjectMemoryEntry[];
};

export type ResearchEvidenceItem = {
  id: string;
  project_id: string;
  workflow_id?: string;
  claim_ids?: string[];
  experiment_id?: string;
  note_id?: string;
  artifact_id?: string;
  evidence_type: string;
  summary: string;
  source?: {
    source_type?: string;
    source_id?: string;
    title?: string;
    locator?: string;
    quote?: string;
    url?: string;
  };
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchEvidenceBulkUpdateResult = {
  updated_count: number;
  evidences: ResearchEvidenceItem[];
};

export type ResearchReminderItem = {
  id: string;
  reminder_type: string;
  project_id: string;
  workflow_id?: string;
  experiment_id?: string;
  title: string;
  summary: string;
  stage?: string;
};

export type ResearchAuditEvent = {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  project_id?: string;
  workflow_id?: string;
  summary: string;
  created_at?: string;
  actor?: string;
  metadata?: Record<string, unknown>;
};

export type ResearchDatasetVersion = {
  id: string;
  project_id: string;
  workflow_id?: string;
  name: string;
  version_label: string;
  description?: string;
  path?: string;
  manifest_path?: string;
  source_paths?: string[];
  artifact_id?: string;
  parent_version_id?: string;
  split_spec?: Record<string, unknown>;
  transform_steps?: Array<Record<string, unknown>>;
  file_hashes?: Record<string, string>;
  tags?: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchDatasetVersionBulkUpdateResult = {
  updated_count: number;
  dataset_versions: ResearchDatasetVersion[];
};

export type ResearchArtifactItem = {
  id: string;
  project_id: string;
  workflow_id?: string;
  experiment_id?: string;
  title: string;
  artifact_type: string;
  description?: string;
  path?: string;
  uri?: string;
  source_type?: string;
  source_id?: string;
  note_ids?: string[];
  claim_ids?: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchArtifactBulkUpdateResult = {
  updated_count: number;
  artifacts: ResearchArtifactItem[];
};

export type ResearchArtifactRelation = {
  id: string;
  project_id: string;
  workflow_id?: string;
  experiment_id?: string;
  relation_type: string;
  source_artifact_id: string;
  target_artifact_id: string;
  summary?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type ResearchArtifactLineage = {
  artifact: ResearchArtifactItem;
  direction: string;
  relations: ResearchArtifactRelation[];
  related_artifacts: ResearchArtifactItem[];
};

export type ResearchExperimentProvenance = {
  captured_at?: string;
  git_commit?: string;
  git_branch?: string;
  git_dirty?: boolean;
  git_diff_summary?: string;
  cwd?: string;
  command?: string[];
  environment_keys?: string[];
  dependency_fingerprint?: Record<string, unknown>;
  dataset_version_ids?: string[];
  input_hashes?: Record<string, string>;
  output_hashes?: Record<string, string>;
  replayable?: boolean;
  metadata?: Record<string, unknown>;
};

export type ResearchExperimentExecution = {
  mode?: string;
  command?: string[];
  entrypoint?: string;
  working_dir?: string;
  notebook_path?: string;
  result_bundle_file?: string;
  result_bundle_schema?: string;
  environment?: Record<string, string>;
  external_run_id?: string;
  requested_by?: string;
  instructions?: string;
  metadata?: Record<string, unknown>;
};

export type ResearchExperimentItem = {
  id: string;
  project_id: string;
  workflow_id?: string;
  name: string;
  status: string;
  parameters?: Record<string, unknown>;
  input_data?: Record<string, unknown>;
  dataset_version_ids?: string[];
  metrics?: Record<string, unknown>;
  notes?: string;
  output_files?: string[];
  related_run_ids?: string[];
  claim_ids?: string[];
  note_ids?: string[];
  artifact_ids?: string[];
  execution?: ResearchExperimentExecution;
  provenance?: ResearchExperimentProvenance;
  comparison_group?: string;
  metadata?: Record<string, unknown>;
  updated_at?: string;
};

export type ResearchExperimentBulkUpdateResult = {
  updated_count: number;
  experiments: ResearchExperimentItem[];
};

export type ResearchExperimentReplayPlan = {
  experiment: ResearchExperimentItem;
  execution_mode?: string;
  command?: string[];
  entrypoint?: string;
  notebook_path?: string;
  working_dir?: string;
  environment_keys?: string[];
  dataset_versions?: ResearchDatasetVersion[];
  dependency_fingerprint?: Record<string, unknown>;
  input_hashes?: Record<string, string>;
  output_hashes?: Record<string, string>;
};

export type ResearchOverview = {
  counts: {
    projects: number;
    workflows: number;
    active_workflows: number;
    notes: number;
    claims: number;
    evidences: number;
    experiments: number;
    artifacts: number;
  };
  active_workflows: ResearchWorkflowItem[];
  projects: ResearchProjectItem[];
};

export type ResearchProjectBlockerTaskItem = {
  task_id: string;
  title: string;
  status: string;
  assignee?: string;
  action_type?: string;
  target?: string;
  suggested_tool?: string;
  can_dispatch?: boolean;
  can_execute?: boolean;
  dispatch_count?: number;
  execution_count?: number;
  last_dispatch_summary?: string;
  last_execution_summary?: string;
};

export type ResearchProjectBlockerItem = {
  kind: string;
  workflow_id?: string;
  experiment_id?: string;
  blocked_task_id?: string;
  blocked_task_title?: string;
  title: string;
  summary: string;
  status: string;
  stage?: string;
  open_remediation_tasks?: number;
  ready_for_retry?: boolean;
  contract_failure_count?: number;
  has_dispatchable_tasks?: boolean;
  has_executable_tasks?: boolean;
  updated_at?: string;
  actionable_tasks?: ResearchProjectBlockerTaskItem[];
};

export type ResearchDashboard = {
  project: ResearchProjectItem;
  counts: Record<string, number>;
  health: {
    workflows: Record<string, number>;
    experiments: Record<string, number>;
    remediation: Record<string, number>;
  };
  active_workflows: ResearchWorkflowItem[];
  recent_notes: Array<{ id: string; title: string; note_type?: string }>;
  recent_experiments: Array<{ id: string; name: string; status: string }>;
  recent_claims: ResearchClaimItem[];
  recent_drafts: Array<{ id: string; title: string; artifact_type: string }>;
  recent_blockers: ResearchProjectBlockerItem[];
};

export type ResearchClosureReport = {
  project: ResearchProjectItem;
  readiness: {
    overall_status: string;
    completion_score: number;
    ready_for_writing: boolean;
    ready_for_submission: boolean;
    ready_for_reproducibility: boolean;
    blocking_issue_count: number;
    warning_issue_count: number;
  };
  summary: Record<string, number>;
  workflow_status: Record<string, number>;
  artifact_coverage: {
    by_type: Record<string, number>;
    missing_expected_types: string[];
  };
  claim_matrix: Array<{
    claim_id: string;
    workflow_id?: string;
    text: string;
    status: string;
    confidence?: number | null;
    evidence_count: number;
    evidence_types: string[];
    experiment_count: number;
    completed_experiment_count: number;
    artifact_count: number;
    artifact_types: string[];
    ready_for_writing: boolean;
    ready_for_submission: boolean;
    gaps: string[];
    updated_at?: string;
  }>;
  experiment_matrix: Array<{
    experiment_id: string;
    workflow_id?: string;
    name: string;
    status: string;
    claim_count: number;
    artifact_count: number;
    contract_enabled: boolean;
    contract_passed: boolean;
    bundle_state: string;
    bundle_schema?: string;
    reproducibility_ready: boolean;
    missing_metrics: string[];
    missing_outputs: string[];
    missing_artifact_types: string[];
    bundle_missing_sections: string[];
    gaps: string[];
    updated_at?: string;
  }>;
  action_items: ResearchClosureActionItem[];
};

export type ResearchClosureActionItem = {
  severity: string;
  kind: string;
  title: string;
  summary: string;
  closure_key?: string;
  target_type: string;
  target_id: string;
  stage?: string;
  assignee?: string;
  suggested_tool?: string;
  auto_executable?: boolean;
  materializable?: boolean;
  artifact_type?: string;
  workflow_id?: string;
  experiment_id?: string;
  claim_id?: string;
};

export type ResearchClosureMaterializeResult = {
  project?: ResearchProjectItem;
  created_count: number;
  skipped_count: number;
  tasks: ResearchWorkflowTask[];
  skipped?: Array<{
    reason?: string;
    action?: {
      kind?: string;
      title?: string;
      target_id?: string;
    };
    task?: ResearchWorkflowTask;
  }>;
  closure?: ResearchClosureReport;
};

export type ResearchClosureActionExecuteResult = {
  executed: boolean;
  materialized?: boolean;
  reason?: string;
  written_path?: string;
  closure_action?: {
    kind?: string;
    target_id?: string;
    title?: string;
    auto_executable?: boolean;
  };
  artifact?: {
    id: string;
    title: string;
    artifact_type: string;
    path?: string;
  } | null;
  note?: {
    id: string;
    title: string;
    note_type?: string;
  } | null;
  materialize_result?: ResearchClosureMaterializeResult;
  closure?: ResearchClosureReport;
};

export type ResearchClosureActionBatchResult = {
  mode: string;
  requested_count: number;
  executed_count: number;
  materialized_count: number;
  skipped_count: number;
  results: Array<{
    closure_key: string;
    executed: boolean;
    materialized: boolean;
    skipped: boolean;
    reason?: string;
    created_count?: number;
  }>;
  closure?: ResearchClosureReport;
};

export type ResearchProjectPackageResult = {
  project?: ResearchProjectItem;
  closure?: ResearchClosureReport;
  package_dir: string;
  archive_path: string;
  manifest_path: string;
  included_file_count: number;
  missing_file_count: number;
  included_files?: Array<{
    kind?: string;
    id?: string;
    title?: string;
    source_path?: string;
    bundle_path?: string;
  }>;
  missing_files?: Array<{
    kind?: string;
    id?: string;
    title?: string;
    source_path?: string;
  }>;
  artifact?: {
    id: string;
    title: string;
    artifact_type: string;
    path?: string;
  };
  note?: {
    id: string;
    title: string;
    note_type?: string;
  };
};

export type ResearchWorkflowTaskActionResult = {
  workflow?: ResearchWorkflowItem;
  task?: ResearchWorkflowTask & {
    dispatch_count?: number;
    execution_count?: number;
    last_dispatch_summary?: string;
    last_execution_summary?: string;
  };
  skipped?: boolean;
  executed?: boolean;
  reason?: string;
  task_kind?: string;
  delivery?: {
    ok?: boolean;
    error?: string;
  };
};

export type ResearchWorkflowRemediationContext = {
  contract_failures: Array<{
    experiment_id?: string;
    experiment_name?: string;
    summary?: string;
    missing_metrics?: string[];
    missing_outputs?: string[];
    missing_artifact_types?: string[];
  }>;
  remediation_summary?: string;
  remediation_actions?: Array<Record<string, unknown>>;
  blocked_task_id?: string;
  blocked_task_title?: string;
  remediation_tasks: Array<{
    id: string;
    title: string;
    status: string;
    assignee?: string;
    action_type?: string;
    target?: string;
    suggested_tool?: string;
    due_at?: string | null;
    dispatch_count?: number;
    execution_count?: number;
    last_dispatch_summary?: string;
    last_execution_summary?: string;
    can_dispatch?: boolean;
    can_execute?: boolean;
  }>;
  ready_for_retry?: boolean;
  retry_exhausted_count?: number;
  retry_exhausted_tasks?: Array<Record<string, unknown>>;
};

export type ResearchWorkflowRemediationBatchResult = {
  workflow?: ResearchWorkflowItem;
  project?: ResearchProjectItem;
  remediation_context?: ResearchWorkflowRemediationContext;
  results?: ResearchWorkflowTaskActionResult[];
  dispatched_count?: number;
  executed_count?: number;
  skipped?: boolean;
  reason?: string;
};

export type ResearchProjectBlockerBatchResult = {
  project?: ResearchProjectItem;
  dashboard?: ResearchDashboard;
  mode?: string;
  selected_workflow_ids?: string[];
  requested_count?: number;
  matched_count?: number;
  applied_count?: number;
  workflow_results?: Array<
    | ResearchWorkflowRemediationBatchResult
    | ResearchWorkflowExecutionResult
  >;
  dispatched_count?: number;
  executed_count?: number;
  resumed_count?: number;
  skipped?: boolean;
  reason?: string;
};

export type ResearchClaimGraph = {
  project?: ResearchProjectItem | null;
  workflow?: ResearchWorkflowItem | null;
  claim: ResearchClaimItem;
  evidences: ResearchEvidenceItem[];
  notes: Array<{ id: string; title: string; content?: string }>;
  artifacts: Array<{ id: string; title: string; artifact_type: string; path?: string }>;
  experiments: Array<{ id: string; name: string; status: string; metrics?: Record<string, unknown> }>;
};

export type ResearchWorkflowExecutionResult = {
  workflow: ResearchWorkflowItem;
  project?: ResearchProjectItem;
  note?: {
    id: string;
    title: string;
    note_type?: string;
    content?: string;
  };
  response?: string;
  mutated_by_agent: boolean;
  agent_id: string;
  session_id: string;
  execution_id: string;
  skipped?: boolean;
  reason?: string;
};
