import { useEffect, useMemo, useState } from "react";
import { Github, KeyRound, Puzzle, RefreshCw, Save, Trash2 } from "lucide-react";
import {
  batchDeleteSkills,
  deleteSkill,
  disableSkill,
  enableSkill,
  listEnvVars,
  listActiveSkills,
  listSkills,
  saveEnvVars,
  streamImportSkillsFromGitHubRepo,
} from "../api";
import type {
  EnvItem,
  ImportedSkillItem,
  SkillEnvRequirement,
  SkillImportProgressEvent,
  SkillItem,
  SkillRepositoryImportResult,
} from "../types";
import {
  Badge,
  DetailModal,
  EmptyState,
  MetricPill,
  NoticeBanner,
  PageHeader,
  SurfaceCard,
  Toggle,
} from "../components/ui";

function getSkillId(skill: SkillItem, idx: number): string {
  return skill.id || skill.name || `skill-${idx}`;
}

function getSkillName(skill: SkillItem, idx: number): string {
  return skill.name || skill.id || `skill-${idx}`;
}

function getDeleteVerb(skill: SkillItem): string {
  return skill.source === "customized" ? "删除" : "隐藏";
}

function normalizeEnvRequirements(skill: SkillItem): SkillEnvRequirement[] {
  const raw = skill.requires?.env;
  if (!Array.isArray(raw)) return [];

  const out: SkillEnvRequirement[] = [];
  for (const item of raw) {
    if (typeof item === "string" && item.trim()) {
      out.push({ name: item.trim() });
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const name = String((item as SkillEnvRequirement).name || "").trim();
    if (!name) continue;
    out.push({
      name,
      required:
        typeof (item as SkillEnvRequirement).required === "boolean"
          ? Boolean((item as SkillEnvRequirement).required)
          : undefined,
      secret:
        typeof (item as SkillEnvRequirement).secret === "boolean"
          ? Boolean((item as SkillEnvRequirement).secret)
          : undefined,
      description:
        typeof (item as SkillEnvRequirement).description === "string"
          ? String((item as SkillEnvRequirement).description)
          : undefined,
      default:
        typeof (item as SkillEnvRequirement).default === "string"
          ? String((item as SkillEnvRequirement).default)
          : undefined,
    });
  }
  return out;
}

function toEnvMap(envs: EnvItem[]): Record<string, string> {
  return envs.reduce<Record<string, string>>((acc, item) => {
    acc[item.key] = item.value;
    return acc;
  }, {});
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [envMap, setEnvMap] = useState<Record<string, string>>({});
  const [envDrafts, setEnvDrafts] = useState<Record<string, string>>({});
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [repoRef, setRepoRef] = useState("");
  const [rewriteWithModel, setRewriteWithModel] = useState(true);
  const [importingRepo, setImportingRepo] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importController, setImportController] =
    useState<AbortController | null>(null);
  const [importStatus, setImportStatus] = useState<
    "idle" | "running" | "success" | "error" | "cancelled"
  >("idle");
  const [importCurrentMessage, setImportCurrentMessage] = useState("");
  const [importDiscoveredRoots, setImportDiscoveredRoots] = useState<string[]>(
    [],
  );
  const [importImportedItems, setImportImportedItems] = useState<
    ImportedSkillItem[]
  >([]);
  const [importLogEntries, setImportLogEntries] = useState<
    Array<{ level: "info" | "warning" | "success" | "danger"; text: string }>
  >([]);
  const [importProgress, setImportProgress] = useState({
    current: 0,
    total: 0,
  });
  const [selectedEnvBySkillId, setSelectedEnvBySkillId] = useState<
    Record<string, string>
  >({});
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
  const [busySkillId, setBusySkillId] = useState("");
  const [savingEnvSkillId, setSavingEnvSkillId] = useState("");
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [lastImport, setLastImport] =
    useState<SkillRepositoryImportResult | null>(null);

  async function onLoad() {
    const [skillRows, activeRows, envRows] = await Promise.all([
      listSkills(),
      listActiveSkills(),
      listEnvVars(),
    ]);
    setSkills(skillRows);
    setActive(activeRows);
    const nextEnvMap = toEnvMap(envRows);
    setEnvMap(nextEnvMap);
    setEnvDrafts(nextEnvMap);
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, []);

  useEffect(() => {
    const validIds = new Set(skills.map((skill, idx) => getSkillId(skill, idx)));
    setSelectedSkillIds((prev) => prev.filter((id) => validIds.has(id)));
  }, [skills]);

  useEffect(() => {
    setSelectedEnvBySkillId((prev) => {
      const next: Record<string, string> = {};
      for (const [idx, skill] of skills.entries()) {
        const skillId = getSkillId(skill, idx);
        const envOptions = normalizeEnvRequirements(skill)
          .map((item) => String(item.name || "").trim())
          .filter(Boolean);
        if (envOptions.length === 0) continue;
        const prevValue = prev[skillId];
        next[skillId] = envOptions.includes(prevValue)
          ? prevValue
          : envOptions[0];
      }
      return next;
    });
  }, [skills]);

  function pushImportLog(
    level: "info" | "warning" | "success" | "danger",
    text: string,
  ) {
    setImportLogEntries((prev) => [...prev, { level, text }]);
  }

  function resetImportModalState() {
    setImportStatus("idle");
    setImportCurrentMessage("");
    setImportDiscoveredRoots([]);
    setImportImportedItems([]);
    setImportLogEntries([]);
    setImportProgress({ current: 0, total: 0 });
  }

  async function onToggle(skillName: string, isActive: boolean) {
    const action = isActive ? disableSkill : enableSkill;
    setBusySkillId(skillName);
    setError("");
    setNotice("");
    try {
      await action(skillName);
      setNotice(`已${isActive ? "禁用" : "启用"}技能 ${skillName}`);
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新技能状态失败");
    } finally {
      setBusySkillId("");
    }
  }

  async function onDelete(skill: SkillItem, idx: number) {
    const skillId = getSkillId(skill, idx);
    const skillName = getSkillName(skill, idx);
    const deleteVerb = getDeleteVerb(skill);
    const deleteHint =
      deleteVerb === "删除"
        ? "这会移除本地导入的 skill 目录。"
        : "这不会删除仓库里的源文件，只会从当前 ResearchClaw 工作区隐藏并停用。";
    if (!window.confirm(`确认${deleteVerb}技能 ${skillName}？\n\n${deleteHint}`)) {
      return;
    }

    setBusySkillId(skillId);
    setError("");
    setNotice("");
    try {
      const result = await deleteSkill(skillId);
      setSelectedSkillIds((prev) => prev.filter((id) => id !== skillId));
      setNotice(
        result.action === "hidden"
          ? `已隐藏技能 ${result.skill}`
          : `已删除技能 ${result.skill}`,
      );
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除技能失败");
    } finally {
      setBusySkillId("");
    }
  }

  function toggleSkillSelection(skillId: string) {
    setSelectedSkillIds((prev) =>
      prev.includes(skillId)
        ? prev.filter((item) => item !== skillId)
        : [...prev, skillId],
    );
  }

  async function onImportRepo() {
    const nextRepoUrl = repoUrl.trim();
    if (!nextRepoUrl) {
      setError("请先输入 GitHub 仓库地址");
      return;
    }

    setError("");
    setNotice("");
    resetImportModalState();
    setImportModalOpen(true);
    setImportingRepo(true);
    setImportStatus("running");
    setImportCurrentMessage("准备连接后端导入流...");

    const controller = streamImportSkillsFromGitHubRepo(
      {
        repoUrl: nextRepoUrl,
        ref: repoRef.trim() || undefined,
        overwrite: true,
        rewriteWithModel,
      },
      (event: SkillImportProgressEvent) => {
        switch (event.type) {
          case "start":
          case "stage":
            if (event.message) {
              setImportCurrentMessage(event.message);
              pushImportLog("info", event.message);
            }
            break;
          case "discovered":
            setImportDiscoveredRoots(
              Array.isArray(event.roots) ? event.roots : [],
            );
            if (typeof event.count === "number") {
              setImportProgress({ current: 0, total: event.count });
            }
            if (event.message) {
              setImportCurrentMessage(event.message);
              pushImportLog("info", event.message);
            }
            break;
          case "skill_start":
            setImportProgress((prev) => ({
              current:
                typeof event.index === "number" ? event.index - 1 : prev.current,
              total:
                typeof event.total === "number" && event.total > 0
                  ? event.total
                  : prev.total,
            }));
            if (event.message) {
              setImportCurrentMessage(event.message);
              pushImportLog("info", event.message);
            }
            break;
          case "skill_done":
            if (event.skill) {
              setImportImportedItems((prev) => [
                ...prev,
                event.skill as ImportedSkillItem,
              ]);
            }
            setImportProgress((prev) => ({
              current:
                typeof event.index === "number" ? event.index : prev.current + 1,
              total:
                typeof event.total === "number" && event.total > 0
                  ? event.total
                  : prev.total,
            }));
            if (event.message) {
              setImportCurrentMessage(event.message);
              pushImportLog("success", event.message);
            }
            break;
          case "warning":
            if (event.message) {
              setImportCurrentMessage(event.message);
              pushImportLog("warning", event.message);
            }
            break;
          case "done":
            setImportController(null);
            setImportingRepo(false);
            setImportStatus("success");
            if (event.result) {
              setLastImport(event.result);
              setImportImportedItems(event.result.imported || []);
              setImportProgress({
                current:
                  event.result.count || event.result.imported.length || 0,
                total: event.result.count || event.result.imported.length || 0,
              });
              setNotice(
                `已导入 ${event.result.count} 个技能：${event.result.imported
                  .map((item) => item.name)
                  .join("、")}`,
              );
              void onLoad();
            }
            if (event.message) {
              setImportCurrentMessage(event.message);
              pushImportLog("success", event.message);
            }
            break;
          case "error": {
            const message = event.message || "导入 GitHub 技能失败";
            setImportController(null);
            setImportingRepo(false);
            setImportStatus("error");
            setImportCurrentMessage(message);
            setError(message);
            pushImportLog("danger", message);
            break;
          }
          default:
            break;
        }
      },
    );
    setImportController(controller);
  }

  function closeImportModal() {
    setImportModalOpen(false);
  }

  function cancelImportRepo() {
    importController?.abort();
    setImportController(null);
    setImportingRepo(false);
    setImportStatus("cancelled");
    setImportCurrentMessage("导入已取消");
    pushImportLog("warning", "导入已取消");
  }

  async function onSaveSkillEnv(
    skillId: string,
    skillName: string,
    requirements: SkillEnvRequirement[],
  ) {
    const requiredKeys = requirements
      .filter((item) => item.required)
      .map((item) => String(item.name || "").trim())
      .filter(Boolean);
    const missingKeys = requiredKeys.filter(
      (key) => !(envDrafts[key] || "").trim(),
    );
    if (missingKeys.length > 0) {
      setError(`请先填写必需环境变量：${missingKeys.join("、")}`);
      setNotice("");
      return;
    }

    const nextEnvMap = { ...envMap };
    const touchedKeys = requirements
      .map((item) => String(item.name || "").trim())
      .filter(Boolean);

    for (const key of touchedKeys) {
      const nextValue = envDrafts[key] ?? "";
      if (nextValue.trim()) {
        nextEnvMap[key] = nextValue;
      } else {
        delete nextEnvMap[key];
      }
    }

    setSavingEnvSkillId(skillId);
    setError("");
    setNotice("");
    try {
      await saveEnvVars(nextEnvMap);
      setEnvMap(nextEnvMap);
      setNotice(
        `已更新 ${skillName} 的环境变量：${touchedKeys.join("、")}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存环境变量失败");
    } finally {
      setSavingEnvSkillId("");
    }
  }

  const sourceOptions = useMemo(() => {
    const values = skills
      .map((skill) => String(skill.source || "").trim())
      .filter(Boolean);
    return Array.from(new Set(values)).sort();
  }, [skills]);

  const enabledCount = useMemo(
    () =>
      skills.filter((skill, idx) =>
        active.includes(getSkillId(skill, idx)),
      ).length,
    [active, skills],
  );

  const customizedCount = useMemo(
    () => skills.filter((skill) => skill.source === "customized").length,
    [skills],
  );

  const skillsWithEnvCount = useMemo(
    () =>
      skills.filter((skill) => normalizeEnvRequirements(skill).length > 0)
        .length,
    [skills],
  );

  const filteredSkills = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return skills
      .filter((skill, idx) => {
        const skillId = getSkillId(skill, idx);
        const skillName = getSkillName(skill, idx);
        const isActive = active.includes(skillId);
        const triggerText = Array.isArray(skill.triggers)
          ? skill.triggers.join(" ")
          : "";
        const matchesQuery = `${skillId} ${skillName} ${
          skill.description || ""
        } ${skill.source || ""} ${skill.scope || ""} ${skill.format || ""} ${
          skill.path || ""
        } ${triggerText}`
          .toLowerCase()
          .includes(normalizedQuery);
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "enabled" && isActive) ||
          (statusFilter === "disabled" && !isActive);
        const matchesSource =
          sourceFilter === "all" || (skill.source || "") === sourceFilter;
        return matchesQuery && matchesStatus && matchesSource;
      })
      .sort((a, b) => {
        const aId = getSkillId(a, 0);
        const bId = getSkillId(b, 0);
        const aActive = active.includes(aId);
        const bActive = active.includes(bId);
        if (aActive !== bActive) return aActive ? -1 : 1;
        return getSkillName(a, 0).localeCompare(getSkillName(b, 0));
      });
  }, [active, query, skills, sourceFilter, statusFilter]);

  const selectedSkills = useMemo(
    () =>
      skills.filter((skill, idx) =>
        selectedSkillIds.includes(getSkillId(skill, idx)),
      ),
    [selectedSkillIds, skills],
  );

  const visibleSkillIds = useMemo(
    () => filteredSkills.map((skill, idx) => getSkillId(skill, idx)),
    [filteredSkills],
  );

  const selectedVisibleSkillCount = useMemo(
    () => visibleSkillIds.filter((id) => selectedSkillIds.includes(id)).length,
    [selectedSkillIds, visibleSkillIds],
  );

  const canToggleImportModal =
    importingRepo ||
    importStatus !== "idle" ||
    importLogEntries.length > 0 ||
    importImportedItems.length > 0 ||
    lastImport !== null;

  const allVisibleSkillsSelected =
    visibleSkillIds.length > 0 &&
    selectedVisibleSkillCount === visibleSkillIds.length;

  function toggleVisibleSkillSelection() {
    setSelectedSkillIds((prev) => {
      if (allVisibleSkillsSelected) {
        return prev.filter((id) => !visibleSkillIds.includes(id));
      }
      const next = new Set(prev);
      for (const skillId of visibleSkillIds) {
        next.add(skillId);
      }
      return Array.from(next);
    });
  }

  async function onBatchDeleteSelectedSkills() {
    if (selectedSkills.length === 0) return;
    const deleteCount = selectedSkills.filter(
      (skill) => skill.source === "customized",
    ).length;
    const hideCount = selectedSkills.length - deleteCount;
    const hintParts = [];
    if (deleteCount > 0) hintParts.push(`${deleteCount} 个将真正删除`);
    if (hideCount > 0) hintParts.push(`${hideCount} 个将隐藏`);
    if (
      !window.confirm(
        `确认批量处理 ${selectedSkills.length} 个技能吗？\n\n${hintParts.join("；")}`,
      )
    ) {
      return;
    }

    setBatchDeleting(true);
    setError("");
    setNotice("");
    try {
      const result = await batchDeleteSkills(selectedSkillIds);
      setSelectedSkillIds([]);
      setNotice(
        result.not_found?.length
          ? `已处理 ${result.deleted_count} 个技能，${result.not_found.length} 个未找到。`
          : `已处理 ${result.deleted_count} 个技能。`,
      );
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量删除技能失败");
    } finally {
      setBatchDeleting(false);
    }
  }

  return (
    <div className="panel">
      <PageHeader
        eyebrow="Capability Catalog"
        title="技能管理"
        description="统一查看、启用、导入、删除或隐藏所有 Agent 技能。删除自定义 skill 会移除本地目录；删除内置或项目级 skill 会在当前工作区隐藏。"
        meta={
          <div className="page-header-meta-row">
            <MetricPill label="技能总数" value={skills.length} />
            <MetricPill label="已启用" value={enabledCount} />
            <MetricPill label="自定义/导入" value={customizedCount} />
            <MetricPill label="需要配置" value={skillsWithEnvCount} />
            <MetricPill label="当前显示" value={filteredSkills.length} />
          </div>
        }
        actions={
          <div className="toolbar-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索技能名称、描述、触发词"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">全部状态</option>
              <option value="enabled">仅已启用</option>
              <option value="disabled">仅未启用</option>
            </select>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="all">全部来源</option>
              {sourceOptions.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </select>
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              刷新技能
            </button>
          </div>
        }
      />

      {notice && <NoticeBanner variant="success">{notice}</NoticeBanner>}
      {error && <NoticeBanner variant="danger">{error}</NoticeBanner>}

      {selectedSkillIds.length > 0 && (
        <NoticeBanner variant="warning">
          已选择 {selectedSkillIds.length} 个技能。批量操作会沿用单个 skill 的删除语义：自定义 skill 删除，内置或项目级 skill 隐藏。
        </NoticeBanner>
      )}

      {!loaded && skills.length === 0 && (
        <EmptyState
          icon={<Puzzle size={28} />}
          title="加载技能列表"
          description="查看当前工作区、项目和内置技能"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      <SurfaceCard
        title="从 GitHub 仓库导入技能"
        description="支持直接粘贴 GitHub 仓库或 tree/blob 子路径。后端会扫描 `SKILL.md`，自动导入到本地技能目录，并尽量把外部路径改写成 ResearchClaw 可读的 `references/` 或 `scripts/`。"
        actions={
          <div className="toolbar-row">
            {canToggleImportModal && (
              <button
                type="button"
                onClick={() => setImportModalOpen((prev) => !prev)}
              >
                {importModalOpen ? "关闭导入弹窗" : "打开导入弹窗"}
              </button>
            )}
            <button onClick={onImportRepo} disabled={importingRepo}>
              <Github size={15} />
              {importingRepo ? "导入中..." : "导入仓库技能"}
            </button>
          </div>
        }
      >
        <div className="form-stack">
          <input
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/Research-Equality/RE-literature-discovery"
          />
          <div className="toolbar-row">
            <input
              value={repoRef}
              onChange={(e) => setRepoRef(e.target.value)}
              placeholder="可选：分支 / tag / commit"
            />
            <label className="toolbar-inline-label">
              <input
                type="checkbox"
                checked={rewriteWithModel}
                onChange={(e) => setRewriteWithModel(e.target.checked)}
              />
              用当前已配置模型辅助修正路径引用
            </label>
          </div>

          {lastImport && (
            <div className="card-list">
              {lastImport.imported.map((item) => {
                const rewrite = item.rewrite;
                return (
                  <div
                    key={`${item.name}-${item.skill_root || "root"}`}
                    className="data-row compact"
                  >
                    <div className="data-row-info">
                      <div className="data-row-title">
                        {item.name}
                        <Badge variant={item.enabled ? "success" : "neutral"}>
                          {item.enabled ? "已启用" : "已导入"}
                        </Badge>
                        {rewrite?.model_used && (
                          <Badge variant="info">
                            模型修复
                            {rewrite.model_name
                              ? ` · ${rewrite.model_name}`
                              : ""}
                          </Badge>
                        )}
                      </div>
                      <div className="data-row-meta">
                        <code>{item.source_url}</code>
                      </div>
                      <div className="data-row-meta">
                        镜像文件 {rewrite?.mirrored_files ?? 0} · 路径替换{" "}
                        {rewrite?.path_updates ?? 0}
                      </div>
                      {Array.isArray(rewrite?.diagnostics) &&
                        rewrite.diagnostics.length > 0 && (
                          <div className="data-row-meta">
                            诊断: {rewrite.diagnostics.join("；")}
                          </div>
                        )}
                    </div>
                  </div>
                );
              })}
              {Array.isArray(lastImport.diagnostics) &&
                lastImport.diagnostics.length > 0 && (
                  <div className="data-row compact">
                    <div className="data-row-info">
                      <div className="data-row-title">未导入项</div>
                      <div className="data-row-meta">
                        {lastImport.diagnostics.join("；")}
                      </div>
                    </div>
                  </div>
                )}
            </div>
          )}
        </div>
      </SurfaceCard>

      <SurfaceCard
        title="Skill API 配置"
        description="导入的 skill 如果在 `SKILL.md` frontmatter 里声明了 `requires.env`，会自动出现在技能卡片里。这里保存的值会写入全局环境变量，skill 运行时直接读取。"
        actions={
          <button
            type="button"
            onClick={() => {
              window.location.href = "/environments";
            }}
          >
            <KeyRound size={15} />
            打开环境变量页
          </button>
        }
      >
        <div className="data-row compact">
          <div className="data-row-info">
            <div className="data-row-title">当前配置方式</div>
            <div className="data-row-meta">
              每个 skill 的 API key 最终都会保存到全局环境变量存储里，而不是单独散落在 skill 目录中。
            </div>
            <div className="data-row-meta">
              例如 `citation-management` 会读取 `S2_API_KEY`；保存后无需重新导入 skill。
            </div>
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard
        title="技能目录"
        description="直接管理所有技能。自定义/导入技能可以彻底删除，内置或项目级技能会在当前工作区隐藏；如果 skill 声明了 API 或环境依赖，也可以直接在这里填写。"
        actions={
          <div className="toolbar-row">
            <button
              type="button"
              onClick={toggleVisibleSkillSelection}
              disabled={visibleSkillIds.length === 0 || batchDeleting}
            >
              {allVisibleSkillsSelected ? "取消选择当前结果" : "选择当前结果"}
            </button>
            <button
              type="button"
              onClick={() => setSelectedSkillIds([])}
              disabled={selectedSkillIds.length === 0 || batchDeleting}
            >
              清空选择
            </button>
            <button
              className="danger"
              type="button"
              onClick={onBatchDeleteSelectedSkills}
              disabled={selectedSkillIds.length === 0 || batchDeleting}
            >
              <Trash2 size={15} />
              {batchDeleting
                ? "批量处理中..."
                : `批量删除 (${selectedSkillIds.length})`}
            </button>
          </div>
        }
      >
        <div className="card-list animate-list">
          {filteredSkills.length === 0 && (
            <div className="empty-inline">当前筛选条件下没有匹配技能</div>
          )}
          {filteredSkills.map((skill, idx) => {
            const skillId = getSkillId(skill, idx);
            const skillName = getSkillName(skill, idx);
            const isActive = active.includes(skillId);
            const diagnostics = Array.isArray(skill.diagnostics)
              ? skill.diagnostics
              : [];
            const triggers = Array.isArray(skill.triggers) ? skill.triggers : [];
            const envRequirements = normalizeEnvRequirements(skill);
            const selectedEnvKey =
              selectedEnvBySkillId[skillId] ||
              String(envRequirements[0]?.name || "").trim();
            const selectedEnvRequirement =
              envRequirements.find(
                (item) =>
                  String(item.name || "").trim() === selectedEnvKey,
              ) || envRequirements[0];
            const activeEnvKey = String(
              selectedEnvRequirement?.name || "",
            ).trim();
            const isActiveEnvConfigured = Boolean(
              String(envMap[activeEnvKey] || "").trim(),
            );
            const missingRequiredEnvCount = envRequirements.filter(
              (item) =>
                item.required && !String(envMap[item.name || ""] || "").trim(),
            ).length;
            const isSelected = selectedSkillIds.includes(skillId);
            const isBusy = batchDeleting || busySkillId === skillId;
            const isSavingEnv = savingEnvSkillId === skillId;

            return (
              <div key={skillId} className="data-row skill-catalog-row">
                <div className="data-row-info">
                  <div className="data-row-title">
                    <Puzzle
                      size={14}
                      style={{ marginRight: 6, verticalAlign: "middle" }}
                    />
                    {skillName}
                    <Badge variant={isActive ? "success" : "neutral"}>
                      {isActive ? "已启用" : "已禁用"}
                    </Badge>
                    {skill.format && (
                      <Badge
                        variant={
                          skill.format === "standard" ? "info" : "warning"
                        }
                      >
                        {skill.format}
                      </Badge>
                    )}
                    {skill.source && (
                      <Badge variant="neutral">{skill.source}</Badge>
                    )}
                    {envRequirements.length > 0 && (
                      <Badge
                        variant={
                          missingRequiredEnvCount > 0 ? "warning" : "info"
                        }
                      >
                        env {envRequirements.length}
                        {missingRequiredEnvCount > 0
                          ? ` · 缺 ${missingRequiredEnvCount}`
                          : " · 已就绪"}
                      </Badge>
                    )}
                  </div>

                  {skill.description && (
                    <div className="data-row-meta">{skill.description}</div>
                  )}

                  <div className="data-row-meta">
                    <code>ID: {skillId}</code>
                    {skill.scope ? ` · scope: ${skill.scope}` : ""}
                  </div>

                  {triggers.length > 0 && (
                    <div className="data-row-meta">
                      触发词:
                      {" " +
                        triggers
                          .slice(0, 6)
                          .map((item) => `#${item}`)
                          .join(" ")}
                    </div>
                  )}

                  {skill.location && (
                    <div className="data-row-meta">
                      <code>{skill.location}</code>
                    </div>
                  )}

                  {diagnostics.length > 0 && (
                    <div className="data-row-meta">
                      诊断: {diagnostics.join(", ")}
                    </div>
                  )}

                  {envRequirements.length > 0 && (
                    <div className="skill-env-editor">
                      <div className="skill-env-editor-head">
                        <div className="data-row-title">
                          <KeyRound
                            size={14}
                            style={{ marginRight: 6, verticalAlign: "middle" }}
                          />
                          ENV 配置
                          <Badge
                            variant={
                              isActiveEnvConfigured ? "success" : "warning"
                            }
                          >
                            {isActiveEnvConfigured ? "已配置" : "未配置"}
                          </Badge>
                          {selectedEnvRequirement?.required && (
                            <Badge variant="warning">必需</Badge>
                          )}
                          {selectedEnvRequirement?.secret && (
                            <Badge variant="neutral">secret</Badge>
                          )}
                        </div>
                      </div>
                      <div className="skill-env-editor-row">
                        <select
                          value={activeEnvKey}
                          disabled={isSavingEnv || isBusy}
                          onChange={(e) =>
                            setSelectedEnvBySkillId((prev) => ({
                              ...prev,
                              [skillId]: e.target.value,
                            }))
                          }
                        >
                          {envRequirements.map((item) => {
                            const envKey = String(item.name || "").trim();
                            return (
                              <option key={envKey} value={envKey}>
                                {envKey}
                              </option>
                            );
                          })}
                        </select>
                        <input
                          type={
                            selectedEnvRequirement?.secret ? "password" : "text"
                          }
                          value={envDrafts[activeEnvKey] ?? ""}
                          onChange={(e) =>
                            setEnvDrafts((prev) => ({
                              ...prev,
                              [activeEnvKey]: e.target.value,
                            }))
                          }
                          placeholder={
                            selectedEnvRequirement?.default
                              ? `默认值: ${selectedEnvRequirement.default}`
                              : `${activeEnvKey}=...`
                          }
                          autoComplete="off"
                          disabled={!activeEnvKey || isSavingEnv || isBusy}
                        />
                        <button
                          disabled={!activeEnvKey || isSavingEnv || isBusy}
                          onClick={() =>
                            onSaveSkillEnv(
                              skillId,
                              skillName,
                              selectedEnvRequirement
                                ? [selectedEnvRequirement]
                                : [],
                            )
                          }
                        >
                          <Save size={15} />
                          {isSavingEnv ? "保存中..." : "保存"}
                        </button>
                      </div>
                      {selectedEnvRequirement?.description && (
                        <div className="data-row-meta skill-env-editor-meta">
                          {selectedEnvRequirement.description}
                        </div>
                      )}
                      <div className="data-row-meta skill-env-editor-meta">
                        留空并保存会移除当前选中的 env。
                      </div>
                    </div>
                  )}
                </div>

                <div className="data-row-actions" style={{ gap: 8 }}>
                  <label
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      color: "var(--text-secondary)",
                      fontSize: 12,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={isBusy}
                      onChange={() => toggleSkillSelection(skillId)}
                    />
                    选择
                  </label>
                  <button disabled={isBusy} onClick={() => onDelete(skill, idx)}>
                    <Trash2 size={15} />
                    {getDeleteVerb(skill)}
                  </button>
                  <Toggle
                    checked={isActive}
                    disabled={isBusy}
                    onChange={() => onToggle(skillId, isActive)}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </SurfaceCard>

      {importModalOpen && (
        <DetailModal title="导入技能" onClose={closeImportModal}>
          <div className="card-list">
            <NoticeBanner
              variant={
                importStatus === "error"
                  ? "danger"
                  : importStatus === "success"
                  ? "success"
                  : importStatus === "cancelled"
                  ? "warning"
                  : "info"
              }
            >
              {importCurrentMessage || "等待导入事件..."}
            </NoticeBanner>

            <div className="page-header-meta-row">
              <MetricPill label="状态" value={importStatus} />
              <MetricPill label="已导入" value={importImportedItems.length} />
              <MetricPill
                label="进度"
                value={
                  importProgress.total > 0
                    ? `${importProgress.current}/${importProgress.total}`
                    : "-"
                }
              />
              <MetricPill
                label="发现 roots"
                value={importDiscoveredRoots.length}
              />
            </div>

            {importDiscoveredRoots.length > 0 && (
              <SurfaceCard
                title="扫描到的 Skill Roots"
                description="后端扫描仓库中包含 SKILL.md 的目录"
              >
                <div className="card-list">
                  {importDiscoveredRoots.map((root) => (
                    <div key={root || "."} className="data-row compact">
                      <div className="data-row-info">
                        <div className="data-row-title">
                          <code>{root || "."}</code>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </SurfaceCard>
            )}

            <SurfaceCard
              title="已加载的 Skills"
              description="每个 skill 完成导入后会立即出现在这里"
            >
              <div className="card-list">
                {importImportedItems.length === 0 && (
                  <div className="empty-inline">还没有导入完成的 skill</div>
                )}
                {importImportedItems.map((item) => (
                  <div
                    key={`${item.name}-${item.skill_root || "root"}`}
                    className="data-row compact"
                  >
                    <div className="data-row-info">
                      <div className="data-row-title">
                        {item.name}
                        <Badge variant={item.enabled ? "success" : "neutral"}>
                          {item.enabled ? "已启用" : "已导入"}
                        </Badge>
                      </div>
                      <div className="data-row-meta">
                        <code>{item.source_url}</code>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </SurfaceCard>

            <SurfaceCard
              title="导入日志"
              description="展示后端返回的阶段、警告和完成状态"
            >
              <div
                className="card-list"
                style={{ maxHeight: 280, overflow: "auto" }}
              >
                {importLogEntries.length === 0 && (
                  <div className="empty-inline">还没有日志</div>
                )}
                {importLogEntries.map((entry, idx) => (
                  <NoticeBanner key={`${entry.text}-${idx}`} variant={entry.level}>
                    {entry.text}
                  </NoticeBanner>
                ))}
              </div>
            </SurfaceCard>

            <div className="toolbar-row">
              {importingRepo ? (
                <button type="button" className="danger" onClick={cancelImportRepo}>
                  <Trash2 size={15} />
                  取消导入
                </button>
              ) : (
                <button type="button" onClick={closeImportModal}>
                  关闭
                </button>
              )}
            </div>
          </div>
        </DetailModal>
      )}
    </div>
  );
}
