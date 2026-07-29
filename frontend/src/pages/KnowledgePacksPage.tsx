import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react"; import type { KnowledgePackItem } from "../domain/types";

export function KnowledgePacksView({ packs, onCreateProfile }: { packs: KnowledgePackItem[]; onCreateProfile: () => void }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [profileFilter, setProfileFilter] = useState("all");
  const profiles = Array.from(new Set(packs.map(pack => pack.profile).filter(Boolean))).sort();
  const filtered = packs.filter(pack => {
    const matchesProfile = profileFilter === "all" || pack.profile === profileFilter;
    const term = query.trim().toLowerCase();
    return matchesProfile && (!term || `${pack.name} ${pack.description} ${pack.id}`.toLowerCase().includes(term));
  });
  return (
    <section className="page-stack knowledge-catalog">
      <div className="page-header">
        <div><div className="page-eyebrow">{t("nav.configuration")}</div><h2>{t("packs.title")}</h2><p className="page-subtitle">{t("packs.subtitle")}</p></div>
        <button className="btn-primary" onClick={onCreateProfile}><Plus size={16} /> {t("packs.use_in_profile")}</button>
      </div>
      <div className="profile-principle"><BookOpen size={20} /><div><strong>{t("packs.catalog_title")}</strong><p>{t("packs.catalog_desc")}</p></div></div>
      <div className="catalog-toolbar card">
        <label><Search size={15} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder={t("packs.search_placeholder")} /></label>
        <select value={profileFilter} onChange={event => setProfileFilter(event.target.value)}>
          <option value="all">{t("packs.all_profiles")}</option>
          {profiles.map(profile => <option key={profile} value={profile}>{profile.replaceAll("_", " ")}</option>)}
        </select>
        <span>{t("packs.count", { count: filtered.length })}</span>
      </div>
      {filtered.length === 0 ? (
        <div className="empty-state"><BookOpen size={38} /><h3>{t("packs.empty_title")}</h3><p>{t("packs.empty_desc")}</p></div>
      ) : (
        <div className="knowledge-pack-grid">
          {filtered.map(pack => (
            <article className="knowledge-pack-card" key={pack.id}>
              <div className="kp-head"><div className="kp-icon"><Database size={19} /></div><div><strong>{pack.name}</strong><span>{pack.id} · v{pack.version || "1.0.0"}</span></div><span className="kp-profile">{pack.profile || t("packs.general")}</span></div>
              <p>{pack.description || t("packs.no_description")}</p>
              <div className="selectable-chips compact">{(pack.categories || []).map(category => <span key={category}>{category.replaceAll("_", " ")}</span>)}</div>
              <div className="kp-metrics">
                <span><ShieldCheck size={13} /> {t("packs.capabilities", { count: pack.capability_count || 0 })}</span>
                <span><Layers3 size={13} /> {t("packs.dependencies", { count: pack.required_packs?.length || 0 })}</span>
              </div>
              {!!pack.incompatible_packs?.length && <div className="kp-warning"><AlertTriangle size={13} /> {t("packs.incompatible", { packs: pack.incompatible_packs.join(", ") })}</div>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

