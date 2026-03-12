import { useEffect, useState } from "react";
import {
  Clock,
  Eye,
  Hash,
  MessageCircle,
  PlayCircle,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  deleteSession,
  getAgents,
  getSessionDetail,
  getSessionsByAgent,
} from "../api";
import { useI18n } from "../i18n";
import type { SessionItem } from "../types";
import {
  Badge,
  DetailModal,
  EmptyState,
  MetricPill,
  NoticeBanner,
  PageHeader,
  SurfaceCard,
} from "../components/ui";

function formatTs(ts?: number): string {
  if (!ts) return "-";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
}

export default function SessionsPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [agents, setAgents] = useState<any[]>([]);
  const [activeAgent, setActiveAgent] = useState<string>("all");
  const [selected, setSelected] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");

  const filteredSessions = sessions.filter((session) => {
    const haystack = [
      session.title || "",
      session.session_id,
      session.agent_id || "",
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  async function onLoad() {
    const [sessionRows, agentRows] = await Promise.all([
      getSessionsByAgent(activeAgent === "all" ? undefined : activeAgent),
      getAgents(),
    ]);
    setSessions(sessionRows);
    setAgents(agentRows);
    setLoaded(true);
  }

  useEffect(() => {
    void onLoad();
  }, [activeAgent]);

  async function onOpen(session: SessionItem) {
    const targetAgentId =
      activeAgent === "all"
        ? session.agent_id
        : activeAgent || session.agent_id;
    setSelected(
      await getSessionDetail(session.session_id, targetAgentId || undefined),
    );
  }

  async function onDelete(session: SessionItem) {
    const sessionId = session.session_id;
    const targetAgentId =
      activeAgent === "all"
        ? session.agent_id
        : activeAgent || session.agent_id;
    if (
      !window.confirm(
        t("确认删除会话 {id} 吗？", { id: sessionId.slice(0, 8) }),
      )
    ) {
      return;
    }
    await deleteSession(sessionId, targetAgentId || undefined);
    if (selected?.session_id === sessionId) {
      setSelected(null);
    }
    await onLoad();
  }

  function onContinue(session: SessionItem) {
    const query = new URLSearchParams();
    query.set("session_id", session.session_id);
    if (session.agent_id) {
      query.set("agent_id", session.agent_id);
    }
    navigate(`/chat?${query.toString()}`);
  }

  return (
    <div className="panel">
      <PageHeader
        eyebrow="Conversation Archive"
        title={t("会话管理")}
        description={t(
          "按 Agent 查看历史会话，快速恢复研究线程并继续推进当前任务。",
        )}
        meta={
          <div className="page-header-meta-row">
            <MetricPill label={t("会话数")} value={sessions.length} />
            <MetricPill label="Agent 视图" value={activeAgent} />
            <MetricPill label={t("可选 Agent")} value={agents.length} />
          </div>
        }
        actions={
          <div className="filter-toolbar">
            <div className="filter-field filter-field-compact">
              <span className="filter-field-label">Agent</span>
              <select
                value={activeAgent}
                onChange={(e) => setActiveAgent(e.target.value)}
              >
                <option value="all">全部 Agent</option>
                {agents.map((agent) => (
                  <option key={String(agent.id)} value={String(agent.id)}>
                    {String(agent.id)}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter-field filter-field-grow">
              <span className="filter-field-label">搜索</span>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索标题 / session id / agent"
              />
            </div>
            <div className="filter-toolbar-actions">
              <button onClick={onLoad}>
                <RefreshCw size={15} />
                刷新会话
              </button>
            </div>
          </div>
        }
      />

      {!loaded && sessions.length === 0 && (
        <EmptyState
          icon={<MessageCircle size={28} />}
          title={t("加载会话列表")}
          description={t("查看和管理所有 Agent 交互会话")}
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              {t("加载")}
            </button>
          }
        />
      )}

      {loaded && query.trim() && (
        <NoticeBanner variant="info">
          {t("当前筛选结果 {filtered} / {total}", {
            filtered: filteredSessions.length,
            total: sessions.length,
          })}
        </NoticeBanner>
      )}

      <SurfaceCard
        title={t("会话列表")}
        description={t(
          "可以直接查看详情、继续对话，或者按 Agent 范围清理历史会话。",
        )}
      >
        <div className="card-list animate-list">
          {filteredSessions.length === 0 && (
            <div className="empty-inline">
              {t("当前筛选条件下没有匹配会话")}
            </div>
          )}
          {filteredSessions.map((session: SessionItem) => (
            <div key={session.session_id} className="data-row">
              <div className="data-row-info">
                <div className="data-row-title">
                  {session.title || session.session_id}
                </div>
                <div className="data-row-meta">
                  <Clock
                    size={11}
                    style={{ marginRight: 3, verticalAlign: "middle" }}
                  />
                  {formatTs(session.updated_at)}
                  <span style={{ margin: "0 6px" }}>·</span>
                  <Hash
                    size={11}
                    style={{ marginRight: 2, verticalAlign: "middle" }}
                  />
                  {t("{count} 条消息", {
                    count: session.message_count ?? 0,
                  })}
                </div>
              </div>
              <div className="data-row-actions">
                <Badge variant="neutral">
                  {(session.agent_id || "main") +
                    ":" +
                    session.session_id.slice(0, 8)}
                </Badge>
                <button
                  className="btn-sm btn-secondary"
                  onClick={() => onOpen(session)}
                >
                  <Eye size={14} />
                  查看
                </button>
                <button className="btn-sm" onClick={() => onContinue(session)}>
                  <PlayCircle size={14} />
                  继续对话
                </button>
                <button
                  className="btn-sm danger"
                  onClick={() => onDelete(session)}
                >
                  <Trash2 size={14} />
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      </SurfaceCard>

      {selected && (
        <DetailModal title="会话详情" onClose={() => setSelected(null)}>
          <pre className="pre">{JSON.stringify(selected, null, 2)}</pre>
        </DetailModal>
      )}
    </div>
  );
}
