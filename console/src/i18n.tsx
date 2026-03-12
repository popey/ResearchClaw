import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Locale = "zh" | "en";

const STORAGE_KEY = "researchclaw.console.locale";

const EN_DICT: Record<string, string> = {
  研究: "Research",
  控制: "Control",
  智能体: "Agent",
  设置: "Settings",
  "AI 对话": "AI Chat",
  论文检索: "Paper Search",
  频道: "Channels",
  会话: "Sessions",
  定时任务: "Scheduled Jobs",
  心跳: "Heartbeat",
  系统状态: "System Status",
  工作区: "Workspace",
  技能: "Skills",
  "Agent 配置": "Agent Config",
  模型: "Models",
  环境变量: "Environment Variables",
  "ResearchClaw 运行中": "ResearchClaw Running",
  刷新: "Refresh",
  加载: "Load",
  新建任务: "New Job",
  新对话: "New Chat",
  继续对话: "Continue Chat",
  查看: "View",
  删除: "Delete",
  编辑: "Edit",
  保存: "Save",
  取消: "Cancel",
  重置: "Reset",
  停止: "Stop",
  发送: "Send",
  "运行中...": "Running...",
  "保存中...": "Saving...",
  "删除中...": "Deleting...",
  "应用中...": "Applying...",
  "检索中...": "Searching...",
  "加载中...": "Loading...",
  已启用: "Enabled",
  已禁用: "Disabled",
  已暂停: "Paused",
  启用: "Enable",
  暂停: "Pause",
  启用状态: "Status",
  任务名称: "Job Name",
  任务类型: "Task Type",
  时区: "Timezone",
  通道: "Channel",
  目标: "Target",
  "目标 User ID": "Target User ID",
  "目标 Session ID": "Target Session ID",
  发送模式: "Dispatch Mode",
  并发上限: "Max Concurrency",
  超时秒数: "Timeout (seconds)",
  错过触发宽限秒数: "Misfire Grace (seconds)",
  文本内容: "Text Content",
  "Agent 提示词": "Agent Prompt",
  "Cron 表达式": "Cron Expression",
  "Cron 表达式不能为空": "Cron expression cannot be empty",
  任务名称不能为空: "Task name cannot be empty",
  文本内容不能为空: "Text content cannot be empty",
  "Agent 提示词不能为空": "Agent prompt cannot be empty",
  "确认删除定时任务「{name}」吗？":
    'Are you sure you want to delete scheduled job "{name}"?',
  '确定删除供应商 "{name}"？':
    'Are you sure you want to delete provider "{name}"?',
  "通道 (默认 console)": "Channel (default: console)",
  马上运行: "Run Now",
  编辑定时任务: "Edit Job",
  新建定时任务: "New Job",
  加载定时任务: "Loading Jobs",
  暂无定时任务: "No Scheduled Jobs",
  刷新任务: "Refresh Jobs",
  点击刷新加载频道: "Click Refresh to Load Channels",
  频道管理: "Channel Management",
  刷新频道: "Refresh Channels",
  会话管理: "Session Management",
  刷新会话: "Refresh Sessions",
  会话详情: "Session Detail",
  开始一段研究对话: "Start a Research Conversation",
  暂无历史会话: "No Chat History",
  "当前会话: ": "Current Session: ",
  未创建: "Not Created",
  思考过程: "Reasoning",
  "正在思考...": "Thinking...",
  加载工作区信息: "Loading Workspace",
  工作区文件: "Workspace Files",
  刷新工作区: "Refresh Workspace",
  关键文件: "Key Files",
  必需: "Required",
  请选择文件: "Please select a file",
  "加载文件中...": "Loading file...",
  对话: "Chat",
  配置: "Config",
  "对话 / 技能 / 定时 / 心跳 关系":
    "Chat / Skills / Schedules / Heartbeat Relations",
  刷新状态: "Refresh Status",
  "API 健康": "API Health",
  正常: "Healthy",
  运行状态: "Runtime",
  运行中: "Running",
  已停止: "Stopped",
  可用工具: "Available Tools",
  激活技能: "Active Skills",
  关闭: "Off",
  运行模式: "Run Mode",
  运行时长: "Uptime",
  加载技能列表: "Loading Skills",
  技能管理: "Skill Management",
  刷新技能: "Refresh Skills",
  加载环境变量: "Loading Environment Variables",
  "检索 ArXiv": "Search ArXiv",
  未找到相关论文: "No relevant papers found",
  搜索学术论文: "Search Academic Papers",
  "MCP 客户端": "MCP Clients",
  新增客户端: "New Client",
  "加载 MCP 客户端": "Loading MCP Clients",
  添加新客户端: "Add New Client",
  新增供应商: "Add Provider",
  供应商类型: "Provider Type",
  模型名称: "Model Name",
  "应用到 Agent（热重载）": "Apply to Agent (hot reload)",
  应用: "Apply",
  保存设置: "Save Settings",
  "模型 & 供应商": "Models & Providers",
  加载供应商配置: "Loading Provider Config",
  暂无供应商: "No Providers",
  "加载 Agent 配置": "Loading Agent Config",
  加载配置: "Load Config",
  重新加载: "Reload",
  最大迭代次数: "Max Iterations",
  最大输入长度: "Max Input Length",
  心跳检测: "Heartbeat Check",
  刷新心跳: "Refresh Heartbeat",
  检测系统心跳: "Check Heartbeat",
  "网络连接失败：请确认后端服务可用并检查浏览器网络/代理设置。":
    "Network error: please ensure backend service is running and check browser network/proxy settings.",
  "流式连接超时：后端响应过慢或网络不稳定。":
    "Stream timeout: backend is slow or network is unstable.",
  "流式连接中断：长时间未收到数据，请重试。":
    "Stream interrupted: no data received for a while. Please retry.",
  "流式连接已结束，但未收到完成信号。":
    "Stream closed without a completion signal.",
  "流式连接未返回有效数据。": "No valid data from streaming connection.",
  "(已停止)": "(Stopped)",
};

