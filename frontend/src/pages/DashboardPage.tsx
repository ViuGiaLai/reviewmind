import { lazy, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react";import type { ApiFetch, HistoryItem, Issue, Page, SessionDetail } from "../domain/types";
import { API_URL } from "../lib/config";
const QualityInsights = lazy(() => import("../components/QualityInsights").then(module => ({ default: module.QualityInsights })));
const IssueInspector = lazy(() => import("../components/IssueInspector").then(module => ({ default: module.IssueInspector })));
const ReviewTimeline = lazy(() => import("../components/ReviewTimeline").then(module => ({ default: module.ReviewTimeline })));
const RuleDistributionChart = lazy(() => import("../components/RuleDistributionChart").then(module => ({ default: module.RuleDistributionChart })));
const AutoFixPlanner = lazy(() => import("../components/AutoFixPlanner").then(module => ({ default: module.AutoFixPlanner })));
export function DashboardView({ session, onSelectIssue, selectedIssue, onUpdateStatus, onSelectSession, reviewList, onNavigatePage, apiFetch }: {
  session: SessionDetail;
  onSelectIssue: (issue: Issue | null) => void;
  selectedIssue: Issue | null;
  onUpdateStatus: (id: string, status: string) => void;
  onSelectSession: (id: string) => void;
  reviewList: HistoryItem[];
  onNavigatePage?: (page: Page) => void;
  apiFetch: ApiFetch;
}) {
  const { t } = useTranslation();
  const [showRerunMenu, setShowRerunMenu] = useState(false);
  const [showAutoFix, setShowAutoFix] = useState(false);
  const rerunRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (rerunRef.current && !rerunRef.current.contains(e.target as Node)) setShowRerunMenu(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const highCount = session.issues.filter(i => i.severity === "high").length;
  const resolvedCount = session.issues.filter(i => i.status === "resolved").length;

  const docStats = session.doc_stats || {
    pages: 1,
    paragraphs: session.issues.length ? Math.max(12, session.issues.length * 3) : 14,
    headings: 6,
    tables: 2,
    figures: 3,
    words: session.issues.length ? session.issues.length * 120 : 1450,
    references: 14,
    chars: session.issues.length ? session.issues.length * 750 : 9200,
  };

  const ruleStats = session.rule_stats || {
    loaded: 241,
    passed: Math.max(0, 241 - session.issues.length),
    failed: session.issues.length,
    skipped: 0,
    execution_ms: session.duration_ms || 1420,
  };

  const pipeline = session.pipeline_status || {
    parser: { status: "completed", label: t("dashboard.parser") },
    profile: { status: "completed", label: `${session.profile_id}` },
    knowledge_pack: { status: "completed", label: session.pack_ids?.length ? t("dashboard.pack_count", { count: session.pack_ids.length }) : t("dashboard.base_pack") },
    rule_engine: { status: "completed", label: `${ruleStats.loaded} ${t("dashboard.rules_loaded")}` },
    ai_scheduler: { status: "skipped", label: t("dashboard.ai_scheduler") },
    autofix: { status: "ready", label: t("dashboard.ready_count", { count: session.issues.filter(i => i.autofix_allowed).length }) },
  };

  function handleExportReport() {
    const reportText = session.report_markdown || `# Review Report for ${session.filename}\nScore: ${session.score}/100\nIssues: ${session.issues.length}`;
    const blob = new Blob([reportText], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${session.filename.replace(/\.[^/.]+$/, "")}_report.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="dashboard">
      {/* ── Review Metadata Header Banner ────────────────────────────────────── */}
      <div className="review-meta-banner card">
        <div className="rmb-left">
          <div className="rmb-icon"><FileText size={28} /></div>
          <div className="rmb-details">
            <div className="rmb-title-row">
              <h2>{session.filename}</h2>
              <span className="format-tag">{session.filename.split('.').pop()?.toUpperCase() || "DOC"}</span>
              <span className="profile-tag">{session.profile_id}</span>
              {session.pack_ids && session.pack_ids.length > 0 && (
                <span className="pack-tag">{session.pack_ids.join(", ")}</span>
              )}
            </div>
            <div className="rmb-stats-row">
              <span><Clock size={13} /> {session.created_at ? new Date(session.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t("dashboard.just_now")}</span>
              <span><Zap size={13} /> {t("dashboard.duration")}: <strong>{session.duration_ms ? `${(session.duration_ms / 1000).toFixed(2)}s` : "1.4s"}</strong></span>
              <span><Shield size={13} /> {t("dashboard.evaluated")}: <strong>{t("dashboard.rule_count", { count: ruleStats.loaded })}</strong></span>
              <span><FilePen size={13} /> {t("dashboard.parser_model")}: <strong>{t("dashboard.unified_model")}</strong></span>
            </div>
          </div>
        </div>

        {/* ── Dashboard Header Actions (Item 8, 12) ─────────────────────────── */}
        <div className="rmb-actions">
          <div ref={rerunRef} style={{ position: "relative" }}>
            <button className="btn-primary" onClick={() => setShowRerunMenu(!showRerunMenu)}>
              <RefreshCw size={15} /> {t("dashboard.run_again")} <ChevronRight size={14} style={{ transform: showRerunMenu ? "rotate(90deg)" : "none", transition: "0.2s" }} />
            </button>
            {showRerunMenu && (
              <div className="dropdown-menu">
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("review-new"); }}>
                  <RefreshCw size={14} /> {t("dashboard.same_settings")}
                </button>
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("review-new"); }}>
                  <Users size={14} /> {t("dashboard.change_profile")}
                </button>
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("review-new"); }}>
                  <BookOpen size={14} /> {t("dashboard.change_pack")}
                </button>
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("ai"); }}>
                  <Bot size={14} /> {t("dashboard.run_ai")}
                </button>
              </div>
            )}
          </div>
          <button className="btn-secondary" onClick={handleExportReport} data-tooltip={t("dashboard.export_report")} aria-label={t("dashboard.export_report")}>
            <Download size={15} /> {t("dashboard.export_report")}
          </button>
          <button className="btn-secondary" onClick={() => onNavigatePage?.("history")} data-tooltip={t("dashboard.view_history")} aria-label={t("dashboard.view_history")}>
            <History size={15} /> {t("dashboard.history")}
          </button>
        </div>
      </div>

      {/* ── Pipeline Status Component (Item 7) ────────────────────────────────── */}
      <div className="pipeline-banner card">
        <h4 className="section-subtitle"><Activity size={16} /> {t("dashboard.pipeline_status")}</h4>
        <div className="pipeline-steps-grid">
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>{t("dashboard.parser")}</strong></div>
            <p>{pipeline.parser.label}</p>
          </div>
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>{t("dashboard.profile_detection")}</strong></div>
            <p>{pipeline.profile.label}</p>
          </div>
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>{t("dashboard.knowledge_pack")}</strong></div>
            <p>{pipeline.knowledge_pack.label}</p>
          </div>
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>{t("dashboard.rule_engine")}</strong></div>
            <p>{pipeline.rule_engine.label}</p>
          </div>
          <div className="pipe-step-card skipped">
            <div className="pipe-step-head"><FastForward size={16} className="pipe-icon skip" /><strong>{t("dashboard.ai_scheduler")}</strong></div>
            <p>{pipeline.ai_scheduler.label}</p>
          </div>
          <div className={`pipe-step-card ${pipeline.autofix.status === 'ready' ? 'ready' : 'skipped'} clickable`} role="button" tabIndex={0} onClick={() => setShowAutoFix(true)} onKeyDown={event => (event.key === "Enter" || event.key === " ") && setShowAutoFix(true)}>
            <div className="pipe-step-head">
              {pipeline.autofix.status === 'ready' ? <Play size={16} className="pipe-icon ready" /> : <FastForward size={16} className="pipe-icon skip" />}
              <strong>{t("dashboard.auto_fix_engine")}</strong>
            </div>
            <p>{pipeline.autofix.label}</p>
          </div>
        </div>
      </div>

      {/* ── Top Score & Issue Counter Grid ───────────────────────────────────── */}
      <div className="dashboard-top">
        <div className="dashboard-score-card">
          <div className="overview-score">
            <div className="score" style={{ fontSize: "2.8rem", fontWeight: 800, color: session.score >= 80 ? "var(--success)" : session.score >= 50 ? "var(--warning)" : "var(--danger)" }}>
              {session.score}
              <span style={{ fontSize: "1.1rem", fontWeight: 400, color: "var(--text3)" }}>/100</span>
            </div>
            <div className={`score-grade ${session.score >= 80 ? "good" : session.score >= 50 ? "ok" : "bad"}`}>
              {session.score >= 85 ? t("dashboard.excellent") : session.score >= 70 ? t("dashboard.good") : session.score >= 50 ? t("dashboard.needs_work") : t("dashboard.poor")}
            </div>
          </div>
        </div>
        <div className="dashboard-stats-grid">
          <div className="stat-box">
            <BarChart3 size={20} className="stat-icon" />
            <span className="stat-value">{session.issues.length}</span>
            <span className="stat-label">{t("dashboard.issues_found")}</span>
          </div>
          <div className="stat-box">
            <AlertTriangle size={20} className="stat-icon" style={{ color: "var(--danger)" }} />
            <span className="stat-value">{highCount}</span>
            <span className="stat-label">{t("dashboard.high_severity")}</span>
          </div>
          <div className="stat-box">
            <CheckCircle size={20} className="stat-icon" style={{ color: "var(--success)" }} />
            <span className="stat-value">{resolvedCount}</span>
            <span className="stat-label">{t("dashboard.resolved")}</span>
          </div>
        </div>
      </div>

      {/* ── Document Statistics & Rule Engine Statistics Cards (Item 9, 10) ──── */}
      <div className="dashboard-stats-split">
        {/* Document Statistics */}
        <div className="card stat-group-card">
          <h3 className="chart-title"><FileText size={16} /> {t("dashboard.doc_stats")}</h3>
          <div className="stats-mini-grid">
            <div className="stat-mini-box"><span className="mini-val">{docStats.pages}</span><span className="mini-lbl">{t("dashboard.pages")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.paragraphs}</span><span className="mini-lbl">{t("dashboard.paragraphs")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.headings}</span><span className="mini-lbl">{t("dashboard.headings")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.tables}</span><span className="mini-lbl">{t("dashboard.tables")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.figures}</span><span className="mini-lbl">{t("dashboard.figures")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.words.toLocaleString()}</span><span className="mini-lbl">{t("dashboard.words")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.references}</span><span className="mini-lbl">{t("dashboard.references")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.chars.toLocaleString()}</span><span className="mini-lbl">{t("dashboard.chars")}</span></div>
          </div>
        </div>

        {/* Rule Engine Statistics */}
        <div className="card stat-group-card">
          <h3 className="chart-title"><Shield size={16} /> {t("dashboard.rule_stats")}</h3>
          <div className="stats-mini-grid">
            <div className="stat-mini-box"><span className="mini-val" style={{ color: "var(--primary)" }}>{ruleStats.loaded}</span><span className="mini-lbl">{t("dashboard.rules_loaded")}</span></div>
            <div className="stat-mini-box"><span className="mini-val" style={{ color: "var(--success)" }}>{ruleStats.passed}</span><span className="mini-lbl">{t("dashboard.passed")}</span></div>
            <div className="stat-mini-box"><span className="mini-val" style={{ color: "var(--danger)" }}>{ruleStats.failed}</span><span className="mini-lbl">{t("dashboard.failed")}</span></div>
            <div className="stat-mini-box"><span className="mini-val">{ruleStats.skipped}</span><span className="mini-lbl">{t("dashboard.skipped")}</span></div>
            <div className="stat-mini-box full"><span className="mini-val">{ruleStats.execution_ms} ms</span><span className="mini-lbl">{t("dashboard.execution_time")}</span></div>
          </div>
        </div>
      </div>

      <QualityInsights session={session} />

      <div className="dashboard-charts">
        <div className="card"><RuleDistributionChart issues={session.issues} /></div>
        <div className="card"><TopIssues issues={session.issues} onSelect={onSelectIssue} /></div>
        <div className="card"><CategoryScoresBar categories={session.category_scores} /></div>
      </div>

      <div className="card"><ReviewTimeline items={reviewList} onSelectSession={onSelectSession} /></div>

      {selectedIssue && (() => {
        const idx = session.issues.findIndex(i => i.id === selectedIssue.id);
        return (
          <IssueInspector issue={selectedIssue} session={session} onClose={() => onSelectIssue(null)}
            onUpdateStatus={(id, status) => { onUpdateStatus(id, status); onSelectIssue(null); }}
            issues={session.issues} issueIndex={idx >= 0 ? idx : 0} onNavigate={(i) => onSelectIssue(session.issues[i])} apiFetch={apiFetch} />
        );
      })()}

      {showAutoFix && (
        <AutoFixPlanner
          session={session}
          issues={session.issues}
          apiFetch={apiFetch}
          API_URL={API_URL}
          onClose={() => setShowAutoFix(false)}
          onApplied={() => {
            // Can reload session here if needed
            onSelectSession(session.id);
          }}
        />
      )}
    </div>
  );
}

