import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next"; import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react"; import { safeGetItem } from "../lib/storage";
import { BrandLogo } from "../components/BrandLogo";
import { AuthModal, type AuthMode } from "../components/AuthModal";
export function LandingPage() {
  const { t, i18n } = useTranslation();
  const [theme] = useState(() => (safeGetItem("theme") as "light" | "dark") || "light");
  const [authMode, setAuthMode] = useState<AuthMode | null>(null);
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);
  const features = [
    { Icon: Zap, title: t("landing.feature_ai_title"), desc: t("landing.feature_ai_desc") },
    { Icon: BarChart3, title: t("landing.feature_score_title"), desc: t("landing.feature_score_desc") },
    { Icon: BookOpen, title: t("landing.feature_pack_title"), desc: t("landing.feature_pack_desc") },
    { Icon: Wrench, title: t("landing.feature_fix_title"), desc: t("landing.feature_fix_desc") },
    { Icon: Eye, title: t("landing.feature_evidence_title"), desc: t("landing.feature_evidence_desc") },
    { Icon: Download, title: t("landing.feature_export_title"), desc: t("landing.feature_export_desc") },
  ];
  const steps = [1, 2, 3, 4, 5].map(step => ({ step, title: t(`landing.how_${step}_title`), desc: t(`landing.how_${step}_desc`) }));
  const profiles = [
    { name: t("landing.academic"), Icon: BookOpen, desc: t("landing.academic_desc") },
    { name: t("landing.business"), Icon: Briefcase, desc: t("landing.business_desc") },
    { name: t("landing.sop"), Icon: Shield, desc: t("landing.sop_desc") },
  ];
  const packs = ["APA 7", "IEEE", "ACM", "Nature", "Springer", "Elsevier", "ISO 9001", "FDA 21 CFR", "WHO"];
  const toggleLanguage = () => i18n.changeLanguage(i18n.resolvedLanguage === "vi" ? "en" : "vi");
  return (
    <div className="landing">
      <nav className="lp-navbar"><div className="lp-nav-inner"><a href="#top" className="lp-logo" aria-label={t("common.brand")}><BrandLogo responsive className="landing-brand-logo" /></a><div className="lp-nav-links"><a href="#features">{t("landing.features")}</a><a href="#how-it-works">{t("landing.how")}</a><a href="#profiles">{t("landing.profiles")}</a><a href="#architecture">{t("landing.architecture")}</a></div><div className="lp-nav-actions"><button className="theme-toggle" aria-label={t("shell.toggle_language")} onClick={toggleLanguage}>{i18n.resolvedLanguage === "vi" ? "VI" : "EN"}</button><button className="btn-sm outline" onClick={() => setAuthMode("sign-in")}>{t("landing.sign_in")}</button><button className="btn-primary" onClick={() => setAuthMode("sign-up")}>{t("landing.get_started")}</button></div></div></nav>
      <main id="top">
        <section className="lp-hero"><div className="lp-hero-bg" /><div className="lp-hero-content"><div className="lp-hero-badge"><Sparkles size={14} /> {t("landing.badge")}</div><h1 className="lp-hero-title">{t("landing.hero_line_1")}<br /><span className="lp-hero-gradient">{t("landing.hero_line_2")}</span></h1><p className="lp-hero-desc">{t("landing.hero_desc")}</p><div className="rules-counter-badge landing-pipeline">{t("landing.pipeline")}</div><div className="lp-hero-actions"><button className="btn-primary" onClick={() => setAuthMode("sign-up")}><Zap size={20} /> {t("landing.start_engine")}</button><button className="btn-secondary" onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}>{t("landing.learn_more")}</button></div><div className="lp-hero-stats"><div className="lp-stat"><strong>200+</strong> {t("landing.rules_stat")}</div><div className="lp-stat-dot" /><div className="lp-stat"><strong>10+</strong> {t("landing.packs_stat")}</div><div className="lp-stat-dot" /><div className="lp-stat"><strong>4</strong> {t("landing.profiles_stat")}</div><div className="lp-stat-dot" /><div className="lp-stat"><strong>100%</strong> {t("landing.free_stat")}</div></div></div></section>
        <section id="features" className="lp-section"><div className="lp-section-inner"><div className="section-kicker">{t("landing.features")}</div><h2 className="lp-section-title">{t("landing.features_title")} <span className="lp-gradient-text">{t("landing.features_accent")}</span></h2><p className="lp-section-sub">{t("landing.features_sub")}</p><div className="lp-features-grid">{features.map(f => <article key={f.title} className="lp-feature-card"><div className="lp-feature-icon"><f.Icon size={22} /></div><h3>{f.title}</h3><p>{f.desc}</p></article>)}</div></div></section>
        <section id="how-it-works" className="lp-section lp-section-alt"><div className="lp-section-inner"><div className="section-kicker">{t("landing.how")}</div><h2 className="lp-section-title">{t("landing.how_title")} <span className="lp-gradient-text">{t("landing.how_accent")}</span></h2><p className="lp-section-sub">{t("landing.how_sub")}</p><div className="lp-steps">{steps.map((item, index) => <article key={item.step} className="lp-step"><div className="lp-step-number">{item.step}</div><div className="lp-step-body"><h3>{item.title}</h3><p>{item.desc}</p></div>{index < steps.length - 1 && <div className="lp-step-line" />}</article>)}</div></div></section>
        <section id="profiles" className="lp-section"><div className="lp-section-inner"><div className="section-kicker">{t("landing.profiles")}</div><h2 className="lp-section-title">{t("landing.profiles_title")} <span className="lp-gradient-text">{t("landing.profiles_accent")}</span></h2><p className="lp-section-sub">{t("landing.profiles_sub")}</p><div className="lp-profiles">{profiles.map(p => <article key={p.name} className="lp-profile-card"><div className="lp-profile-icon"><p.Icon size={24} /></div><h3>{p.name}</h3><p>{p.desc}</p></article>)}</div></div></section>
        <section id="architecture" className="lp-section lp-section-alt"><div className="lp-section-inner"><div className="section-kicker">{t("landing.architecture")}</div><h2 className="lp-section-title">{t("landing.packs_title")} <span className="lp-gradient-text">{t("landing.packs_accent")}</span></h2><p className="lp-section-sub">{t("landing.packs_sub")}</p><div className="lp-packs-grid">{packs.map(pack => <div key={pack} className="lp-pack-chip"><Database size={15} /><strong>{pack}</strong></div>)}</div></div></section>
        <section className="lp-cta"><div className="lp-cta-bg" /><div className="lp-cta-content"><Sparkles size={26} /><h2>{t("landing.cta_title")}</h2><p>{t("landing.cta_desc")}</p><button className="btn-primary" onClick={() => setAuthMode("sign-up")}><ArrowRight size={18} /> {t("landing.launch")}</button></div></section>
      </main>
      <footer className="lp-footer"><div className="lp-footer-inner"><div className="lp-footer-brand"><BrandLogo className="footer-brand-logo" /><p>{t("landing.platform")}</p></div><div className="lp-footer-links"><a href="#features">{t("landing.documentation")}</a><a href="https://github.com/ViuGiaLai/reviewmind" target="_blank" rel="noreferrer">GitHub</a><a href="#">{t("landing.privacy")}</a><a href="#">{t("landing.terms")}</a></div><div className="lp-footer-copy">{t("landing.copyright", { year: new Date().getFullYear() })}</div></div></footer>
      {authMode ? <AuthModal mode={authMode} onClose={() => setAuthMode(null)} onSwitch={setAuthMode} /> : null}
    </div>
  );
}
