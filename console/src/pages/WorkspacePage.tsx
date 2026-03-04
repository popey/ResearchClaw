import { useState } from "react";
import { FolderOpen, RefreshCw, FileText } from "lucide-react";
import { getWorkspaceInfo, getWorkspaceProfile } from "../api";
import { PageHeader, EmptyState } from "../components/ui";

export default function WorkspacePage() {
  const [workspace, setWorkspace] = useState<any>(null);
  const [profile, setProfile] = useState<{
    exists: boolean;
    content: string;
    path?: string;
  } | null>(null);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setWorkspace(await getWorkspaceInfo());
    setProfile(await getWorkspaceProfile());
    setLoaded(true);
  }

  return (
    <div className="panel">
      <PageHeader
        title="工作区"
        description="查看当前工作区信息和 PROFILE 配置"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新工作区
          </button>
        }
      />

      {!loaded && (
        <EmptyState
          icon={<FolderOpen size={28} />}
          title="加载工作区信息"
          description="查看工作目录和 PROFILE 配置文件"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      {workspace && (
        <div className="card mb-4">
          <h3>
            <FolderOpen
              size={14}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            工作区信息
          </h3>
          <pre className="pre">{JSON.stringify(workspace, null, 2)}</pre>
        </div>
      )}

      {profile && (
        <div className="card">
          <h3>
            <FileText
              size={14}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            PROFILE.md
          </h3>
          {!profile.exists ? (
            <p className="muted mt-2">未找到 PROFILE.md 配置文件</p>
          ) : (
            <pre className="pre">{profile.content}</pre>
          )}
        </div>
      )}
    </div>
  );
}
