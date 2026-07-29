import { useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react";import type { ReferenceTemplateItem } from "../domain/types";

export function ReferenceTemplatesView({ templates, onUpload, onDelete, onUse, isUploading }: {
  templates: ReferenceTemplateItem[];
  onUpload: (file: File) => void;
  onDelete: (id: string) => void;
  onUse: (id: string) => void;
  isUploading: boolean;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="templates-page">
      <div className="page-header templates-hero">
        <div>
          <span className="eyebrow"><Sparkles size={14} /> {t("templates.eyebrow")}</span>
          <h2>{t("templates.title")}</h2>
          <p>{t("templates.subtitle")}</p>
        </div>
        <button className="btn-primary" onClick={() => inputRef.current?.click()} disabled={isUploading}>
          {isUploading ? <Loader2 size={17} className="spin" /> : <Upload size={17} />}
          {isUploading ? t("templates.learning") : t("templates.upload")}
        </button>
        <input ref={inputRef} type="file" accept=".docx" hidden onChange={event => {
          const file = event.target.files?.[0];
          if (file) onUpload(file);
          event.target.value = "";
        }} />
      </div>

      <div className="template-policy-card card">
        <Shield size={22} />
        <div>
          <strong>{t("templates.policy_title")}</strong>
          <p>{t("templates.policy_desc")}</p>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="empty-state card template-empty">
          <FilePen size={42} />
          <h3>{t("templates.empty_title")}</h3>
          <p>{t("templates.empty_desc")}</p>
          <button className="btn-primary" onClick={() => inputRef.current?.click()}>{t("templates.upload_first")}</button>
        </div>
      ) : (
        <div className="reference-template-grid">
          {templates.map(item => {
            const body = item.analysis.body || {};
            const layout = item.analysis.layout || {};
            return (
              <article key={item.id} className="reference-template-card card">
                <div className="rtc-head">
                  <div className="rtc-icon"><FilePen size={20} /></div>
                  <div className="rtc-title"><strong title={item.original_name}>{item.original_name}</strong><span>{new Date(item.created_at).toLocaleDateString()}</span></div>
                  <button className="btn-icon danger" aria-label={t("common.delete")} onClick={() => onDelete(item.id)}><Trash2 size={16} /></button>
                </div>
                <div className="rtc-metrics">
                  <div><span>{t("templates.font")}</span><strong>{body.font_name || "—"} {body.font_size ? `${body.font_size} pt` : ""}</strong></div>
                  <div><span>{t("templates.margins")}</span><strong>{layout.margin_left_in ? `${layout.margin_left_in} in` : "—"}</strong></div>
                  <div><span>{t("templates.sections")}</span><strong>{item.analysis.required_sections?.length || 0}</strong></div>
                </div>
                <div className="rtc-sections">
                  {(item.analysis.required_sections || []).slice(0, 6).map(section => <span key={section}>{section}</span>)}
                </div>
                <div className="rtc-footer"><span><CheckCircle size={15} /> {t("templates.ready")}</span><button className="btn-sm outline" onClick={() => onUse(item.id)}><Play size={13} /> {t("templates.use_for_review")}</button></div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
