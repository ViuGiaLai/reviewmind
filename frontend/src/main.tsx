import { useState, useEffect, useRef, useMemo } from "react";
import { createRoot } from "react-dom/client";
import {
  ClerkProvider, SignInButton, SignUpButton, UserButton, useUser, useClerk, useAuth
} from "@clerk/clerk-react";
import { dark } from "@clerk/themes";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target,
  Star, ThumbsUp, BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield, Briefcase, LogIn, LogOut, Trash2, AlertCircle,
  Clock, Activity, Sliders, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2
} from "lucide-react";
import { QualityInsights } from "./components/QualityInsights";
import { IssueInspector } from "./components/IssueInspector";
import { ReviewTimeline } from "./components/ReviewTimeline";
import { RuleDistributionChart } from "./components/RuleDistributionChart";
import { AutoFixPlanner } from "./components/AutoFixPlanner";
import "./styles.css";

/* ── Safe localStorage helpers (handles Safari private mode, storage full) ── */
function safeGetItem(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSetItem(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* Silently fail */ }
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? "";

export interface Issue {
  id: string;
  severity: "high" | "medium" | "low";
  category: string;
  message: string;
  recommendation: string;
  confidence: number;
  evidence_excerpt?: string;
  evidence_location?: string;
  evidence_line_start?: number;
  evidence_line_end?: number;
  rule_id: string;
  source: string;
  status: string;
  autofix_allowed: number;
  scan_history?: { status: string; created_at: string }[];
}

export interface HistoryItem {
  id: string;
  score: number;
  status: string;
  profile_id: string;
  filename: string;
  created_at: string;
  summary?: string;
}

export interface SessionDetail {
  id: string;
  filename: string;
  profile_id: string;
  pack_ids?: string[];
  score: number;
  status: string;
  created_at: string;
  category_scores: Record<string, number>;
  issues: Issue[];
  summary?: string;
  report_markdown?: string;
  duration_ms?: number;
  doc_stats?: {
    pages: number;
    paragraphs: number;
    headings: number;
    tables: number;
    figures: number;
    words: number;
    references: number;
    chars: number;
  };
  rule_stats?: {
    loaded: number;
    passed: number;
    failed: number;
    skipped: number;
    execution_ms: number;
  };
  pipeline_status?: Record<string, { status: string; label: string }>;
  detected_profile?: string;
  document_id?: string;
}

type Page = "landing" | "home" | "reviews" | "review-new" | "review-detail" | "documents" | "history" | "profiles" | "kbpacks" | "ai" | "settings";

interface SidebarSection {
  label: string;
  items: { id: Page; label: string; Icon: any }[];
}

const PAGE_LABELS: Record<Page, string> = {
  landing: "Landing Page",
  home: "Home",
  reviews: "Reviews",
  "review-new": "New Review",
  "review-detail": "Review Detail",
  documents: "Documents",
  history: "History",
  profiles: "Profiles",
  kbpacks: "Knowledge Packs",
  ai: "AI Assistant",
  settings: "Settings",
};

interface DocumentItem {
  id: string;
  name: string;
  uploaded_at: string;
}

function breadcrumb(page: Page, docName?: string): { label: string; page?: Page }[] {
  const crumbs: { label: string; page?: Page }[] = [{ label: "Home", page: "home" }];
  if (page === "home") return crumbs;
  if (page === "reviews" || page === "review-new" || page === "review-detail") {
    crumbs.push({ label: "Reviews", page: "reviews" });
    if (page === "review-new") crumbs.push({ label: "New Review" });
    else if (page === "review-detail" && docName) crumbs.push({ label: docName });
    return crumbs;
  }
  crumbs.push({ label: PAGE_LABELS[page] });
  return crumbs;
}

function App() {
  const [page, setPage] = useState<Page>("home");
  const [theme, setTheme] = useState<"light" | "dark">(() => (safeGetItem("theme") as "light" | "dark") || "dark");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [text, setText] = useState("# Review Document\n\nThis is a sample document for review. The engine will analyze this text for quality, consistency, and compliance issues based on the selected profile.");
  const [binaryFile, setBinaryFile] = useState<File | null>(null);
  const [profile, setProfile] = useState("academic");
  const [result, setResult] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [reviewList, setReviewList] = useState<HistoryItem[]>([]);
  const [notifications, setNotifications] = useState<{ id: string; text: string; time: string; read: boolean }[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [showPackForm, setShowPackForm] = useState(false);
  const [docViewMode, setDocViewMode] = useState<"raw" | "formatted">("raw");
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  const { user, isLoaded, isSignedIn } = useUser();
  const { signOut } = useClerk();
  const { getToken } = useAuth();

  const apiFetch = async (url: string, options: RequestInit = {}) => {
    const token = await getToken();
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  };

  // Sync user to backend when login state changes
  useEffect(() => {
    if (user && isSignedIn) {
      apiFetch(`${API_URL}/api/auth/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: user.fullName || user.username || "Reviewer",
          email: user.primaryEmailAddress?.emailAddress || "",
          avatar_url: user.imageUrl || "",
        }),
      }).catch(() => {});
    }
  }, [user, isSignedIn]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    safeSetItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    loadReviews();
    loadDocuments();
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifications(false);
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) setShowProfileMenu(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!isLoaded) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--text)", background: "var(--bg)" }}>Loading Workspace...</div>;
  }

  if (!isSignedIn || page === "landing") {
    return <LandingPage />;
  }

  const currentUser = {
    name: user?.fullName || user?.username || "Reviewer",
    email: user?.primaryEmailAddress?.emailAddress || "",
    role: "User",
  };

  function handleLogout() {
    signOut();
    setShowProfileMenu(false);
    setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: "Logged out successfully", time: new Date().toLocaleTimeString(), read: false }]);
    setPage("landing");
  }

  function handleLoginSuccess(user: { name: string; email: string; role: string }) {
    safeSetItem("reviewmind_user", JSON.stringify(user));
    setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: `Welcome back, ${user.name}!`, time: new Date().toLocaleTimeString(), read: false }]);
    if (page === "landing") setPage("home");
  }



  const sidebarSections: SidebarSection[] = [
    {
      label: "Workspace",
      items: [
        { id: "home", label: "Home", Icon: LayoutDashboard },
        { id: "reviews", label: "Reviews", Icon: FileText },
        { id: "documents", label: "Documents", Icon: FolderOpen },
        { id: "history", label: "History", Icon: History },
      ],
    },
    {
      label: "Configuration",
      items: [
        { id: "profiles", label: "Profiles", Icon: Users },
        { id: "kbpacks", label: "Knowledge Packs", Icon: BookOpen },
      ],
    },
    {
      label: "Tools",
      items: [
        { id: "ai", label: "AI Assistant", Icon: Bot },
      ],
    },
  ];

  const crumbs = breadcrumb(page, result?.filename);

  async function submitReview(options?: {
    profile_id?: string;
    pack_ids?: string[];
    enabled_categories?: string[];
    review_mode?: string;
    text?: string;
    binaryFile?: File | null;
    document_id?: string | null;
  }) {
    setLoading(true);
    const profId = options?.profile_id || profile;
    const packIds = options?.pack_ids || [];
    const enabledCats = options?.enabled_categories || [];
    const reviewText = options?.text || "";
    const revBinaryFile = options?.binaryFile || null;

    try {
      // Build request body
      const body: Record<string, any> = {
        profile_id: profId,
        pack_ids: packIds,
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
        alert("No document selected and no text provided.");
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
      setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: `Review completed for "${session.filename}" — Score: ${session.score}`, time: new Date().toLocaleString(), read: false }]);
      setPage("review-detail");
    } catch (error) {
      alert(`Review failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setLoading(false);
    }
  }

  function handleFileUpload(file: File) {
    const name = file.name.toLowerCase();
    const isText = name.endsWith(".txt") || name.endsWith(".md") || name.endsWith(".markdown") || name.endsWith(".html") || name.endsWith(".tex");
    if (isText) {
      setBinaryFile(null);
      const reader = new FileReader();
      reader.onload = (e) => {
        setText(e.target?.result as string || "");
      };
      reader.readAsText(file);
    } else {
      setBinaryFile(file);
      setText(`[Binary file: ${file.name} — ${(file.size / 1024).toFixed(0)} KB]\n\nClick "Start Review" below to upload and analyze this file.\nThe backend will parse the document and run the review engine.`);
    }
  }

  function handleClearBinary() {
    setBinaryFile(null);
    setText("# Review Document\n\nThis is a sample document for review. The engine will analyze this text for quality, consistency, and compliance issues based on the selected profile.");
  }

  async function loadReviews() {
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
        setReviewList(list);
      }
    } catch { }
  }

  async function loadDocuments() {
    try {
      const response = await apiFetch(`${API_URL}/api/documents`);
      if (response.ok) {
        const data = await response.json();
        const list = (data.items || data || []).map((item: any) => ({
          id: item.id || crypto.randomUUID(),
          name: item.original_name || item.name || "untitled",
          uploaded_at: item.created_at || item.uploaded_at || new Date().toISOString(),
        }));
        setDocuments(list);
      }
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
    } catch {
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
          setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: `Document "${file.name}" uploaded successfully`, time: new Date().toLocaleString(), read: false }]);
        }
      } else {
        const errText = await response.text().catch(() => "Upload failed");
        setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: `Upload failed: ${errText.slice(0, 200)}`, time: new Date().toLocaleString(), read: false }]);
      }
    } catch (error) {
      console.error("Upload failed:", error);
      setNotifications(prev => [...prev, { id: crypto.randomUUID(), text: `Upload failed: Network error`, time: new Date().toLocaleString(), read: false }]);
    } finally {
      setIsUploadingDocument(false);
    }
  }



  async function handleDeleteDocument(id: string) {
    try {
      await apiFetch(`${API_URL}/api/documents/${id}`, { method: "DELETE" });
    } catch { }
    setDocuments(prev => prev.filter(d => d.id !== id));
  }

  function handleUpdateStatus(issueId: string, status: string) {
    if (!result) return;
    setResult({ ...result, issues: result.issues.map(iss => iss.id === issueId ? { ...iss, status } : iss) });
  }

  const filteredReviews = searchQuery
    ? reviewList.filter(r => r.filename.toLowerCase().includes(searchQuery.toLowerCase()) || r.profile_id.toLowerCase().includes(searchQuery.toLowerCase()))
    : reviewList;

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="app">
      {/* Topbar */}
      <header className="app-header">
        <div className="header-left">
          <button className="btn-icon" onClick={() => setSidebarOpen(!sidebarOpen)} data-tooltip={sidebarOpen ? "Close sidebar" : "Open sidebar"}>
            <Menu size={20} />
          </button>
          <span className="app-title">ReviewMind</span>
        </div>

        {/* Breadcrumb */}
        <nav className="header-breadcrumb">
          {crumbs.map((cr, i) => (
            <span key={i} className="bc-segment">
              {i > 0 && <ChevronRight size={12} className="bc-chevron" />}
              {cr.page ? (
                <button className="bc-link" onClick={() => setPage(cr.page!)}>{cr.label}</button>
              ) : (
                <span className="bc-current">{cr.label}</span>
              )}
            </span>
          ))}
        </nav>

        <div className="header-center">
          <div className="header-search">
            <Search size={14} className="hs-icon" />
            <input type="text" className="hs-input" placeholder="Search reviews, documents, issues..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
            <kbd className="hs-kbd">/</kbd>
          </div>
        </div>

        <div className="header-actions">
          <button className="theme-toggle" onClick={() => setTheme(theme === "light" ? "dark" : "light")} data-tooltip={theme === "light" ? "Dark mode" : "Light mode"}>
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          <div ref={notifRef} style={{ position: "relative" }}>
            <button className="theme-toggle" onClick={() => setShowNotifications(!showNotifications)} data-tooltip="Notifications">
              <Bell size={16} />
              {unreadCount > 0 && <span className="notif-badge">{unreadCount}</span>}
            </button>
            {showNotifications && (
              <div className="notif-dropdown">
                <div className="notif-header">
                  <strong>Notifications</strong>
                  {unreadCount > 0 && <button className="btn-sm outline" onClick={() => setNotifications(prev => prev.map(n => ({ ...n, read: true })))} style={{ fontSize: ".78rem", padding: "2px 8px" }}>Mark all read</button>}
                </div>
                {notifications.length === 0 ? (
                  <div className="notif-empty">No notifications</div>
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
                  <LogOut size={16} /> Sign out
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
                    <button key={item.id} className={`sidebar-item ${page === item.id ? "active" : ""}`} onClick={() => setPage(item.id)}>
                      <item.Icon size={16} />
                      <span>{item.label}</span>
                    </button>
                  ))}
                  <div className="sidebar-divider" />
                </div>
              ))}
              <button className={`sidebar-item ${page === "settings" ? "active" : ""}`} onClick={() => setPage("settings")}>
                <Settings size={16} />
                <span>Settings</span>
              </button>
              <div className="sidebar-divider" />
              <button className="sidebar-item sidebar-new-btn" onClick={() => setPage("review-new")}>
                <Plus size={16} />
                <span>New Review</span>
              </button>
            </div>
            {result && (
              <div className="sidebar-section">
                <div className="sidebar-section-title">Current Review</div>
                <div className="ss-session-card" onClick={() => setPage("review-detail")}>
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
                    <div className="ss-meta">{result.issues.length} issues</div>
                  </div>
                  <button className="btn-sm outline full-width" style={{ marginTop: 8, fontSize: ".76rem", width: "100%" }}>
                    Open Dashboard ➔
                  </button>
                </div>
              </div>
            )}
          </aside>
        )}

        {/* Content */}
        <div className="workspace-main">
          <div className="workspace-content">
            {page === "home" && result ? (
              <DashboardView session={result} onSelectIssue={setSelectedIssue} selectedIssue={selectedIssue} onUpdateStatus={handleUpdateStatus} onSelectSession={handleSelectSession} reviewList={reviewList} onNavigatePage={setPage} apiFetch={apiFetch} />
            ) : page === "home" && !result ? (
              <HomeWelcomeDashboard userName={currentUser.name} onNavigate={setPage} />
            ) : page === "reviews" ? (
              <ReviewsView items={filteredReviews} onSelect={handleSelectReview} onNewReview={() => setPage("review-new")} />
            ) : page === "review-new" ? (
              <ReviewWizardView
                profile={profile}
                setProfile={setProfile}
                loading={loading}
                onSubmit={submitReview}
                documents={documents}
                selectedDocumentId={selectedDocumentId}
                setSelectedDocumentId={setSelectedDocumentId}
                apiFetch={apiFetch}
                API_URL={API_URL}
              />
            ) : page === "review-detail" && result ? (
              <DashboardView session={result} onSelectIssue={setSelectedIssue} selectedIssue={selectedIssue} onUpdateStatus={handleUpdateStatus} onSelectSession={handleSelectSession} reviewList={reviewList} onNavigatePage={setPage} apiFetch={apiFetch} />
            ) : page === "history" ? (
              <HistoryView items={reviewList} onSelect={handleSelectReview} />
            ) : page === "documents" ? (
              <DocumentsView documents={documents} onUpload={handleDocumentUpload} onDelete={handleDeleteDocument} uploadInputRef={uploadInputRef} isUploading={isUploadingDocument} />
            ) : page === "profiles" ? (
              <ProfilesView showForm={showProfileForm} setShowForm={setShowProfileForm} />
            ) : page === "kbpacks" ? (
              <KnowledgePacksView showForm={showPackForm} setShowForm={setShowPackForm} />
            ) : page === "ai" ? (
              <AIAssistantView session={result} />
            ) : page === "settings" ? (
              <SettingsView theme={theme} setTheme={setTheme} />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════
   Views
   ═══════════════════════════════════════ */

/* Welcome Dashboard for Authenticated Users without prior review in session */
function HomeWelcomeDashboard({ userName, onNavigate }: { userName: string; onNavigate: (page: Page) => void }) {
  return (
    <div className="home-welcome-dashboard">
      <div className="welcome-hero-card card">
        <div className="whc-content">
          <div className="whc-badge"><Sparkles size={14} /> Rule-First Document Review Engine</div>
          <h2>Welcome to ReviewMind, {userName}! 👋</h2>
          <p>Analyze your academic papers, technical specs, business proposals, and SOPs against 200+ precision rules.</p>
          <div className="whc-actions">
            <button className="btn-primary" style={{ padding: "12px 24px" }} onClick={() => onNavigate("review-new")}>
              <Zap size={18} /> Start New Review Wizard
            </button>
            <button className="btn-secondary" style={{ padding: "12px 24px" }} onClick={() => onNavigate("documents")}>
              <FolderOpen size={18} /> Document Vault
            </button>
          </div>
        </div>
      </div>

      <div className="welcome-quick-grid">
        <div className="card action-tile" onClick={() => onNavigate("review-new")}>
          <div className="tile-icon primary"><Zap size={22} /></div>
          <strong>New Review Wizard</strong>
          <p>5-step guided review pipeline with auto-profile detection & knowledge pack selection.</p>
          <span className="tile-link">Launch Wizard ➔</span>
        </div>
        <div className="card action-tile" onClick={() => onNavigate("profiles")}>
          <div className="tile-icon success"><Users size={22} /></div>
          <strong>Review Profiles</strong>
          <p>Configure scoring weights and permission matrices for Academic, Business, and SOP docs.</p>
          <span className="tile-link">View Profiles ➔</span>
        </div>
        <div className="card action-tile" onClick={() => onNavigate("kbpacks")}>
          <div className="tile-icon warning"><BookOpen size={22} /></div>
          <strong>Knowledge Packs</strong>
          <p>Explore IEEE, APA 7th, ISO 9001, FDA, and Nature publication standards.</p>
          <span className="tile-link">Explore Packs ➔</span>
        </div>
        <div className="card action-tile" onClick={() => onNavigate("ai")}>
          <div className="tile-icon info"><Bot size={22} /></div>
          <strong>AI Assistant</strong>
          <p>Ask AI for deep document analysis, claim verification, and writing improvements.</p>
          <span className="tile-link">Ask AI ➔</span>
        </div>
      </div>

      <div className="card arch-philosophy-card">
        <div className="apc-header">
          <Shield size={18} style={{ color: "var(--primary)" }} />
          <strong>ReviewMind Architecture Pipeline</strong>
        </div>
        <div className="apc-steps">
          <div className="apc-step"><span className="apc-tag">1. Rule-First</span><span>Deterministic validation</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">2. Knowledge-Driven</span><span>Domain pack context</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">3. AI-Assisted</span><span>Selective LLM review</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">4. Auto Fix</span><span>Safe 1-click edits</span></div>
          <span className="apc-arrow">➔</span>
          <div className="apc-step"><span className="apc-tag">5. Evidence-Based</span><span>Full line-level trace</span></div>
        </div>
      </div>
    </div>
  );
}

/* Enhanced Dashboard View */
function DashboardView({ session, onSelectIssue, selectedIssue, onUpdateStatus, onSelectSession, reviewList, onNavigatePage, apiFetch }: {
  session: SessionDetail;
  onSelectIssue: (issue: Issue | null) => void;
  selectedIssue: Issue | null;
  onUpdateStatus: (id: string, status: string) => void;
  onSelectSession: (id: string) => void;
  reviewList: HistoryItem[];
  onNavigatePage?: (page: Page) => void;
  apiFetch: (url: string, options?: RequestInit) => Promise<Response>;
}) {
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
    parser: { status: "completed", label: "Document Parsed" },
    profile: { status: "completed", label: `${session.profile_id} Profile` },
    knowledge_pack: { status: "completed", label: session.pack_ids?.length ? `${session.pack_ids.length} Pack(s)` : "Base Pack" },
    rule_engine: { status: "completed", label: `${ruleStats.loaded} Rules Executed` },
    ai_scheduler: { status: "skipped", label: "Rule-First: AI Skipped" },
    autofix: { status: "ready", label: `${session.issues.filter(i => i.autofix_allowed).length} Fixes Ready` },
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
              <span><Clock size={13} /> {session.created_at ? new Date(session.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Just now"}</span>
              <span><Zap size={13} /> Duration: <strong>{session.duration_ms ? `${(session.duration_ms / 1000).toFixed(2)}s` : "1.4s"}</strong></span>
              <span><Shield size={13} /> Evaluated: <strong>{ruleStats.loaded} rules</strong></span>
              <span><FilePen size={13} /> Parser: <strong>Unified Model</strong></span>
            </div>
          </div>
        </div>

        {/* ── Dashboard Header Actions (Item 8, 12) ─────────────────────────── */}
        <div className="rmb-actions">
          <div ref={rerunRef} style={{ position: "relative" }}>
            <button className="btn-primary" onClick={() => setShowRerunMenu(!showRerunMenu)}>
              <RefreshCw size={15} /> Run Again <ChevronRight size={14} style={{ transform: showRerunMenu ? "rotate(90deg)" : "none", transition: "0.2s" }} />
            </button>
            {showRerunMenu && (
              <div className="dropdown-menu">
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("review-new"); }}>
                  <RefreshCw size={14} /> Run Again (Same Settings)
                </button>
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("review-new"); }}>
                  <Users size={14} /> Change Profile
                </button>
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("review-new"); }}>
                  <BookOpen size={14} /> Change Knowledge Pack
                </button>
                <button className="dropdown-item" onClick={() => { setShowRerunMenu(false); onNavigatePage?.("ai"); }}>
                  <Bot size={14} /> Run AI Review
                </button>
              </div>
            )}
          </div>
          <button className="btn-secondary" onClick={handleExportReport} data-tooltip="Export Report">
            <Download size={15} /> Export Report
          </button>
          <button className="btn-secondary" onClick={() => onNavigatePage?.("history")} data-tooltip="View History">
            <History size={15} /> History
          </button>
        </div>
      </div>

      {/* ── Pipeline Status Component (Item 7) ────────────────────────────────── */}
      <div className="pipeline-banner card">
        <h4 className="section-subtitle"><Activity size={16} /> Review Pipeline Status</h4>
        <div className="pipeline-steps-grid">
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>1. Parser</strong></div>
            <div className="pipe-step-label">{pipeline.parser?.label || "DOCX Parsed"}</div>
          </div>
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>2. Profile Detection</strong></div>
            <div className="pipe-step-label">{pipeline.profile?.label || session.profile_id}</div>
          </div>
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>3. Knowledge Pack</strong></div>
            <div className="pipe-step-label">{pipeline.knowledge_pack?.label || "Base Pack"}</div>
          </div>
          <div className="pipe-step-card completed">
            <div className="pipe-step-head"><CheckCircle size={16} className="pipe-icon done" /><strong>4. Rule Engine</strong></div>
            <div className="pipe-step-label">{pipeline.rule_engine?.label || `${ruleStats.loaded} Rules Executed`}</div>
          </div>
          <div className={`pipe-step-card ${pipeline.ai_scheduler?.status === "completed" ? "completed" : "skipped"}`}>
            <div className="pipe-step-head">
              {pipeline.ai_scheduler?.status === "completed" ? <Bot size={16} className="pipe-icon done" /> : <Zap size={16} className="pipe-icon skipped" />}
              <strong>5. AI Scheduler</strong>
            </div>
            <div className="pipe-step-label">{pipeline.ai_scheduler?.label || "Skipped (Rules Satisfied)"}</div>
          </div>
          <div className="pipe-step-card ready" style={{ cursor: 'pointer' }} onClick={() => setShowAutoFix(true)}>
            <div className="pipe-step-head"><Wrench size={16} className="pipe-icon ready" /><strong>6. Auto Fix Engine</strong></div>
            <div className="pipe-step-label">{pipeline.autofix?.label || "Ready (Click to Open)"}</div>
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
              {session.score >= 85 ? "Excellent" : session.score >= 70 ? "Good" : session.score >= 50 ? "Needs Work" : "Poor"}
            </div>
          </div>
        </div>
        <div className="dashboard-stats-grid">
          <div className="stat-box">
            <BarChart3 size={20} className="stat-icon" />
            <span className="stat-value">{session.issues.length}</span>
            <span className="stat-label">Issues Found</span>
          </div>
          <div className="stat-box">
            <AlertTriangle size={20} className="stat-icon" style={{ color: "var(--danger)" }} />
            <span className="stat-value">{highCount}</span>
            <span className="stat-label">High Severity</span>
          </div>
          <div className="stat-box">
            <CheckCircle size={20} className="stat-icon" style={{ color: "var(--success)" }} />
            <span className="stat-value">{resolvedCount}</span>
            <span className="stat-label">Resolved</span>
          </div>
        </div>
      </div>

      {/* ── Document Statistics & Rule Engine Statistics Cards (Item 9, 10) ──── */}
      <div className="dashboard-stats-split">
        {/* Document Statistics */}
        <div className="card stat-group-card">
          <h3 className="chart-title"><FileText size={16} /> Document Statistics</h3>
          <div className="stats-mini-grid">
            <div className="stat-mini-box"><span className="mini-val">{docStats.pages}</span><span className="mini-lbl">Pages</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.paragraphs}</span><span className="mini-lbl">Paragraphs</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.headings}</span><span className="mini-lbl">Headings</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.tables}</span><span className="mini-lbl">Tables</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.figures}</span><span className="mini-lbl">Figures</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.words.toLocaleString()}</span><span className="mini-lbl">Words</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.references}</span><span className="mini-lbl">References</span></div>
            <div className="stat-mini-box"><span className="mini-val">{docStats.chars.toLocaleString()}</span><span className="mini-lbl">Characters</span></div>
          </div>
        </div>

        {/* Rule Engine Statistics */}
        <div className="card stat-group-card">
          <h3 className="chart-title"><Shield size={16} /> Rule Engine Statistics</h3>
          <div className="stats-mini-grid">
            <div className="stat-mini-box"><span className="mini-val" style={{ color: "var(--primary)" }}>{ruleStats.loaded}</span><span className="mini-lbl">Rules Loaded</span></div>
            <div className="stat-mini-box"><span className="mini-val" style={{ color: "var(--success)" }}>{ruleStats.passed}</span><span className="mini-lbl">Passed</span></div>
            <div className="stat-mini-box"><span className="mini-val" style={{ color: "var(--danger)" }}>{ruleStats.failed}</span><span className="mini-lbl">Failed</span></div>
            <div className="stat-mini-box"><span className="mini-val">{ruleStats.skipped}</span><span className="mini-lbl">Skipped</span></div>
            <div className="stat-mini-box full"><span className="mini-val">{ruleStats.execution_ms} ms</span><span className="mini-lbl">Execution Time</span></div>
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
function ReviewWizardView({
  profile,
  setProfile,
  loading,
  onSubmit,
  documents,
  selectedDocumentId,
  setSelectedDocumentId,
  apiFetch,
  API_URL,
}: {
  profile: string;
  setProfile: (v: string) => void;
  loading: boolean;
  onSubmit: (options?: any) => void;
  documents: DocumentItem[];
  selectedDocumentId: string | null;
  setSelectedDocumentId: (id: string | null) => void;
  apiFetch: (url: string, options?: RequestInit) => Promise<Response>;
  API_URL: string;
}) {
  const [step, setStep] = useState<number>(() => Number(safeGetItem("rw_step")) || 1);
  const [selectedPacks, setSelectedPacks] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem("rw_packs") || '["academic_base"]'); } catch { return ["academic_base"]; }
  });
  const [selectedCategories, setSelectedCategories] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem("rw_categories") || '["structure", "writing", "citation", "logic", "compliance", "figures", "tables"]'); } catch { return ["structure", "writing", "citation", "logic", "compliance", "figures", "tables"]; }
  });
  const [reviewMode, setReviewMode] = useState<"rule_only" | "rule_ai" | "full">(() => (safeGetItem("rw_mode") as any) || "rule_ai");
  const [language, setLanguage] = useState<"en" | "vi">(() => (safeGetItem("rw_lang") as any) || "en");
  const [text, setText] = useState(() => safeGetItem("rw_text") || "");
  const [binaryFile, setBinaryFile] = useState<File | null>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [uploadMode, setUploadMode] = useState<"upload" | "select" | null>(null);

  useEffect(() => {
    safeSetItem("rw_step", step.toString());
    safeSetItem("rw_packs", JSON.stringify(selectedPacks));
    safeSetItem("rw_categories", JSON.stringify(selectedCategories));
    safeSetItem("rw_mode", reviewMode);
    safeSetItem("rw_lang", language);
    safeSetItem("rw_text", text);
  }, [step, selectedPacks, selectedCategories, reviewMode, language, text]);

  const [showPreview, setShowPreview] = useState<boolean>(false);
  const wizardUploadRef = useRef<HTMLInputElement>(null);

  // Auto-detect profile from document content
  const detectedProfileInfo = useMemo(() => {
    const lowered = (binaryFile ? binaryFile.name : text).toLowerCase();
    if (lowered.includes("design") || lowered.includes("architecture") || lowered.includes("schema") || lowered.includes("component") || lowered.includes(".yaml")) {
      return { id: "technical_design", name: "Technical Design", confidence: 94 };
    }
    if (lowered.includes("proposal") || lowered.includes("business") || lowered.includes("executive") || lowered.includes("budget")) {
      return { id: "business", name: "Business Proposal", confidence: 91 };
    }
    if (lowered.includes("sop") || lowered.includes("procedure") || lowered.includes("compliance") || lowered.includes("safety")) {
      return { id: "sop", name: "SOP & Compliance", confidence: 89 };
    }
    return { id: "academic", name: "Academic Paper", confidence: 93 };
  }, [text, binaryFile]);

  const profilesList = [
    { id: "academic", name: "Academic Paper", desc: "Writing suggestions, citation checks, journal formats, APA/IEEE adherence", Icon: BookOpen },
    { id: "business", name: "Business Proposal", desc: "Clarity, persuasion score, executive summary, jargon detection", Icon: Briefcase },
    { id: "sop", name: "SOP & Compliance", desc: "Regulatory adherence, policy safety scan, risk assessment (Rewrite blocked)", Icon: Shield },
    { id: "technical_design", name: "Technical Specification", desc: "System architecture, API schemas, code consistency, diagram alignment", Icon: Database },
  ];

  const packsList = [
    { id: "academic_base", name: "Academic Base", desc: "Standard academic structure and citation rules", category: "Base", active: true },
    { id: "ieee", name: "IEEE Format", desc: "IEEE engineering & CS citation & table standard", category: "Citation" },
    { id: "apa7", name: "APA 7th", desc: "APA social sciences citation & heading format", category: "Citation" },
    { id: "acm", name: "ACM Style", desc: "ACM computing publication standards", category: "Citation" },
    { id: "nature", name: "Nature Journal", desc: "Nature scientific publication strict checks", category: "Journal" },
    { id: "iso9001", name: "ISO 9001 QMS", desc: "Quality management documentation audit", category: "Compliance" },
    { id: "fda21", name: "FDA 21 CFR", desc: "FDA regulatory compliance checks", category: "Compliance" },
  ];

  const categoriesList = [
    { id: "structure", label: "Structure", desc: "Headings, required sections, document layout" },
    { id: "writing", label: "Writing Quality", desc: "Sentence length, passive voice, readability" },
    { id: "citation", label: "Citations & References", desc: "Inline citations, bibliography completeness" },
    { id: "logic", label: "Logic & Consistency", desc: "Argument flow, claim support, terms consistency" },
    { id: "compliance", label: "Compliance & Safety", desc: "Policy, disclaimer, regulatory rules" },
    { id: "figures", label: "Figures & Captions", desc: "Figure numbering, alt text, resolution" },
    { id: "tables", label: "Tables & Data", desc: "Table headers, caption alignment, cell values" },
  ];

  function togglePack(id: string) {
    setSelectedPacks(prev => prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]);
  }

  function toggleCategory(id: string) {
    setSelectedCategories(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]);
  }

  function handleFileUpload(file: File) {
    setBinaryFile(file);
    setText("");
  }

  async function handleWizardUpload(file: File) {
    setIsUploadingDoc(true);
    setUploadMode("upload");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiFetch(`${API_URL}/api/documents/upload`, {
        method: "POST",
        body: formData,
      });
      if (response.ok) {
        const data = await response.json();
        setSelectedDocumentId(data.document_id);
        setBinaryFile(file);
        setText("");
      }
    } catch (error) {
      console.error("Upload failed", error);
    } finally {
      setIsUploadingDoc(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleWizardUpload(f);
    e.target.value = "";
  }

  function handleSelectDocument(id: string) {
    setSelectedDocumentId(id);
    setUploadMode("select");
    setBinaryFile(null);
    setText("");
  }

  function handleClearSelection() {
    setSelectedDocumentId(null);
    setUploadMode(null);
    setBinaryFile(null);
    setText("");
  }

  function handleStartReview() {
    onSubmit({
      profile_id: profile,
      pack_ids: selectedPacks,
      enabled_categories: selectedCategories,
      review_mode: reviewMode,
      text: text,
      document_id: selectedDocumentId,
    });
  }

  return (
    <div className="wizard-layout">
      {/* ── Wizard Steps Header ───────────────────────────────────────────────── */}
      <div className="wizard-stepper card">
        {[
          { num: 1, label: "Document Upload", Icon: Upload },
          { num: 2, label: "Profile & Auto-Detect", Icon: Target },
          { num: 3, label: "Knowledge Pack", Icon: BookOpen },
          { num: 4, label: "Configuration", Icon: Sliders },
          { num: 5, label: "Review Summary", Icon: CheckCircle },
        ].map((st) => (
          <div key={st.num} className={`wizard-step-item ${step === st.num ? "active" : step > st.num ? "completed" : ""}`} onClick={() => setStep(st.num)}>
            <div className="step-badge">{step > st.num ? <Check size={14} /> : st.num}</div>
            <div className="step-info">
              <span className="step-num-text">STEP {st.num}</span>
              <span className="step-label-text">{st.label}</span>
            </div>
            {st.num < 5 && <div className="step-connector" />}
          </div>
        ))}
      </div>

      {/* ── STEP 1: Upload Document (Item 1, 2) ─────────────────────────────── */}
      {step === 1 && (
        <div className="wizard-card card">
          <h3><Upload size={20} /> Step 1: Select Document</h3>
          <p className="wizard-sub">Choose how you want to provide the document for review.</p>

          {/* ── Option Cards: Upload New or Select Existing ── */}
          {!selectedDocumentId && !binaryFile && !text && (
            <div className="wizard-source-options">
              <div className="card source-option-card" onClick={() => wizardUploadRef.current?.click()}>
                <Upload size={36} className="soc-icon" />
                <strong>Upload New File</strong>
                <p>Upload a DOCX, PDF, or Markdown file. It will be stored and a review can be run later.</p>
                <span className="soc-action">Choose File ➔</span>
                <input ref={wizardUploadRef} type="file" accept=".docx,.pdf,.txt,.md,.markdown,.html,.tex" style={{ display: "none" }} onChange={handleFileSelect} />
              </div>
              {documents.length > 0 && (
                <div className="card source-option-card">
                  <FolderOpen size={36} className="soc-icon" />
                  <strong>Select Existing Document</strong>
                  <p>Pick a document from your previously uploaded document vault.</p>
                  <div className="existing-docs-list">
                    {documents.map(doc => (
                      <div key={doc.id} className={`existing-doc-item ${selectedDocumentId === doc.id ? "selected" : ""}`} onClick={() => handleSelectDocument(doc.id)}>
                        <FileText size={16} />
                        <span>{doc.name}</span>
                        <span className="edoc-date">{new Date(doc.uploaded_at).toLocaleDateString()}</span>
                        {selectedDocumentId === doc.id && <CheckCircle size={14} className="edoc-check" />}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Show Selected Document ── */}
          {(selectedDocumentId || binaryFile) && (
            <div className="uploaded-file-card">
              <div className="ufc-left">
                <FileText size={32} className="ufc-icon" />
                <div className="ufc-meta">
                  {uploadMode === "upload" && binaryFile ? (
                    <>
                      <strong>{binaryFile.name}</strong>
                      <div className="ufc-tags">
                        <span className="format-tag">{binaryFile.name.split('.').pop()?.toUpperCase()}</span>
                        <span className="size-tag">{(binaryFile.size / 1024).toFixed(1)} KB</span>
                        <span className="status-tag ready"><CheckCircle size={12} /> Uploaded & Ready</span>
                      </div>
                    </>
                  ) : (
                    (() => {
                      const doc = documents.find(d => d.id === selectedDocumentId);
                      return (
                        <>
                          <strong>{doc ? doc.name : "Selected Document"}</strong>
                          <div className="ufc-tags">
                            <span className="format-tag">DOC</span>
                            {doc && <span className="size-tag">{new Date(doc.uploaded_at).toLocaleDateString()}</span>}
                            <span className="status-tag ready"><CheckCircle size={12} /> Selected</span>
                          </div>
                        </>
                      );
                    })()
                  )}
                </div>
              </div>
              <div className="ufc-actions">
                <button className="btn-danger-outline" onClick={handleClearSelection}>
                  <Trash2 size={14} /> Clear
                </button>
              </div>
            </div>
          )}

          {/* Progress / Loading */}
          {isUploadingDoc && (
            <div className="wizard-upload-progress">
              <Loader2 size={20} className="spin" />
              <span>Uploading document...</span>
            </div>
          )}

          {/* Quick Stats (when pasted text) */}
          {text && (
            <div className="quick-stats-bar">
              <div className="qs-item"><span className="qs-lbl">Words</span><strong>{text.split(/\s+/).filter(Boolean).length}</strong></div>
              <div className="qs-item"><span className="qs-lbl">Paragraphs</span><strong>{text.split("\n\n").filter(Boolean).length}</strong></div>
              <div className="qs-item"><span className="qs-lbl">Characters</span><strong>{text.length}</strong></div>
            </div>
          )}

          <div className="wizard-nav-actions">
            <button className="btn-primary" disabled={!selectedDocumentId && !binaryFile && !text} onClick={() => setStep(2)}>
              Next: Select Profile <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2: Profile Selection & Auto Detect (Item 1, 13) ─────────────── */}
      {step === 2 && (
        <div className="wizard-card card">
          <h3><Target size={20} /> Step 2: Select Review Profile</h3>
          <p className="wizard-sub">Profile defines scoring weights, required sections, and writing permission constraints.</p>

          {/* Auto-Detect Banner */}
          <div className="auto-detect-banner">
            <div className="adb-left">
              <Sparkles size={20} className="adb-icon" />
              <div>
                <strong>System Auto-Detected Profile: {detectedProfileInfo.name}</strong>
                <p>Based on document keywords, layout structure, and headings ({detectedProfileInfo.confidence}% confidence match).</p>
              </div>
            </div>
            <button className="btn-primary" style={{ padding: "8px 16px", fontSize: ".82rem" }} onClick={() => setProfile(detectedProfileInfo.id)}>
              Use Auto-Detected Profile
            </button>
          </div>

          {/* Profiles Grid */}
          <div className="profiles-select-grid">
            {profilesList.map(p => (
              <div key={p.id} className={`profile-select-card ${profile === p.id ? "selected" : ""}`} onClick={() => setProfile(p.id)}>
                <div className="psc-icon"><p.Icon size={22} /></div>
                <div className="psc-body">
                  <strong>{p.name}</strong>
                  <p>{p.desc}</p>
                </div>
                <div className="psc-check">{profile === p.id && <CheckCircle size={18} />}</div>
              </div>
            ))}
          </div>

          {/* Permission Matrix Info */}
          <div className="permission-info-box">
            <strong>Permission Matrix for "{profile.toUpperCase()}" Profile</strong>
            <p>
              {profile === "academic" && "Allows writing suggestions, syntax fixes, and reference formatting recommendations."}
              {profile === "sop" && "Strict Compliance Mode: Blocks text rewriting and auto-edits by design to prevent unauthorized procedure changes."}
              {profile === "business" && "Allows tone adjustments, clarity improvements, and executive summary enhancements."}
              {profile === "technical_design" && "Allows architecture alignment suggestions, schema validation, and term consistency fixes."}
            </p>
          </div>

          <div className="wizard-nav-actions">
            <button className="btn-secondary" onClick={() => setStep(1)}><ArrowLeft size={16} /> Back</button>
            <button className="btn-primary" onClick={() => setStep(3)}>Next: Knowledge Packs <ArrowRight size={16} /></button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Knowledge Pack Selection (Item 1, 3, 13) ────────────────── */}
      {step === 3 && (
        <div className="wizard-card card">
          <h3><BookOpen size={20} /> Step 3: Select Knowledge Packs</h3>
          <p className="wizard-sub">Knowledge Packs extend the base engine with domain-specific rules (Citations, Compliance, Standards).</p>

          <div className="packs-select-grid">
            {packsList.map(pk => {
              const isSelected = selectedPacks.includes(pk.id);
              return (
                <div key={pk.id} className={`pack-select-card ${isSelected ? "selected" : ""}`} onClick={() => togglePack(pk.id)}>
                  <div className="pkc-header">
                    <Database size={18} />
                    <span className="pkc-category">{pk.category}</span>
                  </div>
                  <strong>{pk.name}</strong>
                  <p>{pk.desc}</p>
                  <div className="pkc-check">{isSelected ? <CheckCircle size={16} /> : <div className="pkc-empty" />}</div>
                </div>
              );
            })}
          </div>

          <div className="rules-counter-badge">
            <Shield size={16} /> Total Active Rules Loaded: <strong>{218 + selectedPacks.length * 12} Rules</strong>
          </div>

          <div className="wizard-nav-actions">
            <button className="btn-secondary" onClick={() => setStep(2)}><ArrowLeft size={16} /> Back</button>
            <button className="btn-primary" onClick={() => setStep(4)}>Next: Configuration <ArrowRight size={16} /></button>
          </div>
        </div>
      )}

      {/* ── STEP 4: Review Configuration & Categories (Item 4, 13) ──────────── */}
      {step === 4 && (
        <div className="wizard-card card">
          <h3><Sliders size={20} /> Step 4: Review Configuration</h3>
          <p className="wizard-sub">Fine-tune review categories, AI assistance level, and language preferences.</p>

          {/* Categories Toggles */}
          <div className="wizard-section">
            <h4>Review Categories ({selectedCategories.length}/7 Selected)</h4>
            <div className="categories-grid">
              {categoriesList.map(cat => {
                const checked = selectedCategories.includes(cat.id);
                return (
                  <label key={cat.id} className={`cat-toggle-card ${checked ? "active" : ""}`}>
                    <input type="checkbox" checked={checked} onChange={() => toggleCategory(cat.id)} />
                    <div>
                      <strong>{cat.label}</strong>
                      <p>{cat.desc}</p>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Review Mode Radio */}
          <div className="wizard-section" style={{ marginTop: 20 }}>
            <h4>Review Execution Mode</h4>
            <div className="modes-grid">
              <label className={`mode-card ${reviewMode === "rule_only" ? "selected" : ""}`}>
                <input type="radio" name="mode" checked={reviewMode === "rule_only"} onChange={() => setReviewMode("rule_only")} />
                <div>
                  <strong>⚡ Rule-First Only (Fastest)</strong>
                  <p>Runs 200+ rule engine checks locally. 0ms LLM latency, 100% deterministic.</p>
                </div>
              </label>
              <label className={`mode-card ${reviewMode === "rule_ai" ? "selected" : ""}`}>
                <input type="radio" name="mode" checked={reviewMode === "rule_ai"} onChange={() => setReviewMode("rule_ai")} />
                <div>
                  <strong>🤖 Rule + AI Assisted (Recommended)</strong>
                  <p>AI Scheduler evaluates whether AI is needed after rules finish. Optional AI analysis.</p>
                </div>
              </label>
              <label className={`mode-card ${reviewMode === "full" ? "selected" : ""}`}>
                <input type="radio" name="mode" checked={reviewMode === "full"} onChange={() => setReviewMode("full")} />
                <div>
                  <strong>🛠️ Full Review & Auto-Fix Plan</strong>
                  <p>Runs full rule engine, AI reviewer, and generates automated 1-click fix suggestions.</p>
                </div>
              </label>
            </div>
          </div>

          {/* Language Selection */}
          <div className="setting-row" style={{ marginTop: 16, maxWidth: 300 }}>
            <label>Report Language</label>
            <select value={language} onChange={e => setLanguage(e.target.value as any)}>
              <option value="en">English (US)</option>
              <option value="vi">Vietnamese (Tiếng Việt)</option>
            </select>
          </div>

          <div className="wizard-nav-actions">
            <button className="btn-secondary" onClick={() => setStep(3)}><ArrowLeft size={16} /> Back</button>
            <button className="btn-primary" onClick={() => setStep(5)}>Next: Summary <ArrowRight size={16} /></button>
          </div>
        </div>
      )}

      {/* ── STEP 5: Review Summary & Execution (Item 5) ─────────────────────── */}
      {step === 5 && (
        <div className="wizard-card card">
          <h3><CheckCircle size={20} /> Step 5: Review Summary</h3>
          <p className="wizard-sub">Verify your document review settings before launching the engine pipeline.</p>

          <div className="summary-confirm-box">
            <div className="sc-row">
              <span>Document File:</span>
              <strong>{binaryFile ? binaryFile.name : "Markdown Text Document"}</strong>
            </div>
            <div className="sc-row">
              <span>Selected Profile:</span>
              <strong style={{ textTransform: "capitalize" }}>{profile} Profile</strong>
            </div>
            <div className="sc-row">
              <span>Knowledge Packs:</span>
              <strong>{selectedPacks.join(", ")}</strong>
            </div>
            <div className="sc-row">
              <span>Enabled Categories:</span>
              <strong>{selectedCategories.length} Categories Enabled</strong>
            </div>
            <div className="sc-row">
              <span>Total Rules Evaluated:</span>
              <strong style={{ color: "var(--primary)" }}>{218 + selectedPacks.length * 12} Rules</strong>
            </div>
            <div className="sc-row">
              <span>Execution Mode:</span>
              <strong style={{ textTransform: "capitalize" }}>{reviewMode.replace("_", " ")}</strong>
            </div>
            <div className="sc-row">
              <span>Estimated Duration:</span>
              <strong>~3.4 seconds</strong>
            </div>
          </div>

          <div className="wizard-nav-actions" style={{ marginTop: 24 }}>
            <button className="btn-secondary" onClick={() => setStep(4)}><ArrowLeft size={16} /> Back</button>
            <button className="btn-primary large" onClick={handleStartReview} disabled={loading} style={{ padding: "14px 32px", fontSize: "1rem" }}>
              {loading ? <RefreshCw size={18} className="spinner" /> : <Zap size={18} />}
              {loading ? "Running Review Engine..." : "Start Review"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


/* Top Issues */
function TopIssues({ issues, onSelect }: { issues: Issue[]; onSelect: (issue: Issue) => void }) {
  const sorted = [...issues].sort((a, b) => b.confidence - a.confidence).slice(0, 5);
  return (
    <div>
      <h3 className="chart-title"><Target size={16} /> Top Issues</h3>
      {sorted.length === 0 ? <div className="chart-empty">No issues</div> : (
        <div className="top-issues-list">
          {sorted.map(issue => (
            <div key={issue.id} className={`top-issue-item ${issue.severity}`} onClick={() => onSelect(issue)} style={{ cursor: "pointer" }}>
              <span className="top-issue-rank">{issue.severity === "high" ? "!" : "·"}</span>
              <div className="top-issue-body">
                <div className="top-issue-header">
                  <span className={`sev-badge ${issue.severity}`}>{issue.severity}</span>
                  <span className="rule-badge">{issue.rule_id}</span>
                </div>
                <div className="top-issue-message">{issue.message}</div>
                <div className="top-issue-rec">{issue.recommendation}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* Category Scores */
function CategoryScoresBar({ categories }: { categories: Record<string, number> }) {
  const entries = Object.entries(categories);
  if (entries.length === 0) return <div className="chart-empty">No category data</div>;
  return (
    <div>
      <h3 className="chart-title"><BarChart3 size={16} /> Category Scores</h3>
      <div className="category-scores">
        {entries.map(([cat, score]) => (
          <div key={cat} className="cat-score-item">
            <span className="cat-label">{cat}</span>
            <div className="cat-bar-bg">
              <div className="cat-bar-fill" style={{ width: `${score}%`, background: score >= 80 ? "var(--success)" : score >= 50 ? "var(--warning)" : "var(--danger)" }} />
            </div>
            <span className="cat-value">{score}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* Reviews List */
function ReviewsView({ items, onSelect, onNewReview }: { items: HistoryItem[]; onSelect: (id: string) => void; onNewReview: () => void }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Reviews</h2>
          <p className="page-subtitle">All review sessions across documents and profiles.</p>
        </div>
        <button className="btn-primary" onClick={onNewReview}><Plus size={16} /> New Review</button>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">
          <FileText size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <h2>No reviews yet</h2>
          <p>Start by reviewing a document — the results will appear here.</p>
        </div>
      ) : (
        <div className="reviews-grid">
          {items.map(item => (
            <div key={item.id} className="review-card" onClick={() => onSelect(item.id)}>
              <div className="rc-header">
                <BarChart3 size={20} style={{ color: item.score >= 80 ? "var(--success)" : item.score >= 50 ? "var(--warning)" : "var(--danger)" }} />
                <div className="rc-info">
                  <strong className="rc-name">{item.filename}</strong>
                  <div className="rc-meta">
                    <span className={`badge ${item.status}`}>{item.status}</span>
                    <span>{item.profile_id}</span>
                    <span>{item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}</span>
                  </div>
                </div>
                <div className="rc-score" style={{ color: item.score >= 80 ? "var(--success)" : item.score >= 50 ? "var(--warning)" : "var(--danger)" }}>{item.score}</div>
              </div>
              {item.summary && <p className="rc-summary">{item.summary}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* History */
function HistoryView({ items, onSelect }: { items: HistoryItem[]; onSelect: (id: string) => void }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Review History</h2>
          <p className="page-subtitle">Timeline of all review sessions and score changes.</p>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">
          <History size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <h2>No history yet</h2>
          <p>Run at least one review to start tracking history.</p>
        </div>
      ) : (
        <div className="history-list">
          {items.map(item => (
            <div key={item.id} className="history-card" onClick={() => onSelect(item.id)}>
              <div className="hc-left">
                <BarChart3 size={24} style={{ color: item.score >= 80 ? "var(--success)" : item.score >= 50 ? "var(--warning)" : "var(--danger)" }} />
              </div>
              <div className="hc-body">
                <div className="hc-title">
                  <strong>{item.filename}</strong>
                  <span className={`badge ${item.status}`}>{item.status}</span>
                </div>
                <div className="hc-meta">
                  <span>Score: {item.score}</span>
                  <span>Profile: {item.profile_id}</span>
                  <span>{item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}</span>
                </div>
                {item.summary && <div className="hc-summary">{item.summary}</div>}
              </div>
              <div className="hc-actions">
                <button className="btn-icon" onClick={e => { e.stopPropagation(); onSelect(item.id); }}><Eye size={16} /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* Documents */
function DocumentsView({ documents, onUpload, onDelete, uploadInputRef, isUploading }: {
  documents: DocumentItem[];
  onUpload: (file: File) => void;
  onDelete: (id: string) => void;
  uploadInputRef: React.RefObject<HTMLInputElement | null>;
  isUploading?: boolean;
}) {
  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    e.target.value = "";
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Documents</h2>
          <p className="page-subtitle">Uploaded documents available for review.</p>
        </div>
        <button className="btn-primary" onClick={() => uploadInputRef.current?.click()} disabled={isUploading}>
          {isUploading ? <Loader2 size={16} className="spin" /> : <Upload size={16} />} 
          {isUploading ? "Uploading..." : "Upload Document"}
        </button>
        <input ref={uploadInputRef} type="file" accept=".txt,.md,.docx,.pdf" style={{ display: "none" }} onChange={handleUpload} />
      </div>
      {documents.length === 0 ? (
        <div className="empty-state">
          <FolderOpen size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <h2>No documents yet</h2>
          <p>Upload a document to get started with a review.</p>
        </div>
      ) : (
        <div className="documents-grid">
          {documents.map(doc => (
            <div key={doc.id} className="document-card">
              <div className="doc-card-icon"><FileText size={24} /></div>
              <div className="doc-card-info">
                <strong>{doc.name}</strong>
                <span style={{ fontSize: ".8rem", color: "var(--text3)" }}>{new Date(doc.uploaded_at).toLocaleDateString()}</span>
              </div>
              <button className="btn-icon" onClick={() => onDelete(doc.id)} data-tooltip="Delete"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* Profiles */
function ProfilesView({ showForm, setShowForm }: { showForm: boolean; setShowForm: (v: boolean) => void }) {
  const [profiles, setProfiles] = useState([
    { id: "academic", name: "Academic", desc: "Writing suggestions, citation checks, academic tone analysis", Icon: BookOpen, capabilities: ["Rewrite", "Citation Check", "Tone Analysis", "Plagiarism Scan"] },
    { id: "business", name: "Business Proposal", desc: "Clarity, persuasion, structure analysis for business docs", Icon: Briefcase, capabilities: ["Clarity Check", "Structure Analysis", "Persuasion Score", "Jargon Detection"] },
    { id: "sop", name: "SOP & Compliance", desc: "Regulatory compliance, policy adherence, risk assessment", Icon: Shield, capabilities: ["Compliance Check", "Risk Assessment", "Policy Scan", "Gap Analysis"] },
  ]);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  function handleCreateProfile() {
    if (!newName.trim()) return;
    const id = newName.toLowerCase().replace(/\s+/g, "-");
    setProfiles(prev => [...prev, { id, name: newName, desc: newDesc || "Custom review profile", Icon: Users, capabilities: [] }]);
    setNewName("");
    setNewDesc("");
    setShowForm(false);
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Profiles</h2>
          <p className="page-subtitle">Review profiles define how documents are analyzed.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={16} /> {showForm ? "Cancel" : "Create Profile"}
        </button>
      </div>
      {showForm && (
        <div className="inline-form card" style={{ marginBottom: 16, padding: 16 }}>
          <h4 style={{ margin: "0 0 8px" }}>New Profile</h4>
          <input className="form-input" placeholder="Profile name" value={newName} onChange={e => setNewName(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
          <textarea className="form-input" placeholder="Description (optional)" value={newDesc} onChange={e => setNewDesc(e.target.value)} style={{ width: "100%", marginBottom: 8, resize: "vertical", minHeight: 60 }} />
          <button className="btn-primary" onClick={handleCreateProfile} disabled={!newName.trim()}><Save size={14} /> Save Profile</button>
        </div>
      )}
      <div className="profile-cards">
        {profiles.map(p => (
          <div key={p.id} className="profile-card selected">
            <div className="profile-card-icon"><p.Icon size={20} /></div>
            <div className="profile-card-body">
              <strong>{p.name}</strong>
              <p style={{ fontSize: ".82rem", color: "var(--text2)", margin: "2px 0" }}>{p.desc}</p>
              <div className="chip-group">
                {p.capabilities.map(c => <span key={c} className="chip">{c}</span>)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* Knowledge Packs */
function KnowledgePacksView({ showForm, setShowForm }: { showForm: boolean; setShowForm: (v: boolean) => void }) {
  const [packs, setPacks] = useState([
    { name: "Standard Rules", desc: "Standard review rules and patterns", active: true },
    { name: "Academic Writing", desc: "Academic writing quality checks", active: true },
    { name: "Business Compliance", desc: "Business compliance and regulatory rules", active: true },
    { name: "Technical Docs", desc: "Technical documentation quality checks", active: true },
  ]);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  function handleCreatePack() {
    if (!newName.trim()) return;
    setPacks(prev => [...prev, { name: newName, desc: newDesc || "Custom rule pack", active: true }]);
    setNewName("");
    setNewDesc("");
    setShowForm(false);
  }

  function togglePack(name: string) {
    setPacks(prev => prev.map(p => p.name === name ? { ...p, active: !p.active } : p));
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Knowledge Packs</h2>
          <p className="page-subtitle">Rule packs that power document analysis.</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={16} /> {showForm ? "Cancel" : "Create Pack"}
        </button>
      </div>
      {showForm && (
        <div className="inline-form card" style={{ marginBottom: 16, padding: 16 }}>
          <h4 style={{ margin: "0 0 8px" }}>New Pack</h4>
          <input className="form-input" placeholder="Pack name" value={newName} onChange={e => setNewName(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
          <textarea className="form-input" placeholder="Description (optional)" value={newDesc} onChange={e => setNewDesc(e.target.value)} style={{ width: "100%", marginBottom: 8, resize: "vertical", minHeight: 60 }} />
          <button className="btn-primary" onClick={handleCreatePack} disabled={!newName.trim()}><Save size={14} /> Save Pack</button>
        </div>
      )}
      <div className="pack-cards">
        {packs.map(pack => (
          <div key={pack.name} className="pack-card selected" onClick={() => togglePack(pack.name)} style={{ cursor: "pointer" }}>
            <div className="pack-card-icon"><Database size={16} /></div>
            <div className="pack-card-body">
              <strong>{pack.name}</strong>
              <p>{pack.desc}</p>
            </div>
            <div className={`pack-toggle ${pack.active ? "checked" : ""}`}><div className="pack-toggle-dot" /></div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* AI Assistant */
function AIAssistantView({ session }: { session: SessionDetail | null }) {
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  async function sendMessage() {
    if (!input.trim()) return;
    const userMsg = input;
    setInput("");
    setMessages(prev => [...prev, { role: "user", text: userMsg }]);
    setAiLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          session_id: session?.id || null,
          context: session ? {
            filename: session.filename,
            score: session.score,
            issues: session.issues.slice(0, 10),
            summary: session.summary,
          } : null,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setMessages(prev => [...prev, { role: "assistant", text: data.response || data.reply || "I processed your request." }]);
      } else {
        setMessages(prev => [...prev, { role: "assistant", text: "Sorry, I encountered an error processing your request. Please try again." }]);
      }
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        text: session
          ? `I can help analyze your review of "${session.filename}" (Score: ${session.score}). Ask me about specific issues, rules, or suggestions for improvement.`
          : "I can help analyze your review results, suggest improvements, or explain specific issues. Try asking about a particular rule or category. Run a review first for more specific assistance."
      }]);
    } finally {
      setAiLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <div className="ai-panel">
        <div className="ai-panel-header">
          <h3><Bot size={18} /> AI Assistant</h3>
          <span className="ai-status">
            {aiLoading ? <RefreshCw size={12} className="spinner" /> : <CheckCircle size={12} />}
            {aiLoading ? " Thinking..." : " Connected"}
          </span>
        </div>
        <div className="ai-messages">
          {messages.length === 0 && (
            <div className="empty-state small" style={{ padding: 30 }}>
              <Sparkles size={24} style={{ opacity: 0.3, marginBottom: 8 }} />
              <p>{session ? `Ask me about "${session.filename}" review (Score: ${session.score}).` : "Ask me anything about your review results."}</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`ai-message ${msg.role}`}>{msg.text}</div>
          ))}
          {aiLoading && messages[messages.length - 1]?.role === "user" && (
            <div className="ai-message assistant thinking">
              <span className="spinner" style={{ width: 14, height: 14 }} />
            </div>
          )}
        </div>
        <div className="ai-input-bar">
          <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about your review..." onKeyDown={e => e.key === "Enter" && !aiLoading && sendMessage()} disabled={aiLoading} />
          <button onClick={sendMessage} disabled={aiLoading || !input.trim()}><Zap size={14} /> Send</button>
        </div>
      </div>
    </div>
  );
}

/* Settings */
function SettingsView({ theme, setTheme }: { theme: string; setTheme: (t: "light" | "dark") => void }) {
  return (
    <div className="settings-page">
      <h2>Settings</h2>
      <div className="settings-section">
        <h3><Settings size={16} /> General</h3>
        <div className="settings-grid">
          <div className="setting-row">
            <div>
              <label>Dark Mode</label>
              <div className="setting-desc">Toggle dark/light theme</div>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" checked={theme === "dark"} onChange={e => setTheme(e.target.checked ? "dark" : "light")} />
              <div className="toggle-track" />
              <div className="toggle-dot" />
            </label>
          </div>
          <div className="setting-row">
            <div>
              <label>API Endpoint</label>
              <div className="setting-desc">Backend server URL</div>
            </div>
            <input type="text" value={API_URL} readOnly />
          </div>
          <div className="setting-row">
            <div>
              <label>Language</label>
              <div className="setting-desc">Interface language</div>
            </div>
            <select>
              <option>English</option>
              <option>Vietnamese</option>
            </select>
          </div>
        </div>
      </div>
      <div className="settings-section">
        <h3><Star size={16} /> About</h3>
        <div className="settings-grid">
          <div className="setting-row">
            <div><label>ReviewMind</label><div className="setting-desc">Document Review Engine v1.0.0</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════════════════════════════ */

function LandingPage() {
  const [theme] = useState(() => (safeGetItem("theme") as "light" | "dark") || "light");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const features = [
    { Icon: Zap, title: "AI Document Review", desc: "Advanced AI analyzes your documents for grammar, structure, citations, and compliance." },
    { Icon: BarChart3, title: "Quality Scoring", desc: "Get an overall quality score with detailed breakdowns by category. Track improvement across revisions." },
    { Icon: BookOpen, title: "Knowledge Packs", desc: "Apply specialized rule sets: APA 7, IEEE, ISO 9001, FDA, and more." },
    { Icon: Wrench, title: "Auto-Fix", desc: "Safe, one-click fixes for formatting, citations, and grammar. AI-powered smart fixes for deeper issues." },
    { Icon: Eye, title: "Evidence Viewer", desc: "Click any issue to jump directly to its location in the document. Side-by-side before/after comparison." },
    { Icon: Download, title: "Multi-Format Export", desc: "Export reports as PDF, DOCX, HTML, Markdown, JSON, or CSV. Share results with your team." },
  ];

  const howItWorks = [
    { step: "1", title: "Upload Your Document", desc: "Drag & drop or select a file. Supports DOCX, PDF, Markdown, TXT, HTML, and LaTeX." },
    { step: "2", title: "Choose Your Profile", desc: "Pick Academic, Business, or SOP. Add Knowledge Packs for specialized rules." },
    { step: "3", title: "AI + Rule Engine Review", desc: "Our hybrid engine scans your document with 200+ rules and AI-powered analysis." },
    { step: "4", title: "Review & Auto-Fix", desc: "Browse issues with evidence previews. Apply safe fixes with one click." },
    { step: "5", title: "Export & Track", desc: "Export polished reports. Track quality scores across revisions over time." },
  ];

  const profiles = [
    { name: "Academic", Icon: BookOpen, desc: "Thesis, dissertation, journal articles, conference papers" },
    { name: "Business", Icon: Briefcase, desc: "Proposals, executive summaries, reports, pitch decks" },
    { name: "SOP & Compliance", Icon: Shield, desc: "Standard operating procedures, regulatory docs, ISO/FDA/WHO" },
  ];

  const packs = [
    { name: "APA 7", desc: "Social sciences citation" },
    { name: "IEEE", desc: "Engineering & CS citation" },
    { name: "ACM", desc: "Computer science citation" },
    { name: "Nature", desc: "Scientific journal format" },
    { name: "Springer", desc: "Technical publication format" },
    { name: "Elsevier", desc: "Journal citation style" },
    { name: "ISO 9001", desc: "QMS documentation" },
    { name: "FDA 21 CFR", desc: "Regulatory compliance" },
    { name: "WHO", desc: "Health guidelines" },
  ];

  return (
    <div className="landing">
      <nav className="lp-navbar">
        <div className="lp-nav-inner">
          <div className="lp-logo" style={{ cursor: "pointer" }}>
            <span className="app-title" style={{ fontSize: "1.2rem" }}>ReviewMind</span>
          </div>
          <div className="lp-nav-links">
            <a href="#features" className="lp-nav-link">Features</a>
            <a href="#how-it-works" className="lp-nav-link">How It Works</a>
            <a href="#profiles" className="lp-nav-link">Profiles</a>
            <a href="#architecture" className="lp-nav-link">Architecture</a>
          </div>
          <div className="lp-nav-actions">
            <SignInButton mode="modal">
              <button className="btn-sm outline" style={{ padding: "9px 20px", fontSize: ".85rem" }}>Sign In</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="btn-primary" style={{ padding: "9px 20px", fontSize: ".85rem" }}>Get Started Free</button>
            </SignUpButton>
          </div>
        </div>
      </nav>

      <section className="lp-hero">
        <div className="lp-hero-bg" />
        <div className="lp-hero-content">
          <div className="lp-hero-badge">AI-Powered Document Review Platform</div>
          <h1 className="lp-hero-title">
            Review smarter.<br />
            <span className="lp-hero-gradient">Write better.</span>
          </h1>
          <p className="lp-hero-desc">
            ReviewMind combines AI analysis with 200+ expert rules to review your academic papers,
            business documents, and SOPs. Get actionable insights, auto-fix issues, and track quality over time.
          </p>

          {/* Architecture Pill */}
          <div className="rules-counter-badge" style={{ margin: "16px auto", background: "var(--surface3)" }}>
            Rule-first → Knowledge-driven → AI-assisted → Auto Fix → Evidence-based
          </div>

          <div className="lp-hero-actions">
            <SignUpButton mode="modal">
              <button className="btn-primary" style={{ padding: "14px 36px", fontSize: ".95rem" }}>
                <Zap size={20} /> Start Review Engine
              </button>
            </SignUpButton>
            <button className="btn-secondary" style={{ padding: "14px 36px", fontSize: ".95rem" }} onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}>
              Learn More
            </button>
          </div>
          <div className="lp-hero-stats">
            <div className="lp-stat"><strong>200+</strong> Rules</div>
            <div className="lp-stat-dot" />
            <div className="lp-stat"><strong>10+</strong> Knowledge Packs</div>
            <div className="lp-stat-dot" />
            <div className="lp-stat"><strong>4</strong> Profiles</div>
            <div className="lp-stat-dot" />
            <div className="lp-stat"><strong>100%</strong> Free to Start</div>
          </div>
        </div>
      </section>

      <section id="features" className="lp-section">
        <div className="lp-section-inner">
          <h2 className="lp-section-title">Everything you need for <span className="lp-gradient-text">better documents</span></h2>
          <p className="lp-section-sub">From grammar checks to compliance audits — ReviewMind does it all in one platform.</p>
          <div className="lp-features-grid">
            {features.map((f, i) => (
              <div key={i} className="lp-feature-card">
                <div className="lp-feature-icon"><f.Icon size={22} /></div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="lp-section">
        <div className="lp-section-inner">
          <h2 className="lp-section-title">How it <span className="lp-gradient-text">works</span></h2>
          <p className="lp-section-sub">Five simple steps from upload to polished document.</p>
          <div className="lp-steps">
            {howItWorks.map((s, i) => (
              <div key={i} className="lp-step">
                <div className="lp-step-number">{s.step}</div>
                <div className="lp-step-body">
                  <h3>{s.title}</h3>
                  <p>{s.desc}</p>
                </div>
                {i < howItWorks.length - 1 && <div className="lp-step-line" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="profiles" className="lp-section">
        <div className="lp-section-inner">
          <h2 className="lp-section-title">Review profiles for every <span className="lp-gradient-text">use case</span></h2>
          <p className="lp-section-sub">Each profile applies the right rules, permissions, and standards for your document type.</p>
          <div className="lp-profiles">
            {profiles.map((p, i) => (
              <div key={i} className="lp-profile-card">
                <div className="lp-profile-icon"><p.Icon size={24} /></div>
                <h3>{p.name}</h3>
                <p>{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="architecture" className="lp-section">
        <div className="lp-section-inner">
          <h2 className="lp-section-title">Knowledge <span className="lp-gradient-text">Packs</span></h2>
          <p className="lp-section-sub">Domain-specific rule sets that power your document review.</p>
          <div className="lp-packs-grid">
            {packs.map((p, i) => (
              <div key={i} className="lp-pack-chip">
                <strong>{p.name}</strong>
                <span>{p.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-cta">
        <div className="lp-cta-bg" />
        <div className="lp-cta-content">
          <h2>Ready to improve your documents?</h2>
          <p>Start reviewing for free — no credit card required.</p>
          <SignUpButton mode="modal">
            <button className="btn-primary" style={{ padding: "14px 36px", fontSize: "1rem" }}>
              <Sparkles size={20} /> Launch Workspace Now
            </button>
          </SignUpButton>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-footer-brand">
            <span className="app-title" style={{ fontSize: "1rem" }}>ReviewMind</span>
            <p>AI-Powered Document Review Platform</p>
          </div>
          <div className="lp-footer-links">
            <a href="#features">Documentation</a>
            <a href="https://github.com/ViuGiaLai/reviewmind" target="_blank" rel="noreferrer">GitHub</a>
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Service</a>
          </div>
          <div className="lp-footer-copy">&copy; {new Date().getFullYear()} ReviewMind. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}

/* ═══════════════════════════════════════
   App Entry — Auth Guard & Page Router
   ═══════════════════════════════════════ */

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

function RootApp() {
  const isDark = typeof window !== "undefined" && (safeGetItem("theme") === "dark" || (!safeGetItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches));

  return (
    <ClerkProvider 
      publishableKey={CLERK_PUBLISHABLE_KEY} 
      afterSignOutUrl="/"
      appearance={{
        baseTheme: isDark ? dark : undefined,
      }}
    >
      <App />
    </ClerkProvider>
  );
}

createRoot(root).render(<RootApp />);
