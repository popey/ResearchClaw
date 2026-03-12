import { streamChat } from "./api";
import type { ChatMessage, StreamEvent, ToolCallInfo } from "./types";

const CHAT_STATE_STORAGE_KEY = "researchclaw.chat.state.v1";

export type ChatRuntimeState = {
  sessionId?: string;
  agentId?: string;
  messages: ChatMessage[];
  chatLoading: boolean;
  streamContent: string;
  streamThinking: string;
  streamToolCalls: ToolCallInfo[];
};

type PersistedChatState = Partial<ChatRuntimeState> & {
  sessionId?: string;
  agentId?: string;
  messages?: ChatMessage[];
};

const EMPTY_STATE: ChatRuntimeState = {
  sessionId: undefined,
  agentId: undefined,
  messages: [],
  chatLoading: false,
  streamContent: "",
  streamThinking: "",
  streamToolCalls: [],
};

function canUseStorage(): boolean {
  return (
    typeof window !== "undefined" && typeof window.localStorage !== "undefined"
  );
}

function createSessionId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `chat-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function normalizeRole(value: unknown): ChatMessage["role"] {
  if (value === "user" || value === "assistant" || value === "tool") {
    return value;
  }
  return "assistant";
}

function normalizeMessages(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(
      (m) =>
        m &&
        typeof m === "object" &&
        typeof (m as ChatMessage).content === "string",
    )
    .map((m) => {
      const msg = m as ChatMessage;
      return {
        role: normalizeRole(msg.role),
        content: String(msg.content ?? ""),
        thinking: msg.thinking ? String(msg.thinking) : undefined,
        toolCalls: Array.isArray(msg.toolCalls)
          ? msg.toolCalls.map((tc) => ({
              name: String(tc?.name ?? "unknown"),
              arguments:
                tc?.arguments === undefined ? undefined : String(tc.arguments),
              result: tc?.result === undefined ? undefined : String(tc.result),
              status:
                tc?.status === "running" ||
                tc?.status === "done" ||
                tc?.status === "error"
                  ? tc.status
                  : undefined,
            }))
          : undefined,
      };
    });
}

function loadInitialState(): ChatRuntimeState {
  if (!canUseStorage()) return { ...EMPTY_STATE };
  try {
    const raw = localStorage.getItem(CHAT_STATE_STORAGE_KEY);
    if (!raw) return { ...EMPTY_STATE };
    const parsed = JSON.parse(raw) as PersistedChatState;
    if (!parsed || typeof parsed !== "object") return { ...EMPTY_STATE };
    return {
      sessionId:
        typeof parsed.sessionId === "string" ? parsed.sessionId : undefined,
      agentId: typeof parsed.agentId === "string" ? parsed.agentId : undefined,
      messages: normalizeMessages(parsed.messages),
      // Never resume loading state after full page refresh.
      chatLoading: false,
      streamContent: "",
      streamThinking: "",
      streamToolCalls: [],
    };
  } catch {
    return { ...EMPTY_STATE };
  }
}

let state: ChatRuntimeState = loadInitialState();
let streamController: AbortController | null = null;
const listeners = new Set<() => void>();

function clearActiveStream() {
  if (!streamController) return;
  streamController.abort();
  streamController = null;
}

function persistState() {
  if (!canUseStorage()) return;
  try {
    const payload: PersistedChatState = {
      sessionId: state.sessionId,
      agentId: state.agentId,
      messages: state.messages,
      chatLoading: state.chatLoading,
      streamContent: state.streamContent,
      streamThinking: state.streamThinking,
      streamToolCalls: state.streamToolCalls,
    };
    localStorage.setItem(CHAT_STATE_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore storage failures.
  }
}

function emit() {
  persistState();
  listeners.forEach((listener) => listener());
}

function setState(updater: (prev: ChatRuntimeState) => ChatRuntimeState) {
  state = updater(state);
  emit();
}

function resetStreamFields(prev: ChatRuntimeState): ChatRuntimeState {
  return {
    ...prev,
    streamContent: "",
    streamThinking: "",
    streamToolCalls: [],
  };
}

function setStreamPatch(
  patch: Partial<
    Pick<
      ChatRuntimeState,
      "streamContent" | "streamThinking" | "streamToolCalls" | "chatLoading"
    >
  >,
) {
  setState((prev) => ({
    ...prev,
    ...patch,
  }));
}

function updateActiveConversation(
  sessionId: string,
  agentId?: string,
  callback?: (sessionId: string) => void,
) {
  setState((prev) => ({
    ...prev,
    sessionId,
    agentId: agentId || prev.agentId,
  }));
  callback?.(sessionId);
}

function pushRunningToolCall(
  calls: ToolCallInfo[],
  event: StreamEvent,
): ToolCallInfo[] {
  return [
    ...calls,
    {
      name: event.name || "unknown",
      arguments: event.arguments,
      status: "running",
    },
  ];
}

function resolveToolResult(
  calls: ToolCallInfo[],
  event: StreamEvent,
): ToolCallInfo[] {
  const next = [...calls];
  const idx = next.findIndex(
    (tc) => tc.name === event.name && tc.status === "running",
  );
  if (idx !== -1) {
    next[idx] = {
      ...next[idx],
      result: event.result,
      status: "done",
    };
    return next;
  }
  next.push({
    name: event.name || "unknown",
    result: event.result,
    status: "done",
  });
  return next;
}

function finalizeStreamWithContent(finalContent: string) {
  setState((prev) => ({
    ...resetStreamFields(prev),
    chatLoading: false,
    messages: [
      ...prev.messages,
      {
        role: "assistant",
        content: finalContent,
        thinking: prev.streamThinking || undefined,
        toolCalls: prev.streamToolCalls.length
          ? [...prev.streamToolCalls]
          : undefined,
      },
    ],
  }));
}

export function subscribeChatRuntime(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getChatRuntimeState(): ChatRuntimeState {
  return state;
}

export function replaceChatConversation(
  sessionId: string | undefined,
  messages: ChatMessage[],
  options?: { stopStreaming?: boolean; agentId?: string },
) {
  const shouldStop = options?.stopStreaming ?? true;
  if (shouldStop) clearActiveStream();

  setState((prev) => ({
    ...resetStreamFields(prev),
    sessionId,
    agentId: options?.agentId,
    messages,
    chatLoading: shouldStop ? false : prev.chatLoading,
  }));
}

export function startNewConversation() {
  clearActiveStream();
  state = { ...EMPTY_STATE };
  emit();
}

export function stopChatStreaming() {
  clearActiveStream();
  if (!state.chatLoading) return;
  const finalContent = state.streamContent || "(已停止)";
  finalizeStreamWithContent(finalContent);
}

export function sendChatMessage(
  rawText: string,
  options?: {
    preferredSessionId?: string;
    preferredAgentId?: string;
    onSessionId?: (sessionId: string) => void;
  },
): string | null {
  const text = rawText.trim();
  if (!text || state.chatLoading) return null;

  const activeSessionId =
    options?.preferredSessionId || state.sessionId || createSessionId();

  setState((prev) => ({
    ...resetStreamFields(prev),
    sessionId: activeSessionId,
    agentId: options?.preferredAgentId || prev.agentId,
    chatLoading: true,
    messages: [...prev.messages, { role: "user", content: text }],
  }));

  let accContent = "";
  let accThinking = "";
  let accToolCalls: ToolCallInfo[] = [];

  streamController = streamChat(
    text,
    activeSessionId,
    options?.preferredAgentId || state.agentId,
    (event: StreamEvent) => {
      if (event.session_id) {
        updateActiveConversation(
          event.session_id,
          event.agent_id,
          options?.onSessionId,
        );
      }

      switch (event.type) {
        case "thinking":
          accThinking += event.content || "";
          setStreamPatch({ streamThinking: accThinking });
          break;

        case "content":
          accContent += event.content || "";
          setStreamPatch({ streamContent: accContent });
          break;

        case "content_replace":
          accContent = event.content || "";
          setStreamPatch({ streamContent: accContent });
          break;

        case "tool_call":
          accToolCalls = pushRunningToolCall(accToolCalls, event);
          setStreamPatch({ streamToolCalls: [...accToolCalls] });
          break;

        case "tool_result":
          accToolCalls = resolveToolResult(accToolCalls, event);
          setStreamPatch({ streamToolCalls: [...accToolCalls] });
          break;

        case "done": {
          const finalContent = event.content || accContent;
          streamController = null;
          finalizeStreamWithContent(finalContent);
          break;
        }

        case "error": {
          const errText = String(event.content || "unknown error");
          const mergedContent = accContent.trim()
            ? `${accContent}\n\n[流式中断] ${errText}`
            : `错误: ${errText}`;
          streamController = null;
          finalizeStreamWithContent(mergedContent);
          break;
        }

        default:
          break;
      }
    },
  );

  return activeSessionId;
}
