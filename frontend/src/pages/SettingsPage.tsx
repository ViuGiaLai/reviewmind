import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react";import { API_URL } from "../lib/config";
import type { AccountInfo } from "../domain/types";

export function SettingsView({ theme, setTheme, account, documentCount, templateCount, profileCount }: { theme: string; setTheme: (theme: "light" | "dark") => void; account: AccountInfo; documentCount: number; templateCount: number; profileCount: number; }) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language;
  return <section className="settings-page page-stack">
    <div className="page-header"><div><div className="page-eyebrow">{t("nav.configuration")}</div><h2>{t("settings.title")}</h2><p className="page-subtitle">{t("settings.subtitle")}</p></div></div>
    <div className="settings-layout">
      <div className="settings-section"><h3><Settings size={16} /> {t("settings.appearance")}</h3><div className="settings-grid">
        <div className="setting-row"><div><label>{t("settings.dark_mode")}</label><div className="setting-desc">{t("settings.dark_mode_desc")}</div></div><label className="toggle-switch"><input type="checkbox" checked={theme === "dark"} onChange={event => setTheme(event.target.checked ? "dark" : "light")} /><div className="toggle-track" /><div className="toggle-dot" /></label></div>
        <div className="setting-row"><div><label>{t("settings.language")}</label><div className="setting-desc">{t("settings.language_desc")}</div></div><select value={language.split("-")[0]} onChange={event => i18n.changeLanguage(event.target.value)}><option value="en">{t("common.english")}</option><option value="vi">{t("common.vietnamese")}</option></select></div>
      </div></div>
      <div className="settings-section"><h3><User size={16} /> {t("settings.account")}</h3><div className="settings-grid">
        <div className="setting-row"><div><label>{account.name}</label><div className="setting-desc">{account.email}</div></div><span className="private-badge"><Lock size={12} /> {t("settings.authenticated")}</span></div>
        <div className="setting-row setting-data-row"><div><label>{t("settings.private_workspace")}</label><div className="setting-desc">{t("settings.private_workspace_desc")}</div></div><div className="account-data-counts"><span>{documentCount} {t("settings.documents")}</span><span>{templateCount} {t("settings.templates")}</span><span>{profileCount} {t("settings.profiles")}</span></div></div>
      </div></div>
      <div className="settings-section"><h3><Shield size={16} /> {t("settings.system")}</h3><div className="settings-grid">
        <div className="setting-row"><div><label>{t("settings.api_endpoint")}</label><div className="setting-desc">{t("settings.api_endpoint_desc")}</div></div><code className="settings-code">{API_URL}</code></div>
        <div className="setting-row"><div><label>{t("common.brand")}</label><div className="setting-desc">{t("settings.version")}</div></div><span className="feature-state on"><CheckCircle size={12} /> {t("settings.ready")}</span></div>
      </div></div>
    </div>
  </section>;
}

