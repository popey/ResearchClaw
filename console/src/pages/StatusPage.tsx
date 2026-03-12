import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Heart,
  MessageSquareMore,
  Puzzle,
  RefreshCw,
  Workflow,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";
import {
  getControlLogs,
  getControlStatus,
  getHealth,
  getHeartbeat,
  getStatus,
  listActiveSkills,
  reloadControlRuntime,
} from "../api";
import {
  MetricPill,
  PageHeader,
  StatCard,
  SurfaceCard,
} from "../components/ui";

type OverviewState = {
  health: string;
  agentName: string;
  running: boolean | null;
  toolCount: number | null;
  activeSkills: number | null;
  heartbeatEnabled: boolean | null;
};

export default function StatusPage() {
  const [overview, setOverview] = useState<OverviewState>({
    health: "unknown",
    agentName: "-",
    running: null,
    toolCount: null,
    activeSkills: null,
    heartbeatEnabled: null,
  });
  const [control, setControl] = useState<any>(null);
  const [logTail, setLogTail] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function onRefreshStatus() {
    setLoading(true);
    const [
      controlResult,
      statusResult,
      healthResult,
      logsResult,
      activeSkillsResult,
      heartbeatResult,
    ] = await Promise.allSettled([
      getControlStatus(),
      getStatus(),
      getHealth(),
      getControlLogs(80),
      listActiveSkills(),
      getHeartbeat(),
    ]);

    const controlData =
      controlResult.status === "fulfilled" ? controlResult.value : null;
    const statusData =
      statusResult.status === "fulfilled" ? statusResult.value : null;
    const runnerAgents = Array.isArray(controlData?.runtime?.runner?.agents)
      ? controlData.runtime.runner.agents
      : [];
    const displayAgent =
      runnerAgents.find((item: any) => item?.default) ||
      runnerAgents.find((item: any) => item?.running) ||
      runnerAgents[0] ||
      null;
    const runningFromControl =
      typeof controlData?.runner_running === "boolean"
        ? controlData.runner_running
        : typeof controlData?.runtime?.runner?.running === "boolean"
        ? controlData.runtime.runner.running
        : null;
    const activeSkillsFromControl = controlData?.runtime?.skills?.active_count;
    const activeSkillsFromApi =
      activeSkillsResult.status === "fulfilled"
        ? activeSkillsResult.value.length
        : null;
    const heartbeatFromControl = controlData?.runtime?.heartbeat || null;
    const heartbeatFromApi =
      heartbeatResult.status === "fulfilled" ? heartbeatResult.value : null;

    setControl(controlData);
    setOverview({
      health:
        healthResult.status === "fulfilled"
          ? healthResult.value.status
          : controlData || statusData
          ? "ok"
          : "down",
      agentName: String(
        controlData?.runtime?.runner?.agent_name ||
          statusData?.agent_name ||
          displayAgent?.id ||
          controlData?.runtime?.runner?.default_agent_id ||
          "-",
      ),
      running:
        typeof runningFromControl === "boolean"
          ? runningFromControl
          : statusData
          ? Boolean(statusData.running)
          : null,
      toolCount:
        statusData?.tool_count != null ||
        controlData?.runtime?.runner?.tool_count != null ||
        displayAgent?.tool_count != null
          ? Number(
              controlData?.runtime?.runner?.tool_count ??
                statusData?.tool_count ??
                displayAgent?.tool_count ??
                0,
            )
          : null,
      activeSkills:
        activeSkillsFromControl != null
          ? Number(activeSkillsFromControl)
          : activeSkillsFromApi,
      heartbeatEnabled:
        typeof heartbeatFromControl?.enabled === "boolean"
          ? Boolean(heartbeatFromControl.enabled)
          : typeof heartbeatFromApi?.enabled === "boolean"
          ? Boolean(heartbeatFromApi.enabled)
          : null,
    });
    setLogTail(
      logsResult.status === "fulfilled"
        ? String(logsResult.value?.content || "")
        : "",
    );
    setLoading(false);
  }

  useEffect(() => {
    void onRefreshStatus();
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void onRefreshStatus();
    }, 10000);

    const handleVisible = () => {
      if (document.visibilityState === "visible") {
        void onRefreshStatus();
      }
    };

    document.addEventListener("visibilitychange", handleVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisible);
    };
  }, []);

  useEffect(() => {
    const shouldRetry =
      overview.health !== "ok" ||
      overview.running === null ||
      overview.toolCount === null ||
      overview.activeSkills === null ||
      overview.heartbeatEnabled === null;

    if (!shouldRetry) {
      return;
    }

    const retry = window.setTimeout(() => {
      void onRefreshStatus();
    }, 2500);

    return () => window.clearTimeout(retry);
  }, [overview]);

  return (
    <div className="panel">
      <PageHeader
        eyebrow="Control Plane"
        title="系统状态"
        description="集中查看服务健康、自动化执行、模型使用和控制面运行态。"
        meta={
          <div className="page-header-meta-row">
            <MetricPill
              label="API"
              value={overview.health === "ok" ? "Healthy" : overview.health}
            />
            <MetricPill
              label="Agent"
              value={
                overview.running === null
                  ? "Unknown"
                  : overview.running
                  ? "Running"
                  : "Stopped"
              }
            />
            <MetricPill
              label="Heartbeat"
              value={
                overview.heartbeatEnabled === null
                  ? "Unknown"
                  : overview.heartbeatEnabled
                  ? "Enabled"
                  : "Off"
              }
            />
          </div>
        }
        actions={
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={async () => {
                setLoading(true);
                try {
                  await reloadControlRuntime();
                  await onRefreshStatus();
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
            >
              <Zap size={15} />
              热重载
            </button>
            <button onClick={onRefreshStatus} disabled={loading}>
              <RefreshCw size={15} className={loading ? "spinner" : ""} />
              刷新状态
            </button>
          </div>
        }
      />

      <SurfaceCard
        title="服务总览"
        description="先确认健康、Agent 状态和能力装载，再下钻到具体链路。"
        className="mb-4"
      >
        <div className="stat-row" data-no-auto-translate>
          <StatCard
            label="API 健康"
            value={overview.health === "ok" ? "正常" : overview.health}
            icon={
              overview.health === "ok" ? (
                <CheckCircle2 size={20} />
              ) : (
                <XCircle size={20} />
              )
            }
            variant={overview.health === "ok" ? "success" : "danger"}
          />
          <StatCard
            label="Agent"
            value={overview.agentName}
            icon={<Bot size={20} />}
            variant="brand"
          />
          <StatCard
            label="运行状态"
            value={
              overview.running === null
                ? "未知"
                : overview.running
                ? "运行中"
                : "已停止"
            }
            icon={<Activity size={20} />}
            variant={
              overview.running === null
                ? "info"
                : overview.running
                ? "success"
                : "warning"
            }
          />
          <StatCard
            label="可用工具"
            value={overview.toolCount ?? "未知"}
            icon={<Wrench size={20} />}
            variant={overview.toolCount === null ? "warning" : "info"}
          />
          <StatCard
            label="激活技能"
            value={overview.activeSkills ?? "未知"}
            icon={<Puzzle size={20} />}
            variant={overview.activeSkills === null ? "info" : "warning"}
          />
          <StatCard
            label="Heartbeat"
            value={
              overview.heartbeatEnabled === null
                ? "未知"
                : overview.heartbeatEnabled
                ? "启用"
                : "关闭"
            }
            icon={<Heart size={20} />}
            variant={
              overview.heartbeatEnabled === null
                ? "warning"
                : overview.heartbeatEnabled
                ? "success"
                : "danger"
            }
          />
        </div>
      </SurfaceCard>

      {control && (
        <>
          <SurfaceCard
            title="运行时与模型"
            description="这里反映 Agent 实例规模、模型请求量和回退链是否在工作。"
            className="mb-4"
          >
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
                  Array.isArray(control.cron_jobs)
                    ? control.cron_jobs.length
                    : 0
                }
                icon={<RefreshCw size={20} />}
                variant="warning"
              />
              <StatCard
                label="Agent 实例"
                value={
                  Array.isArray(control?.runtime?.runner?.agents)
                    ? control.runtime.runner.agents.length
                    : 0
                }
                icon={<Bot size={20} />}
                variant="info"
              />
              <StatCard
                label="模型请求数"
                value={control?.runtime?.runner?.usage?.requests ?? 0}
                icon={<Activity size={20} />}
                variant="brand"
              />
              <StatCard
                label="回退次数"
                value={control?.runtime?.runner?.usage?.fallbacks ?? 0}
                icon={<RefreshCw size={20} />}
                variant="warning"
              />
            </div>
          </SurfaceCard>

          <SurfaceCard
            title="渠道与自动化"
            description="重点关注入口接入量、队列积压和自动化执行结果。"
          >
            <div className="stat-row">
              <StatCard
                label="注册频道"
                value={control?.runtime?.channels?.registered_channels ?? 0}
                icon={<Workflow size={20} />}
                variant="brand"
              />
              <StatCard
                label="通道队列消息"
                value={control?.runtime?.channels?.queued_messages ?? 0}
                icon={<MessageSquareMore size={20} />}
                variant="info"
              />
              <StatCard
                label="处理中会话键"
                value={control?.runtime?.channels?.in_progress_keys ?? 0}
                icon={<Activity size={20} />}
                variant="warning"
              />
              <StatCard
                label="自动化触发成功"
                value={control?.runtime?.automation?.succeeded ?? 0}
                icon={<CheckCircle2 size={20} />}
                variant="success"
              />
              <StatCard
                label="自动化触发失败"
                value={control?.runtime?.automation?.failed ?? 0}
                icon={<AlertTriangle size={20} />}
                variant="danger"
              />
            </div>
          </SurfaceCard>
        </>
      )}

      <SurfaceCard
        title="运行日志"
        description="最近 80 行，适合快速判断热重载、自动化和渠道是否有异常。"
        className="terminal-card"
      >
        <pre className="pre" style={{ maxHeight: 320, overflow: "auto" }}>
          {logTail || "暂无日志"}
        </pre>
      </SurfaceCard>
    </div>
  );
}
