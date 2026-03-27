import { useEffect, useMemo, useState } from "react";
import { Github, Puzzle, RefreshCw } from "lucide-react";
import {
  importSkillsFromGitHubRepo,
  listSkills,
  listActiveSkills,
  enableSkill,
  disableSkill,
} from "../api";
import type { SkillItem, SkillRepositoryImportResult } from "../types";
import {
  PageHeader,
  EmptyState,
  Badge,
  Toggle,
  MetricPill,
  NoticeBanner,
  SurfaceCard,
} from "../components/ui";

function getSkillId(skill: SkillItem, idx: number): string {
  return skill.id || skill.name || `skill-${idx}`;
}

function getSkillName(skill: SkillItem, idx: number): string {
  return skill.name || skill.id || `skill-${idx}`;
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [repoRef, setRepoRef] = useState("");
  const [rewriteWithModel, setRewriteWithModel] = useState(true);
  const [importingRepo, setImportingRepo] = useState(false);
  const [lastImport, setLastImport] = useState<SkillRepositoryImportResult | null>(
    null,
  );

  async function onLoad() {
    const [skillRows, activeRows] = await Promise.all([
      listSkills(),
      listActiveSkills(),
    ]);
    setSkills(skillRows);
    setActive(activeRows);
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, []);

  async function onToggle(skillName: string, isActive: boolean) {
    const action = isActive ? disableSkill : enableSkill;
    await action(skillName);
    setError("");
    setNotice(`已${isActive ? "禁用" : "启用"}技能 ${skillName}`);
    await onLoad();
  }

  async function onImportRepo() {
    const nextRepoUrl = repoUrl.trim();
    if (!nextRepoUrl) {
      setError("请先输入 GitHub 仓库地址");
      return;
    }

    setImportingRepo(true);
    setError("");
    setNotice("");
    try {
      const result = await importSkillsFromGitHubRepo({
        repoUrl: nextRepoUrl,
        ref: repoRef.trim() || undefined,
        overwrite: true,
        rewriteWithModel,
      });
      setLastImport(result);
      setNotice(
        `已导入 ${result.count} 个技能：${result.imported
          .map((item) => item.name)
          .join("、")}`,
      );
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入 GitHub 技能失败");
    } finally {
      setImportingRepo(false);
    }
  }

  const normalizedQuery = query.trim().toLowerCase();
  const filteredSkills = useMemo(
    () =>
      skills.filter((skill, idx) => {
        const skillId = getSkillId(skill, idx);
        const skillName = getSkillName(skill, idx);
        return `${skillId} ${skillName} ${skill.description || ""} ${
          skill.source || ""
        } ${skill.scope || ""} ${skill.format || ""} ${skill.path || ""}`
          .toLowerCase()
          .includes(normalizedQuery);
      }),
    [normalizedQuery, skills],
  );

  return (
    <div className="panel">
      <PageHeader
        eyebrow="Capability Switches"
        title="技能管理"
        description="启用或禁用 Agent 技能，同时影响聊天和 `task_type=agent` 的定时任务。"
        meta={
          <div className="page-header-meta-row">
            <MetricPill label="技能总数" value={skills.length} />
            <MetricPill label="已启用" value={active.length} />
          </div>
        }
        actions={
          <div className="toolbar-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索技能名称或描述"
            />
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              刷新技能
            </button>
          </div>
        }
      />

      {notice && <NoticeBanner variant="success">{notice}</NoticeBanner>}
      {error && <NoticeBanner variant="danger">{error}</NoticeBanner>}

      {!loaded && skills.length === 0 && (
        <EmptyState
          icon={<Puzzle size={28} />}
          title="加载技能列表"
          description="管理 Agent 可用的技能和能力"
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
        description="支持直接粘贴 GitHub 仓库或 tree/blob 子路径。后端会扫描仓库里的 `SKILL.md`，导入到本地技能目录，并把外部路径尽量改写成 ResearchClaw 可读的 `references/` 或 `scripts/`。"
        actions={
          <button onClick={onImportRepo} disabled={importingRepo}>
            <Github size={15} />
            {importingRepo ? "导入中..." : "导入仓库技能"}
          </button>
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
            <label
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                color: "var(--text-secondary)",
                fontSize: 13,
              }}
            >
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
                  <div key={`${item.name}-${item.skill_root || "root"}`} className="data-row compact">
                    <div className="data-row-info">
                      <div className="data-row-title">
                        {item.name}
                        <Badge variant={item.enabled ? "success" : "neutral"}>
                          {item.enabled ? "已启用" : "已导入"}
                        </Badge>
                        {rewrite?.model_used && (
                          <Badge variant="info">
                            模型修复{rewrite.model_name ? ` · ${rewrite.model_name}` : ""}
                          </Badge>
                        )}
                      </div>
                      <div className="data-row-meta">
                        <code>{item.source_url}</code>
                      </div>
                      <div className="data-row-meta">
                        镜像文件 {rewrite?.mirrored_files ?? 0} · 路径替换 {rewrite?.path_updates ?? 0}
                      </div>
                      {Array.isArray(rewrite?.diagnostics) &&
                        rewrite!.diagnostics!.length > 0 && (
                          <div className="data-row-meta">
                            诊断: {rewrite!.diagnostics!.join("；")}
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
        title="技能开关"
        description="建议只启用你当前需要的能力，避免让 Agent 在低价值技能上分散注意力。"
      >
        <div className="card-list animate-list">
          {filteredSkills.length === 0 && (
            <div className="empty-inline">当前筛选条件下没有匹配技能</div>
          )}
          {filteredSkills.map((skill: SkillItem, idx: number) => {
            const skillId = getSkillId(skill, idx);
            const skillName = getSkillName(skill, idx);
            const isActive = active.includes(skillId);
            const diagnostics = Array.isArray(skill.diagnostics)
              ? skill.diagnostics
              : [];
            return (
              <div key={skillId} className="data-row">
                <div className="data-row-info">
                  <div className="data-row-title">
                    <Puzzle
                      size={14}
                      style={{ marginRight: 6, verticalAlign: "middle" }}
                    />
                    {skillName}
                    {isActive ? (
                      <Badge variant="success">已启用</Badge>
                    ) : (
                      <Badge variant="neutral">已禁用</Badge>
                    )}
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
                  </div>
                  {skill.description && (
                    <div className="data-row-meta">{skill.description}</div>
                  )}
                  <div className="data-row-meta">
                    <code>ID: {skillId}</code>
                    {skill.scope ? ` · scope: ${skill.scope}` : ""}
                  </div>
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
                </div>
                <div className="data-row-actions">
                  <Toggle
                    checked={isActive}
                    onChange={() => onToggle(skillId, isActive)}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </SurfaceCard>
    </div>
  );
}
