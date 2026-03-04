import { useState } from "react";
import type { ChangeEvent } from "react";
import { Settings, Download, Save, SlidersHorizontal } from "lucide-react";
import { getAgentRunningConfig, updateAgentRunningConfig } from "../api";
import type { AgentRunningConfig } from "../types";
import { PageHeader } from "../components/ui";

export default function AgentConfigPage() {
  const [config, setConfig] = useState<AgentRunningConfig>({
    max_iters: 50,
    max_input_length: 128000,
  });
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  async function onLoad() {
    setConfig(await getAgentRunningConfig());
    setLoaded(true);
  }

  async function onSave() {
    setSaving(true);
    try {
      await updateAgentRunningConfig(config);
      await onLoad();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="panel">
      <PageHeader
        title="Agent 配置"
        description="调整 Agent 的运行参数"
        actions={
          <div className="row">
            <button className="btn-secondary" onClick={onLoad}>
              <Download size={15} />
              {loaded ? "重新加载" : "加载配置"}
            </button>
            <button onClick={onSave} disabled={saving}>
              <Save size={15} />
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        }
      />

      {!loaded ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <Settings size={28} />
          </div>
          <h3>加载 Agent 配置</h3>
          <p>点击上方加载按钮获取当前配置</p>
          <div className="mt-3">
            <button onClick={onLoad}>
              <Download size={15} />
              加载
            </button>
          </div>
        </div>
      ) : (
        <div className="card-grid">
          <div className="config-card">
            <div className="config-label">
              <SlidersHorizontal
                size={14}
                style={{ marginRight: 6, verticalAlign: "middle" }}
              />
              最大迭代次数
            </div>
            <div className="config-desc">Agent 单次任务的最大推理步数</div>
            <input
              type="number"
              value={config.max_iters}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setConfig((prev: AgentRunningConfig) => ({
                  ...prev,
                  max_iters: Number(e.target.value) || 1,
                }))
              }
            />
          </div>
          <div className="config-card">
            <div className="config-label">
              <SlidersHorizontal
                size={14}
                style={{ marginRight: 6, verticalAlign: "middle" }}
              />
              最大输入长度
            </div>
            <div className="config-desc">单次输入的最大 token 数量</div>
            <input
              type="number"
              value={config.max_input_length}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setConfig((prev: AgentRunningConfig) => ({
                  ...prev,
                  max_input_length: Number(e.target.value) || 1000,
                }))
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}