function normalizeLocale(input: string | null | undefined): Locale {
  if (!input) return "zh";
  const v = input.toLowerCase();
  if (v.startsWith("en")) return "en";
  return "zh";
}

function formatTemplate(
  template: string,
  vars?: Record<string, unknown>,
): string {
  if (!vars) return template;
  let out = template;
  for (const [k, v] of Object.entries(vars)) {
    out = out.replace(new RegExp(`\\{${k}\\}`, "g"), String(v ?? ""));
  }
  return out;
}

export function translateText(
  locale: Locale,
  text: string,
  vars?: Record<string, unknown>,
): string {
  const source = String(text ?? "");
  if (!source) return source;
  if (locale === "zh") return formatTemplate(source, vars);

  if (EN_DICT[source]) return formatTemplate(EN_DICT[source], vars);

  const leading = source.match(/^\s*/)?.[0] ?? "";
  const trailing = source.match(/\s*$/)?.[0] ?? "";
  const core = source.slice(leading.length, source.length - trailing.length);
  if (EN_DICT[core]) {
    return `${leading}${formatTemplate(EN_DICT[core], vars)}${trailing}`;
  }
  return formatTemplate(source, vars);
}

export function getStoredLocale(): Locale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return normalizeLocale(raw);
  } catch {
    // ignore
  }
  if (typeof navigator !== "undefined") {
    return normalizeLocale(navigator.language);
  }
  return "zh";
}

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (text: string, vars?: Record<string, unknown>) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => getStoredLocale());

  useEffect(() => {
    let cancelled = false;
    let shouldFetch = true;
    try {
      shouldFetch = !localStorage.getItem(STORAGE_KEY);
    } catch {
      shouldFetch = true;
    }
    if (!shouldFetch) return () => {};

    void fetch("/api/config")
      .then(async (res) => (res.ok ? res.json() : {}))
      .then((cfg) => {
        if (cancelled) return;
        const lang = typeof cfg?.language === "string" ? cfg.language : "";
        if (lang) {
          setLocaleState(normalizeLocale(lang));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setLocale = useCallback((next: Locale) => {
    const normalized = normalizeLocale(next);
    setLocaleState(normalized);
    try {
      localStorage.setItem(STORAGE_KEY, normalized);
    } catch {
      // ignore
    }
    const payload = { language: normalized === "zh" ? "zh" : "en" };
    void fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }, []);

  const t = useCallback(
    (text: string, vars?: Record<string, unknown>) =>
      translateText(locale, text, vars),
    [locale],
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
    }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return ctx;
}

const TRANSLATABLE_ATTRS = [
  "placeholder",
  "title",
  "aria-label",
  "alt",
  "data-tooltip",
] as const;
const ORIGINAL_TEXT_NODES = new WeakMap<Text, string>();
const ORIGINAL_ATTRS = new WeakMap<Element, Record<string, string>>();

function _is_skippable_text_node(node: Text): boolean {
  const parent = node.parentElement;
  if (!parent) return true;

  const tag = parent.tagName.toLowerCase();
  if (tag === "script" || tag === "style" || tag === "noscript") return true;
  if (parent.closest("textarea, input, code, pre")) return true;
  if (parent.closest("[data-no-auto-translate]")) return true;
  if (parent.isContentEditable) return true;
  return false;
}

function _apply_text_translations(root: HTMLElement, locale: Locale): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let cur = walker.nextNode();
  while (cur) {
    const node = cur as Text;
    const raw = node.nodeValue ?? "";
    if (raw.trim() && !_is_skippable_text_node(node)) {
      if (!ORIGINAL_TEXT_NODES.has(node)) {
        ORIGINAL_TEXT_NODES.set(node, raw);
      }
      let original = ORIGINAL_TEXT_NODES.get(node) ?? raw;
      const translatedOriginal = translateText("en", original);
      if (raw !== original && raw !== translatedOriginal) {
        ORIGINAL_TEXT_NODES.set(node, raw);
        original = raw;
      }
      const next = locale === "en" ? translateText("en", original) : original;
      if (node.nodeValue !== next) {
        node.nodeValue = next;
      }
    }
    cur = walker.nextNode();
  }
}

function _apply_attr_translations(root: HTMLElement, locale: Locale): void {
  const selector = TRANSLATABLE_ATTRS.map((x) => `[${x}]`).join(",");
  if (!selector) return;

  root.querySelectorAll(selector).forEach((el) => {
    if (el.closest("[data-no-auto-translate]")) {
      return;
    }
    let record = ORIGINAL_ATTRS.get(el);
    if (!record) {
      record = {};
      ORIGINAL_ATTRS.set(el, record);
    }

    for (const attr of TRANSLATABLE_ATTRS) {
      const value = el.getAttribute(attr);
      if (value == null) continue;
      if (!(attr in record)) {
        record[attr] = value;
      }
      let original = record[attr] ?? value;
      const translatedOriginal = translateText("en", original);
      if (value !== original && value !== translatedOriginal) {
        record[attr] = value;
        original = value;
      }
      const next = locale === "en" ? translateText("en", original) : original;
      if (value !== next) {
        el.setAttribute(attr, next);
      }
    }
  });
}

function _apply_dom_translations(root: HTMLElement, locale: Locale): void {
  _apply_text_translations(root, locale);
  _apply_attr_translations(root, locale);
}

export function AutoTranslate({ children }: { children: React.ReactNode }) {
  const { locale } = useI18n();

  useEffect(() => {
    const root = document.getElementById("root");
    if (!root) return () => {};

    let rafId: number | null = null;
    const run = () => {
      rafId = null;
      _apply_dom_translations(root, locale);
    };

    run();

    const observer = new MutationObserver(() => {
      if (rafId != null) {
        cancelAnimationFrame(rafId);
      }
      rafId = requestAnimationFrame(run);
    });

    observer.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: [...TRANSLATABLE_ATTRS],
    });

    return () => {
      observer.disconnect();
      if (rafId != null) {
        cancelAnimationFrame(rafId);
      }
    };
  }, [locale]);

  return <>{children}</>;
}
