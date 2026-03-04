import { useMemo, useRef, useEffect, useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";
import { MessageSquare, Send, Loader2 } from "lucide-react";
import { sendChat } from "../api";
import type { ChatMessage } from "../types";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const canSend = useMemo(
    () => chatInput.trim().length > 0 && !chatLoading,
    [chatInput, chatLoading],
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function onSendChat() {
    const text = chatInput.trim();
    if (!text) return;
    setChatLoading(true);
    setMessages((prev: ChatMessage[]) => [
      ...prev,
      { role: "user", content: text },
    ]);
    setChatInput("");

    try {
      const res = await sendChat(text, sessionId);
      setSessionId(res.session_id);
      setMessages((prev: ChatMessage[]) => [
        ...prev,
        { role: "assistant", content: res.response },
      ]);
    } catch (error) {
      setMessages((prev: ChatMessage[]) => [
        ...prev,
        { role: "assistant", content: `请求失败: ${String(error)}` },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  return (
    <div className="panel chat-container">
      <div className="messages">
        {messages.length === 0 && (
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
            <div className="msg-bubble">{msg.content}</div>
          </div>
        ))}
        {chatLoading && (
          <div className="msg assistant">
            <div className="msg-avatar">S</div>
            <div className="msg-bubble">
              <Loader2 size={16} className="spinner" />
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
        <button onClick={onSendChat} disabled={!canSend}>
          <Send size={16} />
          {chatLoading ? "发送中" : "发送"}
        </button>
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
