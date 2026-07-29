import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { HistoryItem, SessionDetail } from "../domain/types";
import { TrendingUp, FolderOpen, Calendar, ArrowUp, ArrowDown, Clock } from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════════
   Review Timeline — Multi-session timeline: score changes, issue resolved/new, time between reviews
   ═══════════════════════════════════════════════════════════════════════════════ */

interface TimelineEntry {
  session: SessionDetail | HistoryItem;
  index: number;
  scoreChange: number | null;
  issueChange: number | null;
  timeSinceLast: string | null;
}

export function ReviewTimeline({ items, onSelectSession }: {
  items: HistoryItem[];
  onSelectSession: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    buildTimeline();
  }, [items]);

  async function buildTimeline() {
    setLoading(true);
    const sorted = [...items].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    const entries: TimelineEntry[] = [];

    for (let i = 0; i < sorted.length; i++) {
      const prev = i > 0 ? sorted[i - 1] : null;
      const current = sorted[i];
      const timeSinceLast = prev ? timeBetween(prev.created_at, current.created_at) : null;
      entries.push({
        session: current,
        index: i + 1,
        scoreChange: prev ? current.score - prev.score : null,
        issueChange: null, // Will be calculated if we have detail
        timeSinceLast,
      });
    }
    setTimeline(entries);
    setLoading(false);
  }

  function timeBetween(a: string, b: string): string {
    const diff = new Date(b).getTime() - new Date(a).getTime();
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h`;
    const mins = Math.floor(diff / 60000);
    return `${mins}min`;
  }

  if (timeline.length === 0) return <div className="chart-empty">{t("timeline.no_history")}</div>;
  if (timeline.length < 2) return <div className="chart-empty">{t("timeline.run_at_least_2")}</div>;

  const firstScore = timeline[0].session.score;
  const lastScore = timeline[timeline.length - 1].session.score;
  const totalChange = lastScore - firstScore;

  return (
    <div className="card review-timeline">
      <h3 className="chart-title"><TrendingUp size={16} /> {t("timeline.title")}</h3>

      {/* Summary */}
      <div className="tl-summary">
        <div className="tl-stat">
          <span className="tl-stat-value">{timeline.length}</span>
          <span className="tl-stat-label">{t("timeline.reviews")}</span>
        </div>
        <div className="tl-stat">
          <span className="tl-stat-value" style={{ color: totalChange >= 0 ? "var(--success)" : "var(--danger)" }}>
            {totalChange >= 0 ? `+${totalChange}` : totalChange}
          </span>
          <span className="tl-stat-label">{t("timeline.total_change")}</span>
        </div>
        <div className="tl-stat">
          <span className="tl-stat-value">{firstScore} → {lastScore}</span>
          <span className="tl-stat-label">{t("timeline.progression")}</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="tl-visual">
        {timeline.map((entry, idx) => {
          const isFirst = idx === 0;
          const isLast = idx === timeline.length - 1;
          const isSelected = selectedIdx === idx;
          const scorePct = Math.min((entry.session.score / 100) * 100, 100);
          const isImprovement = entry.scoreChange !== null && entry.scoreChange >= 0;
          const isDecline = entry.scoreChange !== null && entry.scoreChange < 0;

          return (
            <div key={entry.session.id}
              className={`tl-entry ${isSelected ? "selected" : ""} ${isImprovement ? "improving" : ""} ${isDecline ? "declining" : ""}`}
              onClick={() => { setSelectedIdx(idx); onSelectSession(entry.session.id); }}>
              {/* Timeline node */}
              <div className="tl-node-wrapper">
                <div className={`tl-node ${isFirst ? "first" : ""} ${isLast ? "last" : ""}`}
                  style={{ background: entry.session.score >= 80 ? "var(--success)" : entry.session.score >= 50 ? "var(--warning)" : "var(--danger)" }}>
                  <span className="tl-node-label">#{entry.index}</span>
                </div>
                {idx < timeline.length - 1 && <div className={`tl-line ${isImprovement ? "improving" : "declining"}`} />}
              </div>

              {/* Content */}
              <div className="tl-body">
                <div className="tl-header">
                  <strong className="tl-title">{entry.session.filename}</strong>
                  <span className={`badge ${entry.session.status}`}>{entry.session.status}</span>
                </div>
                <div className="tl-details">
                  <span className="tl-score" style={{ color: entry.session.score >= 80 ? "var(--success)" : entry.session.score >= 50 ? "var(--warning)" : "var(--danger)" }}>
                    {t("timeline.score")}: {entry.session.score}
                  </span>
                  <span className="tl-profile"><FolderOpen size={14} /> {entry.session.profile_id}</span>
                  <span className="tl-date"><Calendar size={14} /> {fmtDate(entry.session.created_at)}</span>
                </div>

                {/* Change indicators */}
                <div className="tl-changes">
                  {entry.scoreChange !== null && (
                    <span className={`tl-change ${isImprovement ? "positive" : "negative"}`}>
                      {isImprovement ? <ArrowUp size={14} /> : <ArrowDown size={14} />} {t("timeline.score_change")} {isImprovement ? "+" : ""}{entry.scoreChange}
                    </span>
                  )}
                  {entry.timeSinceLast && (
                    <span className="tl-time"><Clock size={14} /> {entry.timeSinceLast} {t("timeline.after_previous")}</span>
                  )}
                </div>

                {/* Progress bar */}
                <div className="tl-progress-bg">
                  <div className="tl-progress-fill" style={{ width: `${scorePct}%`, background: entry.session.score >= 80 ? "var(--success)" : entry.session.score >= 50 ? "var(--warning)" : "var(--danger)" }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {loading && <div className="loading-center"><span className="spinner" /></div>}
    </div>
  );
}

function fmtDate(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
