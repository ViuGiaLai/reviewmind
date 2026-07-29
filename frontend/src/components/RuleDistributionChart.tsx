import { Issue } from "../main";
import { BarChart3, Search, Target } from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════════
   Rule Distribution Chart — Shows which rules fire most frequently
   ═══════════════════════════════════════════════════════════════════════════════ */

export function RuleDistributionChart({ issues }: { issues: Issue[] }) {
  // Count by rule_id
  const ruleCounts: Record<string, { count: number; category: string; severity: string }> = {};
  issues.forEach(issue => {
    if (!ruleCounts[issue.rule_id]) {
      ruleCounts[issue.rule_id] = { count: 0, category: issue.category, severity: issue.severity };
    }
    ruleCounts[issue.rule_id].count++;
  });

  const items = Object.entries(ruleCounts)
    .map(([rule, data]) => ({ rule, ...data }))
    .sort((a, b) => b.count - a.count);

  const maxCount = Math.max(...items.map(i => i.count), 1);
  const colors = ["var(--danger)", "var(--warning)", "var(--primary)", "var(--info)", "var(--success)", "#8b5cf6", "#ec4899"];

  if (items.length === 0) return <div className="chart-empty">No rule data</div>;

  return (
    <div className="card rule-dist-chart">
      <h3 className="chart-title"><BarChart3 size={16} /> Rule Distribution</h3>

      {/* Horizontal bar chart */}
      <div className="rdc-list">
        {items.map((item, idx) => (
          <div key={item.rule} className="rdc-item">
            <div className="rdc-header">
              <span className="rdc-rank">#{idx + 1}</span>
              <code className="rdc-rule-id">{item.rule}</code>
              <span className="cat-badge">{item.category}</span>
              <span className={`sev-badge ${item.severity}`}>{item.severity}</span>
              <span className="rdc-count">{item.count}x</span>
            </div>
            <div className="rdc-bar-bg">
              <div
                className="rdc-bar-fill"
                style={{
                  width: `${(item.count / maxCount) * 100}%`,
                  background: colors[idx % colors.length],
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="rdc-summary">
        <span><Search size={14} /> {items.length} unique rules triggered</span>
        <span><BarChart3 size={14} /> {issues.length} total issues</span>
        <span><Target size={14} /> Most active: <strong>{items[0]?.rule}</strong> ({items[0]?.count}x)</span>
      </div>
    </div>
  );
}
