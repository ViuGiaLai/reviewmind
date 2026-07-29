import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react"; import type { DashboardStats, Page } from "../domain/types";

export function HomeWelcomeDashboard({ userName, onNavigate, stats }: { userName: string; onNavigate: (page: Page) => void; stats: DashboardStats | null }) {
  const { t } = useTranslation();
  return (
    <div className="home-welcome-dashboard">
      <div className="welcome-hero-card card">
        <div className="whc-content">
          <div className="whc-badge"><Sparkles size={14} /> {t("home.eyebrow")}</div>
          <h2>{t("home.welcome", { name: userName })}</h2>
          <p>{t("home.subtitle")}</p>
          <div className="whc-actions">
            <button className="btn-primary" style={{ padding: "12px 24px" }} onClick={() => onNavigate("review-new")}>
              <Zap size={18} /> {t("home.start")}
            </button>
            <button className="btn-secondary" style={{ padding: "12px 24px" }} onClick={() => onNavigate("documents")}>
              <FolderOpen size={18} /> {t("home.vault")}
            </button>
          </div>
        </div>
      </div>

      <div className="dashboard-stats-grid home-stats-grid">
        <div className="stat-box"><FileText size={18} className="stat-icon" /><span className="stat-value">{stats?.total_reviews || 0}</span><span className="stat-label">{t("home.total_reviews")}</span></div>
        <div className="stat-box"><BarChart3 size={18} className="stat-icon" /><span className="stat-value">{stats?.average_score || 0}</span><span className="stat-label">{t("home.average_score")}</span></div>
        <div className="stat-box"><AlertCircle size={18} className="stat-icon" /><span className="stat-value">{stats?.open_issues || 0}</span><span className="stat-label">{t("home.open_issues")}</span></div>
        <div className="stat-box"><CheckCircle size={18} className="stat-icon" /><span className="stat-value">{stats?.resolved_issues || 0}</span><span className="stat-label">{t("home.resolved_issues")}</span></div>
      </div>

      <div className="welcome-quick-grid">
        <div className="card action-tile" role="button" tabIndex={0} onClick={() => onNavigate("review-new")} onKeyDown={event => (event.key === "Enter" || event.key === " ") && onNavigate("review-new")}>
          <div className="tile-icon primary"><Zap size={22} /></div>
          <strong>{t("home.new_title")}</strong>
          <p>{t("home.new_desc")}</p>
          <span className="tile-link">{t("home.new_link")} <ArrowRight size={13} /></span>
        </div>
        <div className="card action-tile" role="button" tabIndex={0} onClick={() => onNavigate("profiles")} onKeyDown={event => (event.key === "Enter" || event.key === " ") && onNavigate("profiles")}>
          <div className="tile-icon success"><Users size={22} /></div>
          <strong>{t("home.profiles_title")}</strong>
          <p>{t("home.profiles_desc")}</p>
          <span className="tile-link">{t("home.profiles_link")} <ArrowRight size={13} /></span>
        </div>
        <div className="card action-tile" role="button" tabIndex={0} onClick={() => onNavigate("kbpacks")} onKeyDown={event => (event.key === "Enter" || event.key === " ") && onNavigate("kbpacks")}>
          <div className="tile-icon warning"><BookOpen size={22} /></div>
          <strong>{t("home.packs_title")}</strong>
          <p>{t("home.packs_desc")}</p>
          <span className="tile-link">{t("home.packs_link")} <ArrowRight size={13} /></span>
        </div>
        <div className="card action-tile" role="button" tabIndex={0} onClick={() => onNavigate("ai")} onKeyDown={event => (event.key === "Enter" || event.key === " ") && onNavigate("ai")}>
          <div className="tile-icon info"><Bot size={22} /></div>
          <strong>{t("home.ai_title")}</strong>
          <p>{t("home.ai_desc")}</p>
          <span className="tile-link">{t("home.ai_link")} <ArrowRight size={13} /></span>
        </div>
      </div>

      <div className="card arch-philosophy-card">
        <div className="apc-header">
          <Shield size={18} style={{ color: "var(--primary)" }} />
          <strong>{t("home.pipeline_title")}</strong>
        </div>
        <div className="apc-steps">
          <div className="apc-step"><span className="apc-tag">1. {t("home.pipeline_1_title")}</span><span>{t("home.pipeline_1_desc")}</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">2. {t("home.pipeline_2_title")}</span><span>{t("home.pipeline_2_desc")}</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">3. {t("home.pipeline_3_title")}</span><span>{t("home.pipeline_3_desc")}</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">4. {t("home.pipeline_4_title")}</span><span>{t("home.pipeline_4_desc")}</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">5. {t("home.pipeline_5_title")}</span><span>{t("home.pipeline_5_desc")}</span></div>
        </div>
      </div>
    </div>
  );
}

/* Enhanced Dashboard View */
