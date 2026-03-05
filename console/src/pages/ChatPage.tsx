import { useMemo, useRef, useEffect, useState, useCallback } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";
import {
  MessageSquare,
  Send,
  Loader2,
  BrainCircuit,
  Wrench,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Square,
} from "lucide-react";
import Markdown from "react-markdown";
import { streamChat } from "../api";
import type { ChatMessage, StreamEvent, ToolCallInfo } from "../types";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Current streaming state (for the in-progress assistant message)
  const [streamContent, setStreamContent] = useState("");
  const [streamThinking, setStreamThinking] = useState("");
  const [streamToolCalls, setStreamToolCalls] = useState<ToolCallInfo[]>([]);

  const canSend = useMemo(
    () => chatInput.trim().length > 0 && !chatLoading,
    [chatInput, chatLoading],
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent, streamThinking, streamToolCalls]);

  const resetStream = useCallback(() => {
    setStreamContent("");
    setStreamThinking("");
    setStreamToolCalls([]);
  }, []);

  function handleStop() {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // Finalize whatever we have
    const finalContent = streamContent || "(已停止)";
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: finalContent,
        thinking: streamThinking || undefined,
        toolCalls: streamToolCalls.length ? [...streamToolCalls] : undefined,
      },
    ]);
    resetStream();
    setChatLoading(false);
  }

  function onSendChat() {
    const text = chatInput.trim();
    if (!text || chatLoading) return;

    setChatLoading(true);
    resetStream();
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setChatInput("");

    // Local accumulators (refs for closure stability)
    let accContent = "";
    let accThinking = "";
    let accToolCalls: ToolCallInfo[] = [];

    const controller = streamChat(text, sessionId, (event: StreamEvent) => {
      if (event.session_id) {
        setSessionId(event.session_id);
      }

      switch (event.type) {
        case "thinking":
          accThinking += event.content || "";
          setStreamThinking(accThinking);
          break;

        case "content":
          accContent += event.content || "";
          setStreamContent(accContent);
          break;

        case "content_replace":
          accContent = event.content || "";
          setStreamContent(accContent);
          break;

        case "tool_call":
          accToolCalls = [
            ...accToolCalls,
            {
              name: event.name || "unknown",
              arguments: event.arguments,
              status: "running",
            },
          ];
          setStreamToolCalls([...accToolCalls]);
          break;

        case "tool_result": {
          const idx = accToolCalls.findIndex(
            (tc) => tc.name === event.name && tc.status === "running",
          );
          if (idx !== -1) {
            accToolCalls[idx] = {
              ...accToolCalls[idx],
              result: event.result,
              status: "done",
            };
          } else {
            accToolCalls.push({
              name: event.name || "unknown",
              result: event.result,
              status: "done",
            });
          }
          setStreamToolCalls([...accToolCalls]);
          break;
        }

        case "done": {
          const finalContent = event.content || accContent;
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: finalContent,
              thinking: accThinking || undefined,
              toolCalls: accToolCalls.length ? accToolCalls : undefined,
            },
          ]);
          resetStream();
          setChatLoading(false);
          abortRef.current = null;
          break;
        }

        case "error":
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `错误: ${event.content}`,
              thinking: accThinking || undefined,
              toolCalls: accToolCalls.length ? accToolCalls : undefined,
            },
          ]);
          resetStream();
          setChatLoading(false);
          abortRef.current = null;
          break;
      }
    });

    abortRef.current = controller;
  }

  return (
    <div className="panel chat-container">
      <div className="messages">
        {messages.length === 0 && !chatLoading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <MessageSquare size={28} />
            </div>
            <h3>开始一段研究对话</h3>
            <p>
              你可以询问文献综述、实验设计、论文写作、数据分析等任何学术问题。Scholar
              将为你提供专业帮助。
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`msg ${msg.role}`}>
            <div className="msg-avatar">{msg.role === "user" ? "你" : "S"}</div>
            <div className="msg-bubble">
              {msg.thinking && <ThinkingBlock content={msg.thinking} />}
              {msg.toolCalls && <ToolCallsBlock calls={msg.toolCalls} />}
              <MessageContent content={msg.content} />
            </div>
          </div>
        ))}

        {/* Streaming assistant message */}
        {chatLoading && (
          <div className="msg assistant">
            <div className="msg-avatar">S</div>
            <div className="msg-bubble">
              {streamThinking && (
                <ThinkingBlock content={streamThinking} streaming />
              )}
              {streamToolCalls.length > 0 && (
                <ToolCallsBlock calls={streamToolCalls} />
              )}
              {streamContent ? (
                <MessageContent content={streamContent} />
              ) : (
                !streamThinking &&
                streamToolCalls.length === 0 && (
                  <span className="stream-cursor">
                    <Loader2 size={14} className="spinner" />
                  </span>
                )
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-bar">
        <input
          value={chatInput}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            setChatInput(e.target.value)
          }
          placeholder="例如：帮我总结 Diffusion Models 近两年趋势..."
          onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
            if (e.key === "Enter" && canSend) onSendChat();
          }}
        />
        {chatLoading ? (
          <button onClick={handleStop} className="btn-stop">
            <Square size={14} />
            停止
          </button>
        ) : (
          <button onClick={onSendChat} disabled={!canSend}>
            <Send size={16} />
            发送
          </button>
        )}
      </div>

      {sessionId && (
        <div className="chat-session-label">
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "var(--success)",
              display: "inline-block",
            }}
          />
          Session: {sessionId}
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ─────────────────────────────────────────── */

function MessageContent({ content }: { content: string }) {
  if (!content) return null;
  return (
    <div className="msg-text markdown-body">
      <Markdown>{content}</Markdown>
    </div>
  );
}

function ThinkingBlock({
  content,
  streaming,
}: {
  content: string;
  streaming?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="thinking-block">
      <div className="thinking-header" onClick={() => setExpanded((v) => !v)}>
        <BrainCircuit size={14} />
        <span>{streaming ? "正在思考..." : "思考过程"}</span>
        {streaming && <Loader2 size={12} className="spinner" />}
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {expanded && <div className="thinking-content">{content}</div>}
    </div>
  );
}

function ToolCallsBlock({ calls }: { calls: ToolCallInfo[] }) {
  return (
    <div className="tool-calls-block">
      {calls.map((tc, i) => (
        <div
          key={i}
          className={`tool-call-item tool-call-${tc.status || "running"}`}
        >
          <div className="tool-call-header">
            {tc.status === "running" ? (
              <Loader2 size={13} className="spinner" />
            ) : tc.status === "error" ? (
              <XCircle size={13} />
            ) : (
              <CheckCircle2 size={13} />
            )}
            <Wrench size={12} />
            <span className="tool-call-name">{tc.name}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
