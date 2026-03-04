import { useState } from "react";
import type { ChangeEvent } from "react";
import { KeyRound, Download, Save, RefreshCw } from "lucide-react";
import { listEnvVars, saveEnvVars } from "../api";
import { PageHeader, EmptyState } from "../components/ui";

export default function EnvironmentsPage() {
  const [text, setText] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  async function onLoad() {
    const envs = await listEnvVars();
    const lines = envs.map((item) => `${item.key}=${item.value}`);
    setText(lines.join("\n"));
    setLoaded(true);
  }

  async function onSave() {
    setSaving(true);
    try {
      const vars: Record<string, string> = {};
      for (const line of text.split("\n")) {
        if (!line.trim()) continue;
        const idx = line.indexOf("=");
        if (idx <= 0) continue;
        const key = line.slice(0, idx).trim();
        const value = line.slice(idx + 1);
        vars[key] = value;
      }
      await saveEnvVars(vars);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="panel">
      <PageHeader
        title="环境变量"
        description="管理 API 密钥和环境配置参数"
        actions={
          <div className="row">
            <button className="btn-secondary" onClick={onLoad}>
              <Download size={15} />
              加载
            </button>
            <button onClick={onSave} disabled={saving}>
              <Save size={15} />
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        }
      />

      {!loaded && (
        <EmptyState
          icon={<KeyRound size={28} />}
          title="加载环境变量"
          description="管理 API 密钥、模型配置等环境变量"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      {loaded && (
        <textarea
          value={text}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
            setText(e.target.value)
          }
          rows={16}
          className="textarea"
          placeholder="OPENAI_API_KEY=sk-..."
        />
      )}
    </div>
  );
}
