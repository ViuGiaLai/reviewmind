import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { ApiFetch, Issue, SessionDetail } from "../domain/types";
import { DiffViewer } from "./DiffViewer";
import { FileText, Settings, Bot, Zap, ScrollText, MapPin, Ruler, Check, Slash, X, CheckCircle, CircleX, ChevronLeft, ChevronRight } from "lucide-react";

const API_URL = (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8000";

export function IssueInspector({ issue, session, onClose, onUpdateStatus, onJumpToDoc, issues, issueIndex, onNavigate, apiFetch }: {
  issue: Issue | null;
  session: SessionDetail;
  onClose: () => void;
  onUpdateStatus?: (id: string, status: string) => void;
  onJumpToDoc?: (id: string) => void;
  issues?: Issue[];
  issueIndex?: number;
  onNavigate?: (index: number) => void;
  apiFetch: ApiFetch;
}) {
  const { t, i18n } = useTranslation();
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
    { id: "evidence" as const, label: t("inspector.evidence"), Icon: FileText },
    { id: "rule" as const, label: t("inspector.rule"), Icon: Settings },
    { id: "ai" as const, label: t("inspector.ai_explain"), Icon: Bot },
    { id: "autofix" as const, label: t("inspector.autofix"), Icon: Zap },
    { id: "history" as const, label: t("inspector.history"), Icon: ScrollText },
  ];

  async function loadAiExplanation() {
    setAiLoading(true);
    try {
      const response = await apiFetch(`${API_URL}/api/issues/${iss.id}/explain`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        setAiExplanation(data.explanation || data.response || t("inspector.ai_generated"));
      } else {
        throw new Error(t("errors.api_error"));
      }
    } catch {
      setAiExplanation(t("inspector.ai_fallback", { rule: iss.rule_id, category: iss.category, confidence: iss.confidence, recommendation: iss.recommendation }));
    } finally {
      setAiLoading(false);
    }
  }

  async function loadAutoFix() {
    setFixLoading(true);
    try {
      // Fetch suggestions from the autofix engine
      const response = await apiFetch(`${API_URL}/api/sessions/${session.id}/autofix/suggestions`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        const items = data.items || [];
        // Find suggestion matching this issue
        const match = items.find((s: any) => s.issue_id === iss.id || s.rule_id === iss.rule_id);
        if (match) {
          setAutoFixSuggestion({
            original: match.original_text || iss.evidence_excerpt || t("inspector.original_text"),
            suggested: match.suggested_text || t("inspector.fixed_prefix") + (iss.evidence_excerpt || t("inspector.suggested_text")),
          });
        } else {
          throw new Error(t("errors.no_matching_suggestion"));
        }
      } else {
        throw new Error(t("errors.api_error"));
      }
    } catch {
      setAutoFixSuggestion({
        original: iss.evidence_excerpt || t("inspector.original_text"),
        suggested: t("inspector.fixed_prefix") + (iss.evidence_excerpt || t("inspector.suggested_text")),
      });
    } finally {
      setFixLoading(false);
    }
  }

  async function handleApplyFix() {
    try {
      const suggestionsResp = await apiFetch(`${API_URL}/api/sessions/${session.id}/autofix/suggestions`);
      if (!suggestionsResp.ok) throw new Error(await suggestionsResp.text());
      const suggestionsData = await suggestionsResp.json();
      const match = (suggestionsData.items || []).find((s: any) =>
        s.issue_id === iss.id || s.rule_id === iss.rule_id
      );
      if (!match) throw new Error(t("errors.no_matching_suggestion"));

      const response = await apiFetch(`${API_URL}/api/sessions/${session.id}/autofix/apply/${match.id}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error(await response.text());
      setFixApplied(true);
      onUpdateStatus?.(iss.id, "resolved");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("errors.apply_fix_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
    }
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
            {onJumpToDoc && <button className="btn-sm outline" onClick={() => onJumpToDoc(issue.id)}><FileText size={14} /> {t("inspector.jump")}</button>}
            {issue.status !== "resolved" && onUpdateStatus && <button className="btn-sm success" onClick={() => onUpdateStatus(issue.id, "resolved")}><Check size={14} /> {t("inspector.resolve")}</button>}
            {issue.status !== "ignored" && onUpdateStatus && <button className="btn-sm secondary" onClick={() => onUpdateStatus(issue.id, "ignored")}><Slash size={14} /> {t("inspector.ignore")}</button>}
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
              <h4><FileText size={14} /> {t("inspector.evidence")}</h4>
              {issue.evidence_excerpt && (
                <div className="evidence-block">
                  <blockquote className="inspector-quote">"{issue.evidence_excerpt}"</blockquote>
                  <div className="inspector-location">
                    <span><MapPin size={14} /> {issue.evidence_location}</span>
                    <span><Ruler size={14} /> {t("inspector.lines", { start: issue.evidence_line_start, end: issue.evidence_line_end })}</span>
                  </div>
                </div>
              )}
              <div className="inspector-nav">
                <button className="btn-sm outline" disabled={currentIdx <= 0} onClick={() => onNavigate?.(currentIdx - 1)}>
                  <ChevronLeft size={14} /> {t("inspector.previous")}
                </button>
                <span style={{ fontSize: ".75rem", color: "var(--text3)" }}>{t("inspector.position", { current: currentIdx + 1, total: totalIssues })}</span>
                <button className="btn-sm outline" disabled={currentIdx >= totalIssues - 1} onClick={() => onNavigate?.(currentIdx + 1)}>
                  {t("inspector.next")} <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}

          {/* Rule */}
          {activeSection === "rule" && (
            <div className="inspector-section">
              <h4><Settings size={14} /> {t("inspector.rule")}</h4>
              <table className="inspector-table">
                <tbody>
                  <tr><td>{t("inspector.rule_id")}</td><td><code>{issue.rule_id}</code></td></tr>
                  <tr><td>{t("inspector.category")}</td><td>{issue.category}</td></tr>
                  <tr><td>{t("inspector.severity")}</td><td><span className={`sev-badge ${issue.severity}`}>{issue.severity}</span></td></tr>
                  <tr><td>{t("inspector.confidence")}</td><td>{issue.confidence}%</td></tr>
                  <tr><td>{t("inspector.source")}</td><td>{issue.source}</td></tr>
                  <tr><td>{t("inspector.autofix")}</td><td>{issue.autofix_allowed === 1 ? <><CheckCircle size={14} /> {t("inspector.available")}</> : <><CircleX size={14} /> {t("inspector.not_available")}</>}</td></tr>
                </tbody>
              </table>
              <div className="inspector-rec">
                <strong>{t("inspector.recommendation")}:</strong>
                <p>{issue.recommendation}</p>
              </div>
            </div>
          )}

          {/* AI Explanation */}
          {activeSection === "ai" && (
            <div className="inspector-section">
              <h4><Bot size={14} /> {t("inspector.ai_explain")}</h4>
              {aiLoading ? (
                <div className="ai-message thinking">{[0,1,2].map(i => <div key={i} className="ai-thinking-dot" />)}</div>
              ) : aiExplanation ? (
                <div className="inspector-ai-text">{aiExplanation.split("\n").map((l, i) => <p key={i}>{l}</p>)}</div>
              ) : (
                <button className="btn-sm primary" onClick={loadAiExplanation}>{t("inspector.generate_ai")}</button>
              )}
            </div>
          )}

          {/* Auto Fix */}
          {activeSection === "autofix" && (
            <div className="inspector-section">
              <h4><Zap size={14} /> {t("inspector.autofix")}</h4>
              {fixLoading ? (
                <div className="loading-center"><span className="spinner" /></div>
              ) : autoFixSuggestion ? (
                <div>
                  <DiffViewer original={autoFixSuggestion.original} suggested={autoFixSuggestion.suggested} />
                  <div className="inspector-fix-actions" style={{ marginTop: 8 }}>
                    {!fixApplied ? (
                      <button className="btn-sm success" onClick={handleApplyFix}><Check size={14} /> {t("inspector.apply_fix")}</button>
                    ) : (
                      <span className="status-badge resolved"><CheckCircle size={12} /> {t("inspector.applied")}</span>
                    )}
                    <button className="btn-sm outline" onClick={() => setAutoFixSuggestion(null)}>{t("inspector.regenerate")}</button>
                  </div>
                </div>
              ) : (
                <button className="btn-sm primary" onClick={loadAutoFix}>{t("inspector.generate_fix")}</button>
              )}
            </div>
          )}

          {/* History */}
          {activeSection === "history" && (
            <div className="inspector-section">
              <h4><ScrollText size={14} /> {t("inspector.scan_history")}</h4>
              {scanHistory.length > 0 ? (
                <div className="inspector-scan-list">
                  {scanHistory.map((h, i) => (
                    <div key={i} className="scan-entry">
                      <strong>{t("inspector.scan_number", { number: i + 1 })}</strong> — {h.status}
                      <span style={{ color: "var(--text3)", marginLeft: 8 }}>{fmtDate(h.created_at, i18n.language)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="chart-empty">{t("inspector.no_history")}</div>
              )}
              <div className="inspector-scan-summary">
                <strong>{t("common.session")}: </strong>{session.filename}
                <span style={{ marginLeft: 16 }}><strong>{t("common.profile")}: </strong>{session.profile_id}</span>
                <span style={{ marginLeft: 16 }}><strong>{t("common.score")}: </strong>{session.score}</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="inspector-footer">
          <span className="issue-source">{t("inspector.rule_id")}: {issue.rule_id} · {t("inspector.source")}: {issue.source}</span>
          <span className="issue-source">{t("inspector.issue_id")}: {issue.id}</span>
        </div>
      </div>
    </div>
  );
}

function fmtDate(iso: string, locale: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
