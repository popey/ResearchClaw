export type ChatMessage = {
  role: "user" | "assistant" | "tool";
  content: string;
  /** Thinking/reasoning content (from thinking models) */
  thinking?: string;
  /** Tool calls made in this turn */
  toolCalls?: ToolCallInfo[];
};

export type ToolCallInfo = {
  name: string;
  arguments?: string;
  result?: string;
  status?: "running" | "done" | "error";
};

/** SSE event from /api/agent/chat/stream */
export type StreamEvent = {
  type:
    | "thinking"
    | "content"
    | "content_replace"
    | "tool_call"
    | "tool_result"
    | "done"
    | "error";
  content?: string;
  name?: string;
  arguments?: string;
  result?: string;
  session_id?: string;
};

export type PaperItem = {
  title?: string;
  id?: string;
  published?: string;
  authors?: string[];
  summary?: string;
};

export type SessionItem = {
  session_id: string;
  title?: string;
  created_at?: number;
  updated_at?: number;
  message_count?: number;
};

export type CronJobItem = {
  name: string;
  enabled: boolean;
  running: boolean;
  interval_seconds: number;
};

export type ChannelItem = {
  name: string;
  type: string;
};

export type EnvItem = {
  key: string;
  value: string;
};

export type SkillItem = {
  name?: string;
  enabled?: boolean;
  description?: string;
};

export type McpClientItem = {
  key: string;
  name?: string;
  transport?: string;
  enabled?: boolean;
  description?: string;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
};

export type AgentRunningConfig = {
  max_iters: number;
  max_input_length: number;
};

export type ProviderItem = {
  name: string;
  provider_type: string;
  model_name?: string;
  api_key?: string;
  base_url?: string;
  enabled?: boolean;
  extra?: Record<string, unknown>;
};
