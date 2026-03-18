import { useEffect, useMemo, useState } from "react";
import { Puzzle, RefreshCw } from "lucide-react";
import {
  listSkills,
  listActiveSkills,
  enableSkill,
  disableSkill,
} from "../api";
import type { SkillItem } from "../types";
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
    setNotice(`已${isActive ? "禁用" : "启用"}技能 ${skillName}`);
    await onLoad();
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
