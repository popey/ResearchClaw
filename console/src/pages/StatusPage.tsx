import { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Bot,
  Wrench,
  Clock,
  RefreshCw,
  Zap,
  Puzzle,
  Heart,
} from "lucide-react";
import {
  getHealth,
  getStatus,
  getControlStatus,
  listActiveSkills,
  getHeartbeat,
} from "../api";
import { PageHeader, StatCard } from "../components/ui";

export default function StatusPage() {
  const [health, setHealth] = useState<string>("unknown");
  const [agentName, setAgentName] = useState<string>("-");
  const [running, setRunning] = useState<boolean>(false);
  const [toolCount, setToolCount] = useState<number>(0);
  const [activeSkills, setActiveSkills] = useState<number>(0);
  const [heartbeatEnabled, setHeartbeatEnabled] = useState<boolean>(false);
  const [control, setControl] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function onRefreshStatus() {
    setLoading(true);
    try {
      const h = await getHealth();
      setHealth(h.status);
    } catch {
      setHealth("down");
    }

    try {
      const s = await getStatus();
      setAgentName(s.agent_name);
      setRunning(s.running);
      setToolCount(s.tool_count);
    } catch {
      setAgentName("error");
    }

    try {
      setControl(await getControlStatus());
    } catch {
      setControl(null);
    }

    try {
      const active = await listActiveSkills();
      setActiveSkills(active.length);
    } catch {
      setActiveSkills(0);
    }

    try {
      const hb = await getHeartbeat();
      setHeartbeatEnabled(Boolean(hb?.enabled));
    } catch {
      setHeartbeatEnabled(false);
    }
    setLoading(false);
  }

  useEffect(() => {
    void onRefreshStatus();
  }, []);

  return (
    <div className="panel">
      <PageHeader
        title="系统状态"
        description="查看 ResearchClaw 服务的运行状态"
        actions={
          <button onClick={onRefreshStatus} disabled={loading}>
            <RefreshCw size={15} className={loading ? "spinner" : ""} />
            刷新状态
          </button>
        }
      />

      <div className="stat-row">
        <StatCard
          label="API 健康"
          value={health === "ok" ? "正常" : health}
          icon={
            health === "ok" ? <CheckCircle2 size={20} /> : <XCircle size={20} />
          }
          variant={health === "ok" ? "success" : "danger"}
        />
        <StatCard
          label="Agent"
          value={agentName}
          icon={<Bot size={20} />}
          variant="brand"
        />
        <StatCard
          label="运行状态"
          value={running ? "运行中" : "已停止"}
          icon={<Activity size={20} />}
          variant={running ? "success" : "warning"}
        />
        <StatCard
          label="可用工具"
          value={toolCount}
          icon={<Wrench size={20} />}
          variant="info"
        />
        <StatCard
          label="激活技能"
          value={activeSkills}
          icon={<Puzzle size={20} />}
          variant="warning"
        />
        <StatCard
          label="Heartbeat"
          value={heartbeatEnabled ? "启用" : "关闭"}
          icon={<Heart size={20} />}
          variant={heartbeatEnabled ? "success" : "danger"}
        />
      </div>

      {control && (
        <div className="stat-row">
          <StatCard
            label="运行模式"
            value={control.mode || "-"}
            icon={<Zap size={20} />}
            variant="brand"
          />
          <StatCard
            label="运行时长"
            value={
              control.uptime_seconds
                ? `${Math.round(control.uptime_seconds)}s`
                : "-"
            }
            icon={<Clock size={20} />}
            variant="info"
          />
          <StatCard
            label="定时任务"
            value={
              Array.isArray(control.cron_jobs) ? control.cron_jobs.length : 0
            }
            icon={<RefreshCw size={20} />}
            variant="warning"
          />
        </div>
      )}
    </div>
  );
}
