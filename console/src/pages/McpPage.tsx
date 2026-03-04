import { useState } from "react";
import type { ChangeEvent } from "react";
import { Cable, RefreshCw, Plus, Trash2 } from "lucide-react";
import {
  listMcpClients,
  createMcpClient,
  toggleMcpClient,
  deleteMcpClient,
} from "../api";
import type { McpClientItem } from "../types";
import { PageHeader, EmptyState, Badge, Toggle } from "../components/ui";

export default function McpPage() {
  const [clients, setClients] = useState<McpClientItem[]>([]);
  const [newKey, setNewKey] = useState("");
  const [newName, setNewName] = useState("");
  const [newCommand, setNewCommand] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  async function onLoad() {
    setClients(await listMcpClients());
    setLoaded(true);
  }

  async function onCreate() {
    if (!newKey.trim()) return;
    await createMcpClient(newKey.trim(), {
      name: newName.trim() || newKey.trim(),
      transport: "stdio",
      enabled: true,
      description: "",
      command: newCommand.trim() || "npx",
      args: [],
      url: "",
      env: {},
    });
    setNewKey("");
    setNewName("");
    setNewCommand("");
    setShowAdd(false);
    await onLoad();
  }

  async function onToggle(key: string) {
    await toggleMcpClient(key);
    await onLoad();
  }

  async function onDelete(key: string) {
    await deleteMcpClient(key);
    await onLoad();
  }

  return (
    <div className="panel">
      <PageHeader
        title="MCP 客户端"
        description="管理 Model Context Protocol 客户端连接"
        actions={
          <div className="row">
            <button
              className="btn-secondary"
              onClick={() => setShowAdd(!showAdd)}
            >
              <Plus size={15} />
              新增客户端
            </button>
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              刷新
            </button>
          </div>
        }
      />

      {showAdd && (
        <div
          className="card mb-4"
          style={{
            borderColor: "var(--brand-200)",
            background: "var(--brand-50)",
          }}
        >
          <h3 style={{ marginBottom: 12 }}>
            <Plus
              size={14}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            添加新客户端
          </h3>
          <div className="row wrap" style={{ gap: 10 }}>
            <input
              value={newKey}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewKey(e.target.value)
              }
              placeholder="Client Key"
              style={{ flex: "1 1 180px" }}
            />
            <input
              value={newName}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewName(e.target.value)
              }
              placeholder="显示名称"
              style={{ flex: "1 1 180px" }}
            />
            <input
              value={newCommand}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setNewCommand(e.target.value)
              }
              placeholder="命令 (e.g. npx)"
              style={{ flex: "1 1 150px" }}
            />
            <button onClick={onCreate}>
              <Plus size={15} />
              创建
            </button>
          </div>
        </div>
      )}

      {!loaded && clients.length === 0 && (
        <EmptyState
          icon={<Cable size={28} />}
          title="加载 MCP 客户端"
          description="管理 Agent 的外部工具和服务连接"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      <div className="card-list animate-list">
        {clients.map((item: McpClientItem) => (
          <div key={item.key} className="data-row">
            <div className="data-row-info">
              <div className="data-row-title">
                <Cable
                  size={14}
                  style={{ marginRight: 6, verticalAlign: "middle" }}
                />
                {item.name || item.key}
                <Badge variant={item.enabled ? "success" : "neutral"}>
                  {item.enabled ? "已启用" : "已禁用"}
                </Badge>
              </div>
              <div className="data-row-meta">
                Key: {item.key}
                <span style={{ margin: "0 6px" }}>·</span>
                Transport: {item.transport || "-"}
                {item.command && (
                  <>
                    <span style={{ margin: "0 6px" }}>·</span>
                    Cmd: {item.command}
                  </>
                )}
              </div>
            </div>
            <div className="data-row-actions">
              <Toggle
                checked={item.enabled ?? true}
                onChange={() => onToggle(item.key)}
              />
              <button
                className="btn-sm danger btn-icon"
                onClick={() => onDelete(item.key)}
                data-tooltip="删除"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
