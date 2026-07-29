import { useState, useEffect } from "react";
import { Issue, SessionDetail } from "../main";
import { DiffViewer } from "./DiffViewer";
import { FileText, Settings, Bot, Zap, ScrollText, MapPin, Ruler, Check, Slash, X, CheckCircle, CircleX, ChevronLeft, ChevronRight } from "lucide-react";

const API_URL = (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8000";

export function IssueInspector({ issue, session, onClose, onUpdateStatus, onJumpToDoc, issues, issueIndex, onNavigate }: {
  issue: Issue | null;
  session: SessionDetail;
  onClose: () => void;
  onUpdateStatus?: (id: string, status: string) => void;
  onJumpToDoc?: (id: string) => void;
  issues?: Issue[];
  issueIndex?: number;
  onNavigate?: (index: number) => void;
}) {
  const [activeSection, setActiveSection] = useState<"evidence" | "rule" | "ai" | "autofix" | "history">("evidence");
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [autoFixSuggestion, setAutoFixSuggestion] = useState<{ original: string; suggested: string } | null>(null);
  const [fixLoading, setFixLoading] = useState(false);
  const [fixApplied, setFixApplied] = useState(false);

  if (!issue) return null;
  const iss: Issue = issue;

  const scanHistory = iss.scan_history || [];
  const totalIssues = issues?.length || 1;
  const currentIdx = issueIndex ?? 0;

  const evidenceTabs = [
    { id: "evidence" as const, label: "Evidence", Icon: FileText },
    { id: "rule" as const, label: "Rule", Icon: Settings },
    { id: "ai" as const, label: "AI Explain", Icon: Bot },
    { id: "autofix" as const, label: "Auto Fix", Icon: Zap },
    { id: "history" as const, label: "History", Icon: ScrollText },
  ];

  async function loadAiExplanation() {
    setAiLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/ai/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: iss.rule_id,
          category: iss.category,
          message: iss.message,
          confidence: iss.confidence,
          recommendation: iss.recommendation,
          evidence_excerpt: iss.evidence_excerpt,
          session_id: session.id,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setAiExplanation(data.explanation || data.response || "AI explanation generated.");
      } else {
        throw new Error("API error");
      }
    } catch {
      setAiExplanation(
        `**Rule Analysis: ${iss.rule_id}**\n\n` +
        `This issue was flagged under the **${iss.category}** category with ${iss.confidence}% confidence.\n\n` +
        `**Why it matters:** ${iss.recommendation}\n\n` +
        `**Context:** The ${iss.category} category checks for specific patterns. ` +
        `At ${iss.confidence}% confidence, this is ${iss.confidence >= 90 ? "very likely" : "likely"} a genuine issue.`
      );
    } finally {
      setAiLoading(false);
    }
  }

  async function loadAutoFix() {
    setFixLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/ai/autofix`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: iss.rule_id,
          evidence_excerpt: iss.evidence_excerpt,
          recommendation: iss.recommendation,
          session_id: session.id,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setAutoFixSuggestion({
          original: iss.evidence_excerpt || "Original text",
          suggested: data.suggested || data.fix || "[Fixed] " + (iss.evidence_excerpt || "Suggested text"),
        });
      } else {
        throw new Error("API error");
      }
    } catch {
      setAutoFixSuggestion({
        original: iss.evidence_excerpt || "Original text",
        suggested: "[Fixed] " + (iss.evidence_excerpt || "Suggested text"),
      });
    } finally {
      setFixLoading(false);
    }
  }

  async function handleApplyFix() {
    setFixApplied(true);
    try {
      await fetch(`${API_URL}/api/ai/apply-fix`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          issue_id: iss.id,
          session_id: session.id,
          fixed_text: autoFixSuggestion?.suggested,
        }),
      });
    } catch { }
  }

  useEffect(() => { setActiveSection("evidence"); setAiExplanation(null); setAutoFixSuggestion(null); setFixApplied(false); }, [iss.id]);

  return (
    <div className="inspector-overlay" onClick={onClose}>
      <div className="inspector-panel" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="inspector-header" style={{ borderLeft: `4px solid ${issue.severity === "high" ? "var(--danger)" : issue.severity === "medium" ? "var(--warning)" : "var(--info)"}` }}>
          <div className="inspector-header-left">
            <span className={`sev-badge ${issue.severity}`}>{issue.severity}</span>
            <div>
              <h3 className="inspector-title">{issue.message}</h3>
              <div className="inspector-meta">
                <span className="cat-badge">{issue.category}</span>
                <span className="rule-badge">{issue.rule_id}</span>
                <span className="conf-badge">{issue.confidence}%</span>
                <span className={`status-badge ${issue.status}`}>{issue.status}</span>
              </div>
            </div>
          </div>
          <div className="inspector-header-actions">
            {onJumpToDoc && <button className="btn-sm outline" onClick={() => onJumpToDoc(issue.id)}><FileText size={14} /> Jump</button>}
            {issue.status !== "resolved" && onUpdateStatus && <button className="btn-sm success" onClick={() => onUpdateStatus(issue.id, "resolved")}><Check size={14} /> Resolve</button>}
            {issue.status !== "ignored" && onUpdateStatus && <button className="btn-sm secondary" onClick={() => onUpdateStatus(issue.id, "ignored")}><Slash size={14} /> Ignore</button>}
            <button className="modal-close" onClick={onClose}><X size={16} /></button>
          </div>
        </div>

        {/* Tabs */}
        <div className="inspector-tabs">
          {evidenceTabs.map(tab => (
            <button key={tab.id}
              className={`inspector-tab ${activeSection === tab.id ? "active" : ""}`}
              onClick={() => {
                setActiveSection(tab.id);
                if (tab.id === "ai" && !aiExplanation && !aiLoading) loadAiExplanation();
                if (tab.id === "autofix" && !autoFixSuggestion && !fixLoading) loadAutoFix();
              }}>
              <tab.Icon size={14} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="inspector-content">
          {/* Evidence */}
          {activeSection === "evidence" && (
            <div className="inspector-section">
              <h4><FileText size={14} /> Evidence</h4>
              {issue.evidence_excerpt && (
                <div className="evidence-block">
                  <blockquote className="inspector-quote">"{issue.evidence_excerpt}"</blockquote>
                  <div className="inspector-location">
                    <span><MapPin size={14} /> {issue.evidence_location}</span>
                    <span><Ruler size={14} /> Lines {issue.evidence_line_start}–{issue.evidence_line_end}</span>
                  </div>
                </div>
              )}
              <div className="inspector-nav">
                <button className="btn-sm outline" disabled={currentIdx <= 0} onClick={() => onNavigate?.(currentIdx - 1)}>
                  <ChevronLeft size={14} /> Previous
                </button>
                <span style={{ fontSize: ".75rem", color: "var(--text3)" }}>{currentIdx + 1} of {totalIssues}</span>
                <button className="btn-sm outline" disabled={currentIdx >= totalIssues - 1} onClick={() => onNavigate?.(currentIdx + 1)}>
                  Next <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}

          {/* Rule */}
          {activeSection === "rule" && (
            <div className="inspector-section">
              <h4><Settings size={14} /> Rule Information</h4>
              <table className="inspector-table">
                <tbody>
                  <tr><td>Rule ID</td><td><code>{issue.rule_id}</code></td></tr>
                  <tr><td>Category</td><td>{issue.category}</td></tr>
                  <tr><td>Severity</td><td><span className={`sev-badge ${issue.severity}`}>{issue.severity}</span></td></tr>
                  <tr><td>Confidence</td><td>{issue.confidence}%</td></tr>
                  <tr><td>Source</td><td>{issue.source}</td></tr>
                  <tr><td>Auto-fix</td><td>{issue.autofix_allowed === 1 ? <><CheckCircle size={14} /> Available</> : <><CircleX size={14} /> Not available</>}</td></tr>
                </tbody>
              </table>
              <div className="inspector-rec">
                <strong>Recommendation:</strong>
                <p>{issue.recommendation}</p>
              </div>
            </div>
          )}

          {/* AI Explanation */}
          {activeSection === "ai" && (
            <div className="inspector-section">
              <h4><Bot size={14} /> AI Explanation</h4>
              {aiLoading ? (
                <div className="ai-message thinking">{[0,1,2].map(i => <div key={i} className="ai-thinking-dot" />)}</div>
              ) : aiExplanation ? (
                <div className="inspector-ai-text">{aiExplanation.split("\n").map((l, i) => <p key={i}>{l}</p>)}</div>
              ) : (
                <button className="btn-sm primary" onClick={loadAiExplanation}>Generate AI Explanation</button>
              )}
            </div>
          )}

          {/* Auto Fix */}
          {activeSection === "autofix" && (
            <div className="inspector-section">
              <h4><Zap size={14} /> Auto Fix</h4>
              {fixLoading ? (
                <div className="loading-center"><span className="spinner" /></div>
              ) : autoFixSuggestion ? (
                <div>
                  <DiffViewer original={autoFixSuggestion.original} suggested={autoFixSuggestion.suggested} />
                  <div className="inspector-fix-actions" style={{ marginTop: 8 }}>
                    {!fixApplied ? (
                      <button className="btn-sm success" onClick={handleApplyFix}><Check size={14} /> Apply Fix</button>
                    ) : (
                      <span className="status-badge resolved"><CheckCircle size={12} /> Applied</span>
                    )}
                    <button className="btn-sm outline" onClick={() => setAutoFixSuggestion(null)}>Regenerate</button>
                  </div>
                </div>
              ) : (
                <button className="btn-sm primary" onClick={loadAutoFix}>Generate Fix</button>
              )}
            </div>
          )}

          {/* History */}
          {activeSection === "history" && (
            <div className="inspector-section">
              <h4><ScrollText size={14} /> Issue History</h4>
              {scanHistory.length > 0 ? (
                <div className="inspector-scan-list">
                  {scanHistory.map((h, i) => (
                    <div key={i} className="scan-entry">
                      <strong>Scan #{i + 1}</strong> — {h.status}
                      <span style={{ color: "var(--text3)", marginLeft: 8 }}>{fmtDate(h.created_at)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="chart-empty">No scan history available for this issue.</div>
              )}
              <div className="inspector-scan-summary">
                <strong>Session: </strong>{session.filename}
                <span style={{ marginLeft: 16 }}><strong>Profile: </strong>{session.profile_id}</span>
                <span style={{ marginLeft: 16 }}><strong>Score: </strong>{session.score}</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="inspector-footer">
          <span className="issue-source">Rule: {issue.rule_id} · Source: {issue.source}</span>
          <span className="issue-source">Issue ID: {issue.id}</span>
        </div>
      </div>
    </div>
  );
}

function fmtDate(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
