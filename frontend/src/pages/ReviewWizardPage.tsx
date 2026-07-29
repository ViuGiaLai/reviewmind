import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react";import type { ApiFetch, DocumentItem, EvaluationProfile, ReferenceTemplateItem } from "../domain/types";
import { safeGetItem, safeSetItem } from "../lib/storage";
export function ReviewWizardView({
  storageScope,
  profile,
  setProfile,
  loading,
  onSubmit,
  documents,
  selectedDocumentId,
  setSelectedDocumentId,
  apiFetch,
  API_URL,
  templates,
  selectedTemplateId,
  setSelectedTemplateId,
  evaluationProfiles,
}: {
  storageScope: string;
  profile: string;
  setProfile: (v: string) => void;
  loading: boolean;
  onSubmit: (options?: any) => void;
  documents: DocumentItem[];
  selectedDocumentId: string | null;
  setSelectedDocumentId: (id: string | null) => void;
  apiFetch: ApiFetch;
  API_URL: string;
  templates: ReferenceTemplateItem[];
  selectedTemplateId: string | null;
  setSelectedTemplateId: (id: string | null) => void;
  evaluationProfiles: EvaluationProfile[];
}) {
  const { t } = useTranslation();
  const storageKey = (name: string) => `reviewmind:${storageScope}:wizard:${name}`;
  const [step, setStep] = useState<number>(() => Number(safeGetItem(storageKey("step"))) || 1);
  const [selectedPacks, setSelectedPacks] = useState<string[]>(() => {
    try { return JSON.parse(safeGetItem(storageKey("packs")) || '["academic-base"]'); } catch { return ["academic-base"]; }
  });
  const [selectedCategories, setSelectedCategories] = useState<string[]>(() => {
    try { return JSON.parse(safeGetItem(storageKey("categories")) || '["structure", "writing", "citation", "logic", "compliance", "figures", "tables"]'); } catch { return ["structure", "writing", "citation", "logic", "compliance", "figures", "tables"]; }
  });
  const [reviewMode, setReviewMode] = useState<"rule_only" | "rule_ai" | "full">(() => (safeGetItem(storageKey("mode")) as any) || "rule_ai");
  const [language, setLanguage] = useState<"en" | "vi">(() => (safeGetItem(storageKey("language")) as any) || "en");
  const [text, setText] = useState(() => safeGetItem(storageKey("text")) || "");
  const [binaryFile, setBinaryFile] = useState<File | null>(null);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [uploadMode, setUploadMode] = useState<"upload" | "select" | null>(null);

  useEffect(() => {
    safeSetItem(storageKey("step"), step.toString());
    safeSetItem(storageKey("packs"), JSON.stringify(selectedPacks));
    safeSetItem(storageKey("categories"), JSON.stringify(selectedCategories));
    safeSetItem(storageKey("mode"), reviewMode);
    safeSetItem(storageKey("language"), language);
    safeSetItem(storageKey("text"), text);
  }, [storageScope, step, selectedPacks, selectedCategories, reviewMode, language, text]);

  const [showPreview, setShowPreview] = useState<boolean>(false);
  const wizardUploadRef = useRef<HTMLInputElement>(null);

  // Auto-detect profile from document content
  const detectedProfileInfo = useMemo(() => {
    const lowered = (binaryFile ? binaryFile.name : text).toLowerCase();
    if (lowered.includes("design") || lowered.includes("architecture") || lowered.includes("schema") || lowered.includes("component") || lowered.includes(".yaml")) {
      return { id: "technical_design", name: t("wizard.profile_technical_design_name"), confidence: 94 };
    }
    if (lowered.includes("proposal") || lowered.includes("business") || lowered.includes("executive") || lowered.includes("budget")) {
      return { id: "business", name: t("wizard.profile_business_name"), confidence: 91 };
    }
    if (lowered.includes("sop") || lowered.includes("procedure") || lowered.includes("compliance") || lowered.includes("safety")) {
      return { id: "sop", name: t("wizard.profile_sop_name"), confidence: 89 };
    }
    return { id: "academic", name: t("wizard.profile_academic_name"), confidence: 93 };
  }, [text, binaryFile, t]);

  const profilesList = [
    { id: "academic", name: t("wizard.profile_academic_name"), desc: t("wizard.profile_academic_desc"), Icon: BookOpen },
    { id: "business", name: t("wizard.profile_business_name"), desc: t("wizard.profile_business_desc"), Icon: Briefcase },
    { id: "sop", name: t("wizard.profile_sop_name"), desc: t("wizard.profile_sop_desc"), Icon: Shield },
    { id: "technical_design", name: t("wizard.profile_technical_design_name"), desc: t("wizard.profile_technical_design_desc"), Icon: Database },
    ...evaluationProfiles.map(item => ({ id: item.id, name: item.name, desc: item.description || t("profiles.custom_desc"), Icon: Sliders })),
  ];
  function applyProfile(profileId: string) {
    setProfile(profileId);
    const custom = evaluationProfiles.find(item => item.id === profileId);
    if (!custom) return;
    setSelectedPacks(custom.knowledge_pack_ids);
    setSelectedCategories(custom.enabled_categories);
    setReviewMode(custom.ai_review_enabled ? "rule_ai" : "rule_only");
    setLanguage(custom.language);
    setSelectedTemplateId(custom.reference_template_id);
  }

  const packsList = [
    { id: "academic-base", name: t("wizard.pack_academic_base_name"), desc: t("wizard.pack_academic_base_desc"), category: t("wizard.category_base"), active: true },
    { id: "ieee", name: t("wizard.pack_ieee_name"), desc: t("wizard.pack_ieee_desc"), category: t("wizard.category_citation") },
    { id: "apa", name: t("wizard.pack_apa7_name"), desc: t("wizard.pack_apa7_desc"), category: t("wizard.category_citation") },
    { id: "acm", name: t("wizard.pack_acm_name"), desc: t("wizard.pack_acm_desc"), category: t("wizard.category_citation") },
    { id: "nature", name: t("wizard.pack_nature_name"), desc: t("wizard.pack_nature_desc"), category: t("wizard.category_journal") },
    { id: "iso9001", name: t("wizard.pack_iso9001_name"), desc: t("wizard.pack_iso9001_desc"), category: t("wizard.category_compliance") },
    { id: "fda", name: t("wizard.pack_fda21_name"), desc: t("wizard.pack_fda21_desc"), category: t("wizard.category_compliance") },
  ];
  const categoriesList = [
    { id: "structure", label: t("wizard.cat_structure"), desc: t("wizard.cat_structure_desc") },
    { id: "writing", label: t("wizard.cat_writing"), desc: t("wizard.cat_writing_desc") },
    { id: "citation", label: t("wizard.cat_citation"), desc: t("wizard.cat_citation_desc") },
    { id: "logic", label: t("wizard.cat_logic"), desc: t("wizard.cat_logic_desc") },
    { id: "compliance", label: t("wizard.cat_compliance"), desc: t("wizard.cat_compliance_desc") },
    { id: "figures", label: t("wizard.cat_figures"), desc: t("wizard.cat_figures_desc") },
    { id: "tables", label: t("wizard.cat_tables"), desc: t("wizard.cat_tables_desc") },
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
      } else {
        throw new Error(await response.text());
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      alert(t("errors.upload_failed", { message: error instanceof Error ? error.message : t("common.unknown_error") }));
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
      report_language: language,
      text: text,
      document_id: selectedDocumentId,
      template_id: selectedTemplateId,
    });
  }

  return (
    <div className="wizard-layout">
      {/* ── Wizard Steps Header ───────────────────────────────────────────────── */}
      <div className="wizard-stepper card">
        {[
          { num: 1, label: t("wizard.step_1"), Icon: Upload },
          { num: 2, label: t("wizard.step_2"), Icon: Target },
          { num: 3, label: t("wizard.step_3"), Icon: BookOpen },
          { num: 4, label: t("wizard.step_4"), Icon: Sliders },
          { num: 5, label: t("wizard.start_review"), Icon: CheckCircle },
        ].map((st) => (
          <div key={st.num} className={`wizard-step-item ${step === st.num ? "active" : step > st.num ? "completed" : ""}`} onClick={() => setStep(st.num)}>
            <div className="step-badge">{step > st.num ? <Check size={14} /> : st.num}</div>
            <div className="step-info">
              <span className="step-num-text">{t("wizard.step_label", { step: st.num })}</span>
              <span className="step-label-text">{st.label}</span>
            </div>
            {st.num < 5 && <div className="step-connector" />}
          </div>
        ))}
      </div>

      {/* ── STEP 1: Upload Document (Item 1, 2) ─────────────────────────────── */}
      {step === 1 && (
        <div className="wizard-card card">
          <h3><Upload size={20} /> {t("wizard.s1_title")}</h3>
          <p className="wizard-sub">{t("wizard.s1_desc")}</p>

          {/* ── Option Cards: Upload New or Select Existing ── */}
          {!selectedDocumentId && !binaryFile && !text && (
            <div className="wizard-source-options">
              <div className="card source-option-card" role="button" tabIndex={0} onClick={() => wizardUploadRef.current?.click()} onKeyDown={event => (event.key === "Enter" || event.key === " ") && wizardUploadRef.current?.click()}>
                <Upload size={36} className="soc-icon" />
                <strong>{t("wizard.upload_new")}</strong>
                <p>{t("wizard.upload_new_desc")}</p>
                <span className="soc-action">{t("wizard.choose_file")}</span>
                <input ref={wizardUploadRef} type="file" accept=".docx,.pdf,.txt,.md,.markdown,.html,.tex" style={{ display: "none" }} onChange={handleFileSelect} />
              </div>
              {documents.length > 0 && (
                <div className="card source-option-card">
                  <FolderOpen size={36} className="soc-icon" />
                  <strong>{t("wizard.select_existing")}</strong>
                  <p>{t("wizard.select_existing_desc")}</p>
                  <div className="existing-docs-list">
                    {documents.map(doc => (
                      <div key={doc.id} className={`existing-doc-item ${selectedDocumentId === doc.id ? "selected" : ""}`} role="button" tabIndex={0} onClick={() => handleSelectDocument(doc.id)} onKeyDown={event => (event.key === "Enter" || event.key === " ") && handleSelectDocument(doc.id)}>
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
                        <span className="status-tag ready"><CheckCircle size={12} /> {t("wizard.uploaded_ready")}</span>
                      </div>
                    </>
                  ) : (
                    (() => {
                      const doc = documents.find(d => d.id === selectedDocumentId);
                      return (
                        <>
                          <strong>{doc ? doc.name : t("wizard.selected_document")}</strong>
                          <div className="ufc-tags">
                            <span className="format-tag">DOC</span>
                            {doc && <span className="size-tag">{new Date(doc.uploaded_at).toLocaleDateString()}</span>}
                            <span className="status-tag ready"><CheckCircle size={12} /> {t("common.selected")}</span>
                          </div>
                        </>
                      );
                    })()
                  )}
                </div>
              </div>
              <div className="ufc-actions">
                <button className="btn-danger-outline" onClick={handleClearSelection}>
                  <Trash2 size={14} /> {t("wizard.clear")}
                </button>
              </div>
            </div>
          )}

          {/* Progress / Loading */}
          {isUploadingDoc && (
            <div className="wizard-upload-progress">
              <Loader2 size={20} className="spin" />
              <span>{t("wizard.uploading")}</span>
            </div>
          )}

          {/* Quick Stats (when pasted text) */}
          {text && (
            <div className="quick-stats-bar">
              <div className="qs-item"><span className="qs-lbl">{t("wizard.words")}</span><strong>{text.split(/\s+/).filter(Boolean).length}</strong></div>
              <div className="qs-item"><span className="qs-lbl">{t("wizard.paragraphs")}</span><strong>{text.split("\n\n").filter(Boolean).length}</strong></div>
              <div className="qs-item"><span className="qs-lbl">{t("wizard.characters")}</span><strong>{text.length}</strong></div>
            </div>
          )}

          <div className="wizard-nav-actions">
            <button className="btn-primary" disabled={!selectedDocumentId && !binaryFile && !text} onClick={() => setStep(2)}>
              {t("wizard.next_profile")}
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 2: Profile Selection & Auto Detect (Item 1, 13) ─────────────── */}
      {step === 2 && (
        <div className="wizard-card card">
          <h3><Target size={20} /> {t("wizard.s2_title")}</h3>
          <p className="wizard-sub">{t("wizard.s2_desc")}</p>

          {/* Auto-Detect Banner */}
          <div className="auto-detect-banner">
            <div className="adb-left">
              <Sparkles size={20} className="adb-icon" />
              <div>
                <strong>{t("wizard.auto_detected")} {detectedProfileInfo.name}</strong>
                <p>{t("wizard.detection_reason")} · {t("wizard.confidence", { value: detectedProfileInfo.confidence })}</p>
              </div>
            </div>
            <button className="btn-primary" style={{ padding: "8px 16px", fontSize: ".82rem" }} onClick={() => applyProfile(detectedProfileInfo.id)}>
              {t("wizard.use_detected")}
            </button>
          </div>

          {/* Profiles Grid */}
          <div className="profiles-select-grid">
            {profilesList.map(p => (
              <div key={p.id} className={`profile-select-card ${profile === p.id ? "selected" : ""}`} role="button" tabIndex={0} onClick={() => applyProfile(p.id)} onKeyDown={event => (event.key === "Enter" || event.key === " ") && applyProfile(p.id)}>
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
            <strong>{t("wizard.permission_matrix", { profile: profilesList.find(p => p.id === profile)?.name || profile })}</strong>
            <p>
              {profile === "academic" && t("wizard.permission_academic")}
              {profile === "sop" && t("wizard.permission_sop")}
              {profile === "business" && t("wizard.permission_business")}
              {profile === "technical_design" && t("wizard.permission_technical_design")}
            </p>
          </div>

          <div className="wizard-nav-actions">
            <button className="btn-secondary" onClick={() => setStep(1)}><ArrowLeft size={16} /> {t("common.back")}</button>
            <button className="btn-primary" onClick={() => setStep(3)}>{t("wizard.next_pack")}</button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Knowledge Pack Selection (Item 1, 3, 13) ────────────────── */}
      {step === 3 && (
        <div className="wizard-card card">
          <h3><BookOpen size={20} /> {t("wizard.s3_title")}</h3>
          <p className="wizard-sub">{t("wizard.s3_desc")}</p>

          <div className="wizard-section template-picker-section">
            <div className="template-picker-heading">
              <div>
                <h4>{t("wizard.reference_template")}</h4>
                <p>{t("wizard.reference_template_desc")}</p>
              </div>
              <span className="content-safe-badge"><Shield size={14} /> {t("wizard.content_stays_yours")}</span>
            </div>
            <div className="template-choice-grid">
              <button className={`template-choice ${!selectedTemplateId ? "selected" : ""}`} onClick={() => setSelectedTemplateId(null)}>
                <CircleX size={18} />
                <strong>{t("wizard.no_template")}</strong>
                <span>{t("wizard.no_template_desc")}</span>
              </button>
              {templates.map(item => (
                <button key={item.id} className={`template-choice ${selectedTemplateId === item.id ? "selected" : ""}`} onClick={() => setSelectedTemplateId(item.id)}>
                  <FilePen size={18} />
                  <strong>{item.original_name}</strong>
                  <span>{item.analysis.body?.font_name || t("templates.detected_format")} · {item.analysis.required_sections?.length || 0} {t("templates.sections")}</span>
                </button>
              ))}
            </div>
            {templates.length === 0 && <p className="template-empty-hint">{t("wizard.add_template_hint")}</p>}
          </div>
          <div className="packs-select-grid">
            {packsList.map(pk => {
              const isSelected = selectedPacks.includes(pk.id);
              return (
                <div key={pk.id} className={`pack-select-card ${isSelected ? "selected" : ""}`} role="button" tabIndex={0} onClick={() => togglePack(pk.id)} onKeyDown={event => (event.key === "Enter" || event.key === " ") && togglePack(pk.id)}>
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
            <Shield size={16} /> {t("wizard.active_rules", { count: 218 + selectedPacks.length * 12 })}
          </div>

          <div className="wizard-nav-actions">
            <button className="btn-secondary" onClick={() => setStep(2)}><ArrowLeft size={16} /> {t("common.back")}</button>
            <button className="btn-primary" onClick={() => setStep(4)}>{t("wizard.next_config")}</button>
          </div>
        </div>
      )}

      {/* ── STEP 4: Review Configuration & Categories (Item 4, 13) ──────────── */}
      {step === 4 && (
        <div className="wizard-card card">
          <h3><Sliders size={20} /> {t("wizard.s4_title")}</h3>
          <p className="wizard-sub">{t("wizard.s4_desc")}</p>

          {/* Categories Toggles */}
          <div className="wizard-section">
            <h4>{t("wizard.rule_categories")} · {t("wizard.selected_count", { selected: selectedCategories.length, total: categoriesList.length })}</h4>
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
            <h4>{t("wizard.review_mode")}</h4>
            <div className="modes-grid">
              <label className={`mode-card ${reviewMode === "rule_only" ? "selected" : ""}`}>
                <input type="radio" name="mode" checked={reviewMode === "rule_only"} onChange={() => setReviewMode("rule_only")} />
                <div>
                  <strong>⚡ {t("wizard.mode_fast")}</strong>
                  <p>{t("wizard.mode_fast_desc")}</p>
                </div>
              </label>
              <label className={`mode-card ${reviewMode === "rule_ai" ? "selected" : ""}`}>
                <input type="radio" name="mode" checked={reviewMode === "rule_ai"} onChange={() => setReviewMode("rule_ai")} />
                <div>
                  <strong>🤖 {t("wizard.mode_ai")}</strong>
                  <p>{t("wizard.mode_ai_desc")}</p>
                </div>
              </label>
              <label className={`mode-card ${reviewMode === "full" ? "selected" : ""}`}>
                <input type="radio" name="mode" checked={reviewMode === "full"} onChange={() => setReviewMode("full")} />
                <div>
                  <strong>🛠️ {t("wizard.mode_full")}</strong>
                  <p>{t("wizard.mode_full_desc")}</p>
                </div>
              </label>
            </div>
          </div>

          {/* Language Selection */}
          <div className="setting-row" style={{ marginTop: 16, maxWidth: 300 }}>
            <label>{t("wizard.report_language")}</label>
            <select value={language} onChange={e => setLanguage(e.target.value as any)}>
              <option value="en">{t("common.english")}</option>
              <option value="vi">{t("common.vietnamese")}</option>
            </select>
          </div>

          <div className="wizard-nav-actions">
            <button className="btn-secondary" onClick={() => setStep(3)}><ArrowLeft size={16} /> {t("common.back")}</button>
            <button className="btn-primary" onClick={() => setStep(5)}>{t("wizard.next_summary")}</button>
          </div>
        </div>
      )}

      {/* ── STEP 5: Review Summary & Execution (Item 5) ─────────────────────── */}
      {step === 5 && (
        <div className="wizard-card card">
          <h3><CheckCircle size={20} /> {t("wizard.s5_title")}</h3>
          <p className="wizard-sub">{t("wizard.s5_desc")}</p>

          <div className="summary-confirm-box">
            <div className="sc-row">
              <span>{t("wizard.document")}:</span>
              <strong>{binaryFile ? binaryFile.name : t("wizard.markdown_document")}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.profile_selected")}:</span>
              <strong style={{ textTransform: "capitalize" }}>{profilesList.find(p => p.id === profile)?.name || profile}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.reference_template")}:</span>
              <strong>{templates.find(item => item.id === selectedTemplateId)?.original_name || t("wizard.no_template")}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.packs_loaded")}:</span>
              <strong>{selectedPacks.join(", ")}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.categories_active")}:</span>
              <strong>{t("wizard.selected_count", { selected: selectedCategories.length, total: categoriesList.length })}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.total_rules")}:</span>
              <strong style={{ color: "var(--primary)" }}>{t("dashboard.rule_count", { count: 218 + selectedPacks.length * 12 })}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.execution_mode")}:</span>
              <strong style={{ textTransform: "capitalize" }}>{reviewMode.replace("_", " ")}</strong>
            </div>
            <div className="sc-row">
              <span>{t("wizard.estimated_duration")}:</span>
              <strong>{t("wizard.duration_value")}</strong>
            </div>
          </div>

          <div className="wizard-nav-actions" style={{ marginTop: 24 }}>
            <button className="btn-secondary" onClick={() => setStep(4)}><ArrowLeft size={16} /> {t("common.back")}</button>
            <button className="btn-primary large" onClick={handleStartReview} disabled={loading} style={{ padding: "14px 32px", fontSize: "1rem" }}>
              {loading ? <RefreshCw size={18} className="spinner" /> : <Zap size={18} />}
              {loading ? t("wizard.running") : t("wizard.run_review")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


/* Result charts */
