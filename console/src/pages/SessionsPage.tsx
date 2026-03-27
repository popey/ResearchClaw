import { useEffect, useMemo, useState } from "react";
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
  batchDeleteSessions,
  deleteSession,
  getAgents,
  getSessionDetail,
  getSessionsByAgent,
} from "../api";
import { useI18n } from "../i18n";
import type { SessionDeleteTarget, SessionItem } from "../types";
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

function resolveSessionAgentId(
  session: SessionItem,
  activeAgent: string,
): string | undefined {
  if (activeAgent === "all") return session.agent_id || undefined;
  return activeAgent || session.agent_id || undefined;
}

function getSessionSelectionKey(
  session: SessionItem,
  activeAgent: string,
): string {
  return `${resolveSessionAgentId(session, activeAgent) || "main"}:${session.session_id}`;
}

function getSessionDeleteTarget(
  session: SessionItem,
  activeAgent: string,
): SessionDeleteTarget {
  return {
    session_id: session.session_id,
    agent_id: resolveSessionAgentId(session, activeAgent) || "main",
  };
}

export default function SessionsPage() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [agents, setAgents] = useState<any[]>([]);
  const [activeAgent, setActiveAgent] = useState<string>("all");
  const [selected, setSelected] = useState<any>(null);
  const [selectedSessionKeys, setSelectedSessionKeys] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busySessionKey, setBusySessionKey] = useState("");
  const [batchDeleting, setBatchDeleting] = useState(false);

  const queryText = query.trim().toLowerCase();
  const filteredSessions = useMemo(
    () =>
      sessions.filter((session) => {
        const haystack = [
          session.title || "",
          session.session_id,
          session.agent_id || "",
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(queryText);
      }),
    [queryText, sessions],
  );

  const selectedSessions = useMemo(
    () =>
      sessions.filter((session) =>
        selectedSessionKeys.includes(
          getSessionSelectionKey(session, activeAgent),
        ),
      ),
    [activeAgent, selectedSessionKeys, sessions],
  );

  const visibleSelectionKeys = useMemo(
    () =>
      filteredSessions.map((session) =>
        getSessionSelectionKey(session, activeAgent),
      ),
    [activeAgent, filteredSessions],
  );

  const selectedVisibleCount = useMemo(
    () =>
      visibleSelectionKeys.filter((key) => selectedSessionKeys.includes(key))
        .length,
    [selectedSessionKeys, visibleSelectionKeys],
  );

  const allVisibleSelected =
    visibleSelectionKeys.length > 0 &&
    selectedVisibleCount === visibleSelectionKeys.length;

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

  useEffect(() => {
    const validKeys = new Set(
      sessions.map((session) => getSessionSelectionKey(session, activeAgent)),
    );
    setSelectedSessionKeys((prev) => prev.filter((key) => validKeys.has(key)));
  }, [activeAgent, sessions]);

  async function onOpen(session: SessionItem) {
    const targetAgentId = resolveSessionAgentId(session, activeAgent);
    setSelected(
      await getSessionDetail(session.session_id, targetAgentId || undefined),
    );
  }

  async function onDelete(session: SessionItem) {
    const sessionId = session.session_id;
    const targetAgentId = resolveSessionAgentId(session, activeAgent);
    const sessionKey = getSessionSelectionKey(session, activeAgent);
    if (
      !window.confirm(
        t("确认删除会话 {id} 吗？", { id: sessionId.slice(0, 8) }),
      )
    ) {
      return;
    }
    setBusySessionKey(sessionKey);
    setError("");
    setNotice("");
    try {
      await deleteSession(sessionId, targetAgentId || undefined);
      if (selected?.session_id === sessionId) {
        setSelected(null);
      }
      setSelectedSessionKeys((prev) =>
        prev.filter((key) => key !== sessionKey),
      );
      setNotice(`已删除会话 ${sessionId.slice(0, 8)}`);
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除会话失败");
    } finally {
      setBusySessionKey("");
    }
  }

  function toggleSessionSelection(session: SessionItem) {
    const key = getSessionSelectionKey(session, activeAgent);
    setSelectedSessionKeys((prev) =>
      prev.includes(key)
        ? prev.filter((item) => item !== key)
        : [...prev, key],
    );
  }

  function toggleVisibleSelection() {
    setSelectedSessionKeys((prev) => {
      if (allVisibleSelected) {
        return prev.filter((key) => !visibleSelectionKeys.includes(key));
      }
      const next = new Set(prev);
      for (const key of visibleSelectionKeys) {
        next.add(key);
      }
      return Array.from(next);
    });
  }

  async function onBatchDelete() {
    if (selectedSessions.length === 0) return;
    if (
      !window.confirm(
        `确认批量删除 ${selectedSessions.length} 个会话吗？该操作会同时清理关联的记忆消息。`,
      )
    ) {
      return;
    }

    setBatchDeleting(true);
    setError("");
    setNotice("");
    try {
      const result = await batchDeleteSessions(
        selectedSessions.map((session) =>
          getSessionDeleteTarget(session, activeAgent),
        ),
      );
      if (selected) {
        const selectedKey = getSessionSelectionKey(selected, activeAgent);
        const deletedKeys = new Set(
          result.deleted.map(
            (item) => `${item.agent_id || "main"}:${item.session_id}`,
          ),
        );
        if (deletedKeys.has(selectedKey)) {
          setSelected(null);
        }
      }
      setSelectedSessionKeys([]);
      setNotice(
        result.not_found?.length
          ? `已删除 ${result.deleted_count} 个会话，${result.not_found.length} 个未找到。`
          : `已删除 ${result.deleted_count} 个会话。`,
      );
      await onLoad();
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量删除会话失败");
    } finally {
      setBatchDeleting(false);
    }
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

      {notice && <NoticeBanner variant="success">{notice}</NoticeBanner>}
      {error && <NoticeBanner variant="danger">{error}</NoticeBanner>}

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

      {selectedSessionKeys.length > 0 && (
        <NoticeBanner variant="warning">
          已选择 {selectedSessionKeys.length} 个会话。可以直接批量删除，或清空选择后继续筛选。
        </NoticeBanner>
      )}

      <SurfaceCard
        title={t("会话列表")}
        description={t(
          "可以直接查看详情、继续对话，或者按 Agent 范围清理历史会话。",
        )}
        actions={
          <div className="toolbar-row">
            <button
              type="button"
              onClick={toggleVisibleSelection}
              disabled={visibleSelectionKeys.length === 0 || batchDeleting}
            >
              {allVisibleSelected ? "取消选择当前结果" : "选择当前结果"}
            </button>
            <button
              type="button"
              onClick={() => setSelectedSessionKeys([])}
              disabled={selectedSessionKeys.length === 0 || batchDeleting}
            >
              清空选择
            </button>
            <button
              className="danger"
              type="button"
              onClick={onBatchDelete}
              disabled={selectedSessions.length === 0 || batchDeleting}
            >
              <Trash2 size={14} />
              {batchDeleting
                ? "批量删除中..."
                : `批量删除 (${selectedSessions.length})`}
            </button>
          </div>
        }
      >
        <div className="card-list animate-list">
          {filteredSessions.length === 0 && (
            <div className="empty-inline">
              {t("当前筛选条件下没有匹配会话")}
            </div>
          )}
          {filteredSessions.map((session: SessionItem) => {
            const sessionKey = getSessionSelectionKey(session, activeAgent);
            const isSelected = selectedSessionKeys.includes(sessionKey);
            const isBusy = batchDeleting || busySessionKey === sessionKey;
            return (
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
                    onChange={() => toggleSessionSelection(session)}
                  />
                  选择
                </label>
                <Badge variant="neutral">
                  {(session.agent_id || "main") +
                    ":" +
                    session.session_id.slice(0, 8)}
                </Badge>
                <button
                  className="btn-sm btn-secondary"
                  disabled={isBusy}
                  onClick={() => onOpen(session)}
                >
                  <Eye size={14} />
                  查看
                </button>
                <button
                  className="btn-sm"
                  disabled={isBusy}
                  onClick={() => onContinue(session)}
                >
                  <PlayCircle size={14} />
                  继续对话
                </button>
                <button
                  className="btn-sm danger"
                  disabled={isBusy}
                  onClick={() => onDelete(session)}
                >
                  <Trash2 size={14} />
                  删除
                </button>
              </div>
            </div>
          )})}
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
