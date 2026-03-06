import { useEffect, useState } from "react";
import { Puzzle, RefreshCw } from "lucide-react";
import {
  listSkills,
  listActiveSkills,
  enableSkill,
  disableSkill,
} from "../api";
import type { SkillItem } from "../types";
import { PageHeader, EmptyState, Badge, Toggle } from "../components/ui";

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [active, setActive] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setSkills(await listSkills());
    setActive(await listActiveSkills());
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, []);

  async function onToggle(skillName: string, isActive: boolean) {
    if (isActive) {
      await disableSkill(skillName);
    } else {
      await enableSkill(skillName);
    }
    await onLoad();
  }

  return (
    <div className="panel">
      <PageHeader
        title="技能管理"
        description="启用或禁用 Agent 技能（同时影响聊天与 task_type=agent 的定时任务）"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新技能
          </button>
        }
      />

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

      <div className="card-list animate-list">
        {skills.map((skill: SkillItem, idx: number) => {
          const skillName = skill.name || `skill-${idx}`;
          const isActive = active.includes(skillName);
          return (
            <div key={skillName} className="data-row">
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
                </div>
                {skill.description && (
                  <div className="data-row-meta">{skill.description}</div>
                )}
              </div>
              <div className="data-row-actions">
                <Toggle
                  checked={isActive}
                  onChange={() => onToggle(skillName, isActive)}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
