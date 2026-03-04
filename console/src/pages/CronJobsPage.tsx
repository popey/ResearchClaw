import { useState } from "react";
import { Timer, RefreshCw } from "lucide-react";
import { getCronJobs, toggleCronJob } from "../api";
import type { CronJobItem } from "../types";
import { PageHeader, EmptyState, Badge, Toggle } from "../components/ui";

export default function CronJobsPage() {
  const [jobs, setJobs] = useState<CronJobItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  async function onLoad() {
    setJobs(await getCronJobs());
    setLoaded(true);
  }

  async function onToggle(name: string, enabled: boolean) {
    await toggleCronJob(name, enabled);
    await onLoad();
  }

  return (
    <div className="panel">
      <PageHeader
        title="定时任务"
        description="管理周期性执行的自动化任务"
        actions={
          <button onClick={onLoad}>
            <RefreshCw size={15} />
            刷新任务
          </button>
        }
      />

      {!loaded && jobs.length === 0 && (
        <EmptyState
          icon={<Timer size={28} />}
          title="加载定时任务"
          description="查看和控制所有自动化定时任务"
          action={
            <button onClick={onLoad}>
              <RefreshCw size={15} />
              加载
            </button>
          }
        />
      )}

      <div className="card-list animate-list">
        {jobs.map((job: CronJobItem) => (
          <div key={job.name} className="data-row">
            <div className="data-row-info">
              <div className="data-row-title">
                <Timer
                  size={14}
                  style={{ marginRight: 6, verticalAlign: "middle" }}
                />
                {job.name}
              </div>
              <div className="data-row-meta">
                间隔: {job.interval_seconds}s
                <span style={{ margin: "0 6px" }}>·</span>
                {job.running ? (
                  <Badge variant="success">运行中</Badge>
                ) : (
                  <Badge variant="neutral">空闲</Badge>
                )}
              </div>
            </div>
            <div className="data-row-actions">
              <Toggle
                checked={job.enabled}
                onChange={(checked) => onToggle(job.name, checked)}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
