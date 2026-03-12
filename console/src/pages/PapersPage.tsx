import { useState } from "react";
import type { ChangeEvent } from "react";
import { Search, FileText, Calendar, Users, ExternalLink } from "lucide-react";
import { searchArxiv } from "../api";
import { useI18n } from "../i18n";
import type { PaperItem } from "../types";
import { PageHeader, EmptyState } from "../components/ui";

export default function PapersPage() {
  const { t } = useI18n();
  const [paperQuery, setPaperQuery] = useState(
    "large language model reasoning",
  );
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [paperLoading, setPaperLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  async function onSearchPapers() {
    if (!paperQuery.trim()) return;
    setPaperLoading(true);
    setHasSearched(true);
    try {
      const result = await searchArxiv(paperQuery);
      setPapers(result);
    } catch (error) {
      setPapers([{ title: t("检索失败: {error}", { error: String(error) }) }]);
    } finally {
      setPaperLoading(false);
    }
  }

  return (
    <div className="panel">
      <PageHeader
        title={t("论文检索")}
        description={t("从 ArXiv 搜索最新学术论文，快速了解研究动态")}
      />

      <div className="search-bar">
        <input
          value={paperQuery}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            setPaperQuery(e.target.value)
          }
          placeholder={t("输入研究主题关键词...")}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSearchPapers();
          }}
        />
        <button onClick={onSearchPapers} disabled={paperLoading}>
          <Search size={15} />
          {paperLoading ? t("检索中...") : t("检索 ArXiv")}
        </button>
      </div>

      {!hasSearched && papers.length === 0 && (
        <EmptyState
          icon={<FileText size={28} />}
          title={t("搜索学术论文")}
          description={t("输入主题或关键词，从 ArXiv 获取相关研究论文")}
        />
      )}

      {hasSearched && papers.length === 0 && !paperLoading && (
        <EmptyState
          icon={<Search size={28} />}
          title={t("未找到相关论文")}
          description={t("请尝试使用不同的关键词进行搜索")}
        />
      )}

      <div className="card-grid animate-list">
        {papers.map((paper, idx) => (
          <div key={idx} className="paper-card">
            <h3>{paper.title || "Untitled"}</h3>
            <div className="paper-meta">
              {paper.id && (
                <span className="paper-meta-item">
                  <ExternalLink size={12} />
                  {paper.id}
                </span>
              )}
              {paper.published && (
                <span className="paper-meta-item">
                  <Calendar size={12} />
                  {paper.published}
                </span>
              )}
              {paper.authors && paper.authors.length > 0 && (
                <span className="paper-meta-item">
                  <Users size={12} />
                  {t("{count} 位作者", { count: paper.authors.length })}
                </span>
              )}
            </div>
            {paper.authors && paper.authors.length > 0 && (
              <p className="text-xs muted mt-2">
                {paper.authors.slice(0, 5).join(", ")}
                {paper.authors.length > 5 && t("等")}
              </p>
            )}
            {paper.summary && (
              <p className="paper-summary mt-2">
                {paper.summary.slice(0, 300)}
                {paper.summary.length > 300 ? "..." : ""}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
