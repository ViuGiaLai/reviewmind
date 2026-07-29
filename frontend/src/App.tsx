import { lazy, startTransition, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { UserButton, useAuth, useClerk, useUser } from "@clerk/clerk-react";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type {
  AccountInfo, ApiFetch, DashboardStats, DocumentItem, EvaluationProfile, HistoryItem, Issue,
  KnowledgePackItem, Page, ReferenceTemplateItem, SessionDetail, SidebarSection
} from "./domain/types";
import { API_URL } from "./lib/config";
import { safeGetItem, safeSetItem } from "./lib/storage";
import { breadcrumb } from "./navigation";
import { BrandLogo } from "./components/BrandLogo";
import { HomeWelcomeDashboard } from "./pages/HomePage";
import { LandingPage } from "./pages/LandingPage";
const loadAssistantPage = () => import("./pages/AssistantPage");
const loadDashboardPage = () => import("./pages/DashboardPage");
const loadEvaluationProfilesModule = () => import("./components/EvaluationProfilesView");
const loadKnowledgePacksPage = () => import("./pages/KnowledgePacksPage");
const loadReferenceTemplatesPage = () => import("./pages/ReferenceTemplatesPage");
const loadReviewWizardPage = () => import("./pages/ReviewWizardPage");
const loadSettingsPage = () => import("./pages/SettingsPage");
const loadWorkspaceListsPage = () => import("./pages/WorkspaceListsPage");

const AIAssistantView = lazy(() => loadAssistantPage().then(module => ({ default: module.AIAssistantView })));
const DashboardView = lazy(() => loadDashboardPage().then(module => ({ default: module.DashboardView })));
const EvaluationProfilesView = lazy(() => loadEvaluationProfilesModule().then(module => ({ default: module.EvaluationProfilesView })));
const KnowledgePacksView = lazy(() => loadKnowledgePacksPage().then(module => ({ default: module.KnowledgePacksView })));
const ReferenceTemplatesView = lazy(() => loadReferenceTemplatesPage().then(module => ({ default: module.ReferenceTemplatesView })));
const ReviewWizardView = lazy(() => loadReviewWizardPage().then(module => ({ default: module.ReviewWizardView })));
const SettingsView = lazy(() => loadSettingsPage().then(module => ({ default: module.SettingsView })));
const DocumentsView = lazy(() => loadWorkspaceListsPage().then(module => ({ default: module.DocumentsView })));
const HistoryView = lazy(() => loadWorkspaceListsPage().then(module => ({ default: module.HistoryView })));
const ReviewsView = lazy(() => loadWorkspaceListsPage().then(module => ({ default: module.ReviewsView })));
export function App() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState<Page>("home");
  const [theme, setTheme] = useState<"light" | "dark">(() => (safeGetItem("theme") as "light" | "dark") || "dark");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [profile, setProfile] = useState("academic");
  const [result, setResult] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [reviewList, setReviewList] = useState<HistoryItem[]>([]);
  const [notifications, setNotifications] = useState<{ id: string; text: string; time: string; read: boolean }[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [templates, setTemplates] = useState<ReferenceTemplateItem[]>([]);
  const [evaluationProfiles, setEvaluationProfiles] = useState<EvaluationProfile[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [knowledgePacks, setKnowledgePacks] = useState<KnowledgePackItem[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const uploadInputRef = useRef<HTMLInputElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const requestControllerRef = useRef(new AbortController());
  const activeUserIdRef = useRef<string | null>(null);

  const { user, isLoaded, isSignedIn } = useUser();
  const { signOut } = useClerk();
  const { getToken } = useAuth();

  const apiFetch: ApiFetch = useCallback(async (url: string, options: RequestInit = {}) => {
    const scopedUserId = activeUserIdRef.current;
    const controller = requestControllerRef.current;
    const token = await getToken();
    if (!token) throw new Error("Missing authenticated session token");
    if (!scopedUserId || scopedUserId !== activeUserIdRef.current || controller.signal.aborted) {
      throw new DOMException("Account scope changed", "AbortError");
    }
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers, signal: options.signal || controller.signal });
  }, [getToken]);
  const navigate = useCallback((nextPage: Page) => {
    startTransition(() => setPage(nextPage));
  }, []);

useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    safeSetItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const nextUserId = isSignedIn && user?.id ? user.id : null;
    requestControllerRef.current.abort();
    requestControllerRef.current = new AbortController();
    activeUserIdRef.current = nextUserId;

    setReviewList([]);
    setDocuments([]);
    setTemplates([]);
    setEvaluationProfiles([]);
    setDashboardStats(null);
    setKnowledgePacks([]);
    setSelectedTemplateId(null);
    setIsUploadingTemplate(false);
    setResult(null);
    setSelectedIssue(null);
    setSelectedDocumentId(null);
    setProfile("academic");
    setShowProfileForm(false);
    setNotifications([]);
    setSearchQuery("");
    setLoading(false);
    setIsUploadingDocument(false);
    setShowNotifications(false);
    setShowProfileMenu(false);
    setPage(nextUserId ? "home" : "landing");

    if (!isLoaded || !nextUserId || !user) {
      return;
    }

    const controller = requestControllerRef.current;
    void (async () => {
      try {
        const syncPromise = apiFetch(`${API_URL}/api/auth/sync`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: user.fullName || user.username || "Reviewer",
            email: user.primaryEmailAddress?.emailAddress || "",
            avatar_url: user.imageUrl || "",
          }),
        });
        await Promise.all([syncPromise, loadReviews(), loadDocuments(), loadTemplates(), loadEvaluationProfiles(), loadDashboard(), loadKnowledgePacks()]);
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          console.error("Account data initialization failed", error);
        }
      }
    })();

    return () => controller.abort();
  }, [isLoaded, isSignedIn, user?.id]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    const preloadTimer = window.setTimeout(() => {
      void Promise.allSettled([
        loadAssistantPage(),
        loadDashboardPage(),
        loadEvaluationProfilesModule(),
        loadKnowledgePacksPage(),
        loadReferenceTemplatesPage(),
        loadReviewWizardPage(),
        loadSettingsPage(),
        loadWorkspaceListsPage(),
      ]);
    }, 250);
    return () => window.clearTimeout(preloadTimer);
  }, [isLoaded, isSignedIn]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifications(false);
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) setShowProfileMenu(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const sidebarSections = useMemo<SidebarSection[]>(() => [
    {
      label: t("nav.workspace"),
      items: [
        { id: "home", label: t("nav.home"), Icon: LayoutDashboard },
        { id: "reviews", label: t("nav.reviews"), Icon: FileText },
        { id: "documents", label: t("nav.documents"), Icon: FolderOpen },
        { id: "templates", label: t("nav.templates"), Icon: FilePen },
        { id: "history", label: t("dashboard.history"), Icon: History },
      ],
    },
    {
      label: t("nav.configuration"),
      items: [
        { id: "profiles", label: t("nav.profiles"), Icon: Users },
        { id: "kbpacks", label: t("nav.kbpacks"), Icon: BookOpen },
        { id: "ai", label: t("nav.ai"), Icon: Bot },
        { id: "settings", label: t("nav.settings"), Icon: Settings },
      ],
    },
  ], [t]);

  const filteredReviews = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase();
    return query ? reviewList.filter(item => item.filename.toLocaleLowerCase().includes(query) || item.profile_id.toLocaleLowerCase().includes(query)) : reviewList;
  }, [reviewList, searchQuery]);

  const unreadCount = useMemo(() => notifications.filter(item => !item.read).length, [notifications]);

  const authUserId = isSignedIn && user?.id ? user.id : null;
  const isChangingAccount = isLoaded && isSignedIn && activeUserIdRef.current !== authUserId;
  if (!isLoaded || isChangingAccount) {
    return <div className="app-loading" role="status" aria-label={t("common.loading")}><BrandLogo variant="mark" className="loading-brand-logo" /><Loader2 className="spin" size={18} /></div>;
  }

  if (!isSignedIn || page === "landing") {
    return <LandingPage />;
  }

  const currentUser: AccountInfo = {
    name: user?.fullName || user?.username || "Reviewer",
    email: user?.primaryEmailAddress?.emailAddress || "",
    role: "User",
  };

  function handleLogout() {
    signOut();
    setShowProfileMenu(false);
    setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: t("notifications.logout_success"), time: new Date().toLocaleTimeString(), read: false }]);
    setPage("landing");
  }



  const crumbs = breadcrumb(page, t, result?.filename);

  async function submitReview(options?: {
    profile_id?: string;
    pack_ids?: string[];
    enabled_categories?: string[];
    review_mode?: string;
    report_language?: string;
    text?: string;
    binaryFile?: File | null;
    document_id?: string | null;
    template_id?: string | null;
  }) {
    setLoading(true);
    const profId = options?.profile_id || profile;
    const packIds = options?.pack_ids || [];
    const enabledCats = options?.enabled_categories || [];
    const reviewText = options?.text || "";

    try {
      // Build request body
      const body: Record<string, any> = {
        profile_id: profId,
        pack_ids: packIds,
        review_mode: options?.review_mode || "rule_ai",
        report_language: options?.report_language || i18n.resolvedLanguage || "en",
        template_id: options?.template_id || undefined,
      };
      if (enabledCats.length > 0) {
        body.enabled_categories = enabledCats;
      }

      const docId = options?.document_id || selectedDocumentId;
      if (docId) {
        body.document_id = docId;
      } else if (reviewText) {
        body.text = reviewText;
        body.filename = "document.md";
        body.content_type = "text/markdown";
      } else {
        alert(t("errors.no_document"));
        setLoading(false);
        return;
      }

      const response = await apiFetch(`${API_URL}/api/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      const session: SessionDetail = {
        id: data.id || data.session_id || crypto.randomUUID(),
        filename: data.filename || data.document_name || "untitled",
        profile_id: profId,
        pack_ids: packIds,
        score: data.score ?? 0,
        status: data.status || "completed",
        created_at: data.created_at || new Date().toISOString(),
        category_scores: data.category_scores || {},
        issues: (data.issues || []).map((iss: any) => ({
          id: iss.id || crypto.randomUUID(),
          severity: iss.severity || "low",
          category: iss.category || "general",
          message: iss.message || "",
          recommendation: iss.recommendation || "",
          confidence: iss.confidence ?? 0,
          evidence_excerpt: iss.evidence_excerpt || iss.evidence?.excerpt || "",
          evidence_location: iss.evidence_location || iss.evidence?.location || "",
          evidence_line_start: iss.evidence_line_start ?? 0,
          evidence_line_end: iss.evidence_line_end ?? 0,
          rule_id: iss.rule_id || "unknown",
          source: iss.source || "engine",
          status: iss.status || "open",
          autofix_allowed: iss.autofix_allowed ?? 0,
          scan_history: iss.scan_history || [],
        })),
        summary: data.summary || "",
        report_markdown: data.report_markdown || "",
        duration_ms: data.duration_ms,
        doc_stats: data.doc_stats || (data.document_info ? {
          pages: data.document_info.page_count || 1,
          paragraphs: data.document_info.block_count || 1,
          headings: 0,
          tables: data.document_info.table_count || 0,
          figures: data.document_info.figure_count || 0,
          words: data.document_info.word_count || 0,
          references: 0,
          chars: data.document_info.char_count || 0,
        } : undefined),
        rule_stats: data.rule_stats,
        pipeline_status: data.pipeline_status,
        detected_profile: data.detected_profile,
        document_id: data.document_id,
      };
      setResult(session);
      const newItem: HistoryItem = { id: session.id, score: session.score, status: session.status, profile_id: profId, filename: session.filename, created_at: session.created_at, summary: session.summary };
      setReviewList(prev => [newItem, ...prev]);
      void loadDashboard();
      setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: t("notifications.review_complete", { filename: session.filename, score: session.score }), time: new Date().toLocaleString(), read: false }]);
      setPage("review-detail");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("errors.review_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
    } finally {
      setLoading(false);
    }
  }


  async function loadReviews() {
    const scopedUserId = activeUserIdRef.current;
    try {
      const response = await apiFetch(`${API_URL}/api/reviews`);
      if (response.ok) {
        const data = await response.json();
        const list = (data.reviews || data || []).map((item: any) => ({
          id: item.id || "",
          score: item.score ?? 0,
          status: item.status || "completed",
          profile_id: item.profile_id || "",
          filename: item.filename || "untitled",
          created_at: item.created_at || "",
          summary: item.summary || "",
        }));
        if (scopedUserId === activeUserIdRef.current) setReviewList(list);
      }
    } catch { }
  }

  async function loadDocuments() {
    const scopedUserId = activeUserIdRef.current;
    try {
      const response = await apiFetch(`${API_URL}/api/documents`);
      if (response.ok) {
        const data = await response.json();
        const list = (data.items || data || []).map((item: any) => ({
          id: item.id || crypto.randomUUID(),
          name: item.original_name || item.name || "untitled",
          uploaded_at: item.created_at || item.uploaded_at || new Date().toISOString(),
        }));
        if (scopedUserId === activeUserIdRef.current) setDocuments(list);
      }
    } catch { }
  }

  async function loadTemplates() {
    const scopedUserId = activeUserIdRef.current;
    try {
      const response = await apiFetch(`${API_URL}/api/templates`);
      if (response.ok) {
        const data = await response.json();
        if (scopedUserId === activeUserIdRef.current) setTemplates(data.items || []);
      }
    } catch { }
  }
  async function loadEvaluationProfiles() {
    const scopedUserId = activeUserIdRef.current;
    try {
      const response = await apiFetch(`${API_URL}/api/evaluation-profiles`);
      if (response.ok) {
        const data = await response.json();
        if (scopedUserId === activeUserIdRef.current) setEvaluationProfiles(data.items || []);
      }
    } catch { }
  }
  async function loadDashboard() {
    const scopedUserId = activeUserIdRef.current;
    try {
      const response = await apiFetch(`${API_URL}/api/dashboard`);
      if (response.ok && scopedUserId === activeUserIdRef.current) setDashboardStats(await response.json());
    } catch { }
  }

  async function loadKnowledgePacks() {
    const scopedUserId = activeUserIdRef.current;
    try {
      const response = await apiFetch(`${API_URL}/api/packs`);
      if (response.ok && scopedUserId === activeUserIdRef.current) setKnowledgePacks(await response.json());
    } catch { }
  }

  async function handleSelectReview(id: string) {
    const found = reviewList.find(r => r.id === id);
    if (!found) return;
    try {
      const response = await apiFetch(`${API_URL}/api/history/${id}`);
      if (response.ok) {
        const data = await response.json();
        const session: SessionDetail = {
          id: data.id || id,
          filename: data.filename || found.filename,
          profile_id: data.profile_id || found.profile_id,
          pack_ids: data.pack_ids || [],
          score: data.score ?? found.score,
          status: data.status || found.status,
          created_at: data.created_at || found.created_at,
          category_scores: data.category_scores || {},
          issues: (data.issues || []).map((iss: any) => ({
            id: iss.id || crypto.randomUUID(),
            severity: iss.severity || "low",
            category: iss.category || "general",
            message: iss.message || "",
            recommendation: iss.recommendation || "",
            confidence: iss.confidence ?? 0,
            evidence_excerpt: iss.evidence_excerpt || iss.evidence?.excerpt || "",
            evidence_location: iss.evidence_location || iss.evidence?.location || "",
            evidence_line_start: iss.evidence_line_start ?? 0,
            evidence_line_end: iss.evidence_line_end ?? 0,
            rule_id: iss.rule_id || "unknown",
            source: iss.source || "engine",
            status: iss.status || "open",
            autofix_allowed: iss.autofix_allowed ?? 0,
            scan_history: iss.scan_history || [],
          })),
          summary: data.summary || found.summary || "",
          report_markdown: data.report_markdown || "",
          duration_ms: data.duration_ms,
          doc_stats: data.doc_stats,
          rule_stats: data.rule_stats,
          pipeline_status: data.pipeline_status,
          detected_profile: data.detected_profile,
          document_id: data.document_id,
        };
        setResult(session);
        setPage("review-detail");
      } else {
        setResult({
          id: found.id, filename: found.filename, profile_id: found.profile_id,
          score: found.score, status: found.status, created_at: found.created_at,
          category_scores: {}, issues: [], summary: found.summary,
        });
        setPage("review-detail");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setResult({
        id: found.id, filename: found.filename, profile_id: found.profile_id,
        score: found.score, status: found.status, created_at: found.created_at,
        category_scores: {}, issues: [], summary: found.summary,
      });
      setPage("review-detail");
    }
  }

  function handleSelectSession(sessionId: string) {
    handleSelectReview(sessionId);
  }



  async function handleDocumentUpload(file: File) {
    setIsUploadingDocument(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiFetch(`${API_URL}/api/documents/upload`, {
        method: "POST",
        body: formData,
      });
      if (response.ok) {
        const data = await response.json();
        if (data.document_id) {
          setDocuments(prev => [
            { id: data.document_id, name: file.name, uploaded_at: new Date().toISOString() },
            ...prev,
          ]);
          setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: t("notifications.upload_success", { filename: file.name }), time: new Date().toLocaleString(), read: false }]);
        }
      } else {
        const errText = await response.text().catch(() => t("common.unknown_error"));
        setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: t("notifications.upload_failed", { message: errText.slice(0, 200) }), time: new Date().toLocaleString(), read: false }]);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      console.error("Upload failed:", error);
      setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: t("notifications.upload_failed", { message: t("errors.network_error") }), time: new Date().toLocaleString(), read: false }]);
    } finally {
      setIsUploadingDocument(false);
    }
  }



  async function handleTemplateUpload(file: File) {
    setIsUploadingTemplate(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiFetch(`${API_URL}/api/templates/upload`, { method: "POST", body: formData });
      if (!response.ok) throw new Error(await response.text());
      const created = await response.json();
      setTemplates(prev => [created, ...prev]);
      setSelectedTemplateId(created.id);
      setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: t("templates.upload_success", { filename: file.name }), time: new Date().toLocaleString(), read: false }]);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("templates.upload_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
    } finally {
      setIsUploadingTemplate(false);
    }
  }

  async function handleDeleteTemplate(id: string) {
    try {
      const response = await apiFetch(`${API_URL}/api/templates/${id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await response.text());
      setTemplates(prev => prev.filter(item => item.id !== id));
      if (selectedTemplateId === id) setSelectedTemplateId(null);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("templates.delete_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
    }
  }
  async function handleDeleteDocument(id: string) {
    try {
      const response = await apiFetch(`${API_URL}/api/documents/${id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await response.text());
      setDocuments(prev => prev.filter(d => d.id !== id));
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("errors.delete_document_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
    }
  }

  async function handleDeleteReview(id: string) {
    if (!window.confirm(t("history.delete_confirm"))) return;
    try {
      const response = await apiFetch(`${API_URL}/api/history/${id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await response.text());
      setReviewList(current => current.filter(item => item.id !== id));
      if (result?.id === id) { setResult(null); setSelectedIssue(null); }
      void loadDashboard();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("history.delete_error"));
    }
  }

  async function handleUpdateStatus(issueId: string, status: string) {
    if (!result) return;
    try {
      const response = await apiFetch(`${API_URL}/api/sessions/${result.id}/issues/${issueId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw new Error(await response.text());
      setResult({ ...result, issues: result.issues.map(iss => iss.id === issueId ? { ...iss, status } : iss) });
      void loadDashboard();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("errors.update_issue_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
    }
  }


  return (
    <div className="app">
      {/* Topbar */}
      <header className="app-header">
        <div className="header-left">
          <button className="btn-icon" aria-label={sidebarOpen ? t("shell.close_sidebar") : t("shell.open_sidebar")} onClick={() => setSidebarOpen(!sidebarOpen)}>
            <Menu size={20} />
          </button>
          <BrandLogo responsive className="workspace-brand-logo" />
        </div>

        {/* Breadcrumb */}
        <nav className="header-breadcrumb">
          {crumbs.map((cr, i) => (
            <span key={i} className="bc-segment">
              {i > 0 && <ChevronRight size={12} className="bc-chevron" />}
              {cr.page ? (
                <button className="bc-link" onClick={() => navigate(cr.page!)}>{cr.label}</button>
              ) : (
                <span className="bc-current">{cr.label}</span>
              )}
            </span>
          ))}
        </nav>

        <div className="header-center">
          <div className="header-search">
            <Search size={14} className="hs-icon" />
            <input type="search" className="hs-input" aria-label={t("nav.search")} placeholder={t("nav.search")} value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
            <kbd className="hs-kbd">/</kbd>
          </div>
        </div>

        <div className="header-actions">
          <button 
            className="theme-toggle" 
            onClick={() => {
              const newLang = i18n.language === "en" ? "vi" : "en";
              i18n.changeLanguage(newLang);
              localStorage.setItem("i18nextLng", newLang);
            }} 
            aria-label={t("shell.toggle_language")}
            style={{ fontSize: '0.8rem', fontWeight: 'bold' }}
          >
            {i18n.language === "en" ? "EN" : "VI"}
          </button>
          <button className="theme-toggle" aria-label={theme === "light" ? t("shell.dark_mode") : t("shell.light_mode")} onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>

          <div ref={notifRef} style={{ position: "relative" }}>
            <button className="theme-toggle" aria-label={t("shell.notifications")} onClick={() => setShowNotifications(!showNotifications)}>
              <Bell size={16} />
              {unreadCount > 0 && <span className="notif-badge">{unreadCount}</span>}
            </button>
            {showNotifications && (
              <div className="notif-dropdown">
                <div className="notif-header">
                  <strong>{t("shell.notifications")}</strong>
                  {unreadCount > 0 && <button className="btn-sm outline" onClick={() => setNotifications(prev => prev.map(n => ({ ...n, read: true })))} style={{ fontSize: ".78rem", padding: "2px 8px" }}>{t("shell.mark_all_read")}</button>}
                </div>
                {notifications.length === 0 ? (
                  <div className="notif-empty">{t("shell.no_notifications")}</div>
                ) : (
                  notifications.map(n => (
                    <div key={n.id} className={`notif-item ${n.read ? "read" : ""}`}>
                      <div className="notif-text">{n.text}</div>
                      <div className="notif-time">{n.time}</div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* User Auth Section */}
          <div style={{ position: "relative", marginLeft: 8 }} ref={profileMenuRef}>
            <button className="user-avatar" onClick={() => setShowProfileMenu(!showProfileMenu)} style={{ padding: 0, border: "none", background: "none", cursor: "pointer" }}>
              {user?.imageUrl ? (
                <img src={user.imageUrl} alt={currentUser.name} style={{ width: 32, height: 32, borderRadius: "50%", objectFit: "cover", display: "block" }} />
              ) : (
                <div className="avatar-placeholder" style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--primary)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>
                  {currentUser.name.charAt(0).toUpperCase()}
                </div>
              )}
            </button>

            {showProfileMenu && (
              <div className="profile-dropdown" style={{
                position: "absolute", top: "100%", right: 0, marginTop: 12,
                background: "var(--bg-elevated)", border: "1px solid var(--border)",
                borderRadius: 12, padding: 12, width: 280, zIndex: 100,
                boxShadow: "0 10px 25px -5px rgba(0,0,0,0.2)",
                display: "flex", flexDirection: "column", gap: 12
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, paddingBottom: 12, borderBottom: "1px solid var(--border)" }}>
                  {user?.imageUrl ? (
                    <img src={user.imageUrl} alt={currentUser.name} style={{ width: 40, height: 40, borderRadius: "50%", objectFit: "cover" }} />
                  ) : (
                    <div className="avatar-placeholder" style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--primary)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "1.2rem" }}>
                      {currentUser.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div style={{ overflow: "hidden", flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.95rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: "var(--text)" }}>{currentUser.name}</div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{currentUser.email}</div>
                  </div>
                </div>
                
                <button className="btn-secondary outline" onClick={handleLogout} style={{ width: "100%", justifyContent: "flex-start", padding: "10px 12px", border: "none" }}>
                  <LogOut size={16} /> {t("shell.sign_out")}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main */}
      <div className="app-main">
        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="workspace-sidebar">
            <div className="sidebar-nav">
              {sidebarSections.map((section, si) => (
                <div key={si}>
                  <div className="sidebar-section-title">{section.label}</div>
                  {section.items.map(item => (
                    <button key={item.id} className={`sidebar-item ${page === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}>
                      <item.Icon size={16} />
                      <span>{item.label}</span>
                    </button>
                  ))}
                  <div className="sidebar-divider" />
                </div>
              ))}
              <button className={`sidebar-item ${page === "settings" ? "active" : ""}`} onClick={() => navigate("settings")}>
                <Settings size={16} />
                <span>{t("nav.settings")}</span>
              </button>
              <div className="sidebar-divider" />
              <button className="sidebar-item sidebar-new-btn" onClick={() => navigate("review-new")}>
                <Plus size={16} />
                <span>{t("nav.new_review")}</span>
              </button>
            </div>
            {result && (
              <div className="sidebar-section">
                <div className="sidebar-section-title">{t("nav.current_review")}</div>
                <div className="ss-session-card" role="button" tabIndex={0} onClick={() => navigate("review-detail")} onKeyDown={event => (event.key === "Enter" || event.key === " ") && navigate("review-detail")}>
                  <div className="ss-file-row">
                    <FileText size={14} style={{ color: "var(--primary)" }} />
                    <span className="ss-filename" title={result.filename}>{result.filename}</span>
                  </div>
                  <div className="ss-badges-row">
                    <span className="ss-tag profile">{result.profile_id}</span>
                    {result.pack_ids && result.pack_ids.length > 0 && (
                      <span className="ss-tag pack">{result.pack_ids[0]}</span>
                    )}
                  </div>
                  <div className="ss-score-row">
                    <div className="ss-score-val" style={{ color: result.score >= 80 ? "var(--success)" : result.score >= 50 ? "var(--warning)" : "var(--danger)" }}>
                      {result.score}<small style={{ fontSize: ".7em", opacity: 0.7 }}>/100</small>
                    </div>
                    <div className="ss-meta">{result.issues.length} {t("common.issues")}</div>
                  </div>
                  <button className="btn-sm outline full-width" style={{ marginTop: 8, fontSize: ".76rem", width: "100%" }}>
                    {t("nav.open_dashboard")} <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            )}
          </aside>
        )}

        {/* Content */}
        <div className="workspace-main">
          <div className="workspace-content">
            <Suspense fallback={<div className="page-loading" role="status" aria-label={t("common.loading")}><Loader2 className="spin" size={22} /></div>}>
            {page === "home" && result ? (
              <DashboardView session={result} onSelectIssue={setSelectedIssue} selectedIssue={selectedIssue} onUpdateStatus={handleUpdateStatus} onSelectSession={handleSelectSession} reviewList={reviewList} onNavigatePage={navigate} apiFetch={apiFetch} />
            ) : page === "home" && !result ? (
              <HomeWelcomeDashboard userName={currentUser.name} onNavigate={navigate} stats={dashboardStats} />
            ) : page === "reviews" ? (
              <ReviewsView items={filteredReviews} onSelect={handleSelectReview} onDelete={handleDeleteReview} onNewReview={() => navigate("review-new")} />
            ) : page === "review-new" ? (
              <ReviewWizardView
                key={user?.id}
                storageScope={user?.id || "anonymous"}
                profile={profile}
                setProfile={setProfile}
                loading={loading}
                onSubmit={submitReview}
                documents={documents}
                selectedDocumentId={selectedDocumentId}
                setSelectedDocumentId={setSelectedDocumentId}
                apiFetch={apiFetch}
                API_URL={API_URL}
                templates={templates}
                selectedTemplateId={selectedTemplateId}
                setSelectedTemplateId={setSelectedTemplateId}
                evaluationProfiles={evaluationProfiles}
              />
            ) : page === "review-detail" && result ? (
              <DashboardView session={result} onSelectIssue={setSelectedIssue} selectedIssue={selectedIssue} onUpdateStatus={handleUpdateStatus} onSelectSession={handleSelectSession} reviewList={reviewList} onNavigatePage={navigate} apiFetch={apiFetch} />
            ) : page === "history" ? (
              <HistoryView items={filteredReviews} onSelect={handleSelectReview} onDelete={handleDeleteReview} />
            ) : page === "documents" ? (
              <DocumentsView documents={documents} onUpload={handleDocumentUpload} onDelete={handleDeleteDocument} onReview={id => { setSelectedDocumentId(id); navigate("review-new"); }} uploadInputRef={uploadInputRef} isUploading={isUploadingDocument} />
            ) : page === "templates" ? (
              <ReferenceTemplatesView templates={templates} onUpload={handleTemplateUpload} onDelete={handleDeleteTemplate} onUse={id => { setSelectedTemplateId(id); navigate("review-new"); }} isUploading={isUploadingTemplate} />
            ) : page === "profiles" ? (
              <EvaluationProfilesView profiles={evaluationProfiles} setProfiles={setEvaluationProfiles} showForm={showProfileForm} setShowForm={setShowProfileForm} apiFetch={apiFetch} apiUrl={API_URL} />
            ) : page === "kbpacks" ? (
              <KnowledgePacksView packs={knowledgePacks} onCreateProfile={() => { setShowProfileForm(true); navigate("profiles"); }} />
            ) : page === "ai" ? (
              <AIAssistantView session={result} reviews={reviewList} apiFetch={apiFetch} onSelectSession={handleSelectSession} />
            ) : page === "settings" ? (
              <SettingsView theme={theme} setTheme={setTheme} account={currentUser} documentCount={documents.length} templateCount={templates.length} profileCount={evaluationProfiles.length} />
            ) : null}
            </Suspense>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════
   Views
   ═══════════════════════════════════════ */
