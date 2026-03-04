import { useState } from "react";
import { Server, RefreshCw, Cpu, Globe } from "lucide-react";
import { listProviders, listAvailableModels } from "../api";
import { PageHeader, EmptyState, Badge } from "../components/ui";

export default function ModelsPage() {
  const [providers, setProviders] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setProviders(await listProviders());
    setModels(await listAvailableModels());
    setLoaded(true);
  }

  return (
    <div className="panel">
      <PageHeader
        title="模型设置"
        description="查看已配置的模型供应商和可用模型"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新
          </button>
        }
      />

      {!loaded && (
        <EmptyState
          icon={<Cpu size={28} />}
          title="加载模型信息"
          description="查看所有配置的 LLM 供应商和可用模型"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      {loaded && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            <Server
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            供应商
          </h3>
          <div className="card-grid animate-list mb-4">
            {providers.map((provider, idx) => (
              <div key={idx} className="card">
                <h3>{provider.name || provider.id || "-"}</h3>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    marginBottom: 8,
                  }}
                >
                  <Badge variant="info">
                    {provider.provider_type || provider.type || "-"}
                  </Badge>
                  {provider.model_name && (
                    <Badge variant="neutral">{provider.model_name}</Badge>
                  )}
                </div>
                {provider.base_url && (
                  <div className="data-row-meta">
                    <Globe
                      size={11}
                      style={{ marginRight: 4, verticalAlign: "middle" }}
                    />
                    {provider.base_url}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="divider" />

          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            <Cpu
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            可用模型
          </h3>
          <div className="card-list animate-list">
            {models.map((model, idx) => (
              <div key={idx} className="data-row">
                <div className="data-row-info">
                  <div className="data-row-title">
                    {model.name || model.model_name || "-"}
                  </div>
                </div>
                <div className="data-row-actions">
                  <Badge variant="neutral">{model.provider || "-"}</Badge>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