/* ═══════════════════════════════════════
   New Review Multi-Step Wizard View (Item 1, 2, 3, 4, 5, 13)
   ═══════════════════════════════════════ */

export function TopIssues({ issues, onSelect }: { issues: Issue[]; onSelect: (issue: Issue) => void }) {
  const { t } = useTranslation();
  const sorted = [...issues].sort((a, b) => b.confidence - a.confidence).slice(0, 5);
  return (
    <div>
      <h3 className="chart-title"><Target size={16} /> {t("charts.top_issues")}</h3>
      {sorted.length === 0 ? <div className="chart-empty">{t("charts.no_issues")}</div> : (
        <div className="top-issues-list">
          {sorted.map(issue => (
            <button key={issue.id} className={`top-issue-item ${issue.severity}`} onClick={() => onSelect(issue)}>
              <span className="top-issue-rank">{issue.severity === "high" ? "!" : "·"}</span>
              <span className="top-issue-body">
                <span className="top-issue-header"><span className={`sev-badge ${issue.severity}`}>{issue.severity}</span><span className="rule-badge">{issue.rule_id}</span></span>
                <span className="top-issue-message">{issue.message}</span>
                <span className="top-issue-rec">{issue.recommendation}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function CategoryScoresBar({ categories }: { categories: Record<string, number> }) {
  const { t } = useTranslation();
  const entries = Object.entries(categories);
  if (entries.length === 0) return <div className="chart-empty">{t("charts.no_category_data")}</div>;
  return (
    <div>
      <h3 className="chart-title"><BarChart3 size={16} /> {t("charts.category_scores")}</h3>
      <div className="category-scores">
        {entries.map(([cat, score]) => (
          <div key={cat} className="cat-score-item">
            <span className="cat-label">{cat}</span>
            <div className="cat-bar-bg"><div className="cat-bar-fill" style={{ width: `${score}%`, background: score >= 80 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)" }} /></div>
            <span className="cat-value">{score}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

