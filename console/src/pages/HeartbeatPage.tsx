import { useState } from "react";
import { Heart, RefreshCw } from "lucide-react";
import { getHeartbeat } from "../api";
import { PageHeader, EmptyState } from "../components/ui";

export default function HeartbeatPage() {
  const [heartbeat, setHeartbeat] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setHeartbeat(await getHeartbeat());
    setLoaded(true);
  }

  return (
    <div className="panel">
      <PageHeader
        title="心跳检测"
        description="查看各组件的心跳状态"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新心跳
          </button>
        }
      />

      {!loaded && !heartbeat && (
        <EmptyState
          icon={<Heart size={28} />}
          title="检测系统心跳"
          description="点击刷新查看各组件的实时状态"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      {heartbeat && (
        <pre className="pre">{JSON.stringify(heartbeat, null, 2)}</pre>
      )}
    </div>
  );
}
