import { Issue, SessionDetail } from "../main";
import { Lightbulb, Star, ThumbsUp, Wrench, CircleX, ClipboardList, Target, AlertTriangle, Zap } from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════════
   Quality Insights — Biến dashboard thành trung tâm cải thiện tài liệu
   ═══════════════════════════════════════════════════════════════════════════════ */

export function QualityInsights({ session }: { session: SessionDetail }) {
  const catScores = Object.entries(session.category_scores || {});
  if (catScores.length === 0) return null;

  const sorted = [...catScores].sort((a, b) => a[1] - b[1]);
  const weakest = sorted[0];
  const strongest = sorted[sorted.length - 1];
  const avgScore = session.score;

  // Estimate time to reach 95+
  const gap = 95 - avgScore;
  const issuesPerPoint = session.issues.length / Math.max(avgScore, 1);
  const estimatedIssuesToFix = Math.round(gap * issuesPerPoint * 0.6);
  const estimatedMinutes = Math.max(5, Math.round(estimatedIssuesToFix * 2.5));

  // Recommended fix order: weakest categories first
  const fixOrder = sorted.map(([cat, score]) => ({
    category: cat,
    score,
    priority: score < 60 ? "high" : score < 80 ? "medium" : "low",
    impact: Math.round((95 - score) / 5),
  }));

  return (
    <div className="card quality-insights">
      <h3 className="chart-title"><Lightbulb size={16} /> Quality Insights</h3>

      <div className="qi-grid">
        {/* Overall Assessment */}
        <div className="qi-card qi-main">
          <div className="qi-big-score">
            <span className="qi-score-number" style={{ color: avgScore >= 80 ? "var(--success)" : avgScore >= 50 ? "var(--warning)" : "var(--danger)" }}>
              {avgScore}
            </span>
            <span className="qi-score-total">/100</span>
          </div>
          <div className="qi-assessment">
            {avgScore >= 85 ? <><Star size={14} /> Excellent quality!</> : avgScore >= 70 ? <><ThumbsUp size={14} /> Good, room for improvement</> : avgScore >= 50 ? <><Wrench size={14} /> Needs significant work</> : <><CircleX size={14} /> Major issues to address</>}
          </div>
        </div>

        {/* Weakest Area */}
        <div className="qi-card qi-weak">
          <div className="qi-label">Weakest Area</div>
          <div className="qi-value">{weakest[0]}</div>
          <div className="qi-sub">
            Score: <strong style={{ color: "var(--danger)" }}>{weakest[1]}</strong>
            <span className="qi-impact"> — Fixing this could +{Math.round((95 - weakest[1]) / 5)} pts</span>
          </div>
        </div>

        {/* Strongest Area */}
        <div className="qi-card qi-strong">
          <div className="qi-label">Strongest Area</div>
          <div className="qi-value">{strongest[0]}</div>
          <div className="qi-sub">
            Score: <strong style={{ color: "var(--success)" }}>{strongest[1]}</strong>
          </div>
        </div>

        {/* ETA to 95+ */}
        <div className="qi-card qi-eta">
          <div className="qi-label">Estimated to reach <strong>95+</strong></div>
          <div className="qi-value qi-eta-value">
            <span className="qi-eta-number">{estimatedMinutes}</span>
            <span className="qi-eta-unit">minutes</span>
          </div>
          <div className="qi-sub">
            ~{estimatedIssuesToFix} key issues to fix (gap: {gap} pts)
          </div>
        </div>
      </div>

      {/* Recommended Fix Order */}
      <h4 className="qi-fix-title"><ClipboardList size={16} /> Recommended Fix Order</h4>
      <div className="qi-fix-list">
        {fixOrder.map((item, idx) => (
          <div key={item.category} className={`qi-fix-item ${item.priority}`}>
            <span className="qi-fix-rank">#{idx + 1}</span>
            <span className="qi-fix-category">{item.category}</span>
            <div className="qi-fix-bar-bg">
              <div
                className="qi-fix-bar-fill"
                style={{
                  width: `${item.score}%`,
                  background: item.score >= 80 ? "var(--success)" : item.score >= 50 ? "var(--warning)" : "var(--danger)",
                }}
              />
            </div>
            <span className="qi-fix-score">{item.score}</span>
            <span className="qi-fix-impact">+{item.impact} pts</span>
          </div>
        ))}
      </div>

      {/* Tips */}
      <div className="qi-tips">
        {weakest[1] < 60 && (
          <div className="qi-tip"><Target size={14} /> Focus on <strong>{weakest[0]}</strong> first — it has the highest improvement potential.</div>
        )}
        {session.issues.filter(i => i.severity === "high").length > 0 && (
          <div className="qi-tip"><AlertTriangle size={14} /> Fix {session.issues.filter(i => i.severity === "high").length} HIGH severity issues immediately.</div>
        )}
        <div className="qi-tip"><Zap size={14} /> Your strongest area is <strong>{strongest[0]}</strong> ({strongest[1]} pts). Maintain this quality.</div>
      </div>
    </div>
  );
}
