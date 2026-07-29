import { useEffect, useMemo, useState } from "react";
import {
  Bot, BookOpen, Check, FilePen, Layers3, Lock, Pencil, Plus,
  Save, ShieldCheck, Sparkles, Trash2, WandSparkles, X
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ApiFetch, EvaluationProfile } from "../domain/types";

interface BaseProfile {
  id: string;
  name: string;
  document_types: string[];
  categories: string[];
  weights: Record<string, number>;
}

interface PackOption {
  id: string;
  name: string;
  profile: string;
  description: string;
}

interface TemplateOption {
  id: string;
  original_name: string;
}

interface ProfileOptions {
  base_profiles: BaseProfile[];
  knowledge_packs: PackOption[];
  templates: TemplateOption[];
}

const emptyForm: Omit<EvaluationProfile, "id"> = {
  name: "",
  description: "",
  base_profile_id: "academic",
  document_types: ["thesis"],
  knowledge_pack_ids: [],
  reference_template_id: null,
  enabled_categories: ["structure", "writing", "citation", "formatting"],
  ai_review_enabled: true,
  auto_fix_enabled: false,
  scoring_profile: "weighted",
  language: "vi",
  review_mode: "standard",
  visibility: "private",
};

export function EvaluationProfilesView({
  profiles,
  setProfiles,
  showForm,
  setShowForm,
  apiFetch,
  apiUrl,
}: {
  profiles: EvaluationProfile[];
  setProfiles: React.Dispatch<React.SetStateAction<EvaluationProfile[]>>;
  showForm: boolean;
  setShowForm: (value: boolean) => void;
  apiFetch: ApiFetch;
  apiUrl: string;
}) {
  const { t } = useTranslation();
  const [options, setOptions] = useState<ProfileOptions>({
    base_profiles: [],
    knowledge_packs: [],
    templates: [],
  });
  const [form, setForm] = useState<Omit<EvaluationProfile, "id">>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void apiFetch(`${apiUrl}/api/evaluation-profiles/options`)
      .then(async response => {
        if (!response.ok) throw new Error(await response.text());
        return response.json();
      })
      .then(data => { if (active) setOptions(data); })
      .catch(() => { if (active) setError(t("profiles.options_error")); });
    return () => { active = false; };
  }, [apiFetch, apiUrl, t]);

  const selectedBase = useMemo(
    () => options.base_profiles.find(item => item.id === form.base_profile_id),
    [form.base_profile_id, options.base_profiles],
  );

  function startCreate() {
    const base = options.base_profiles.find(item => item.id === "academic");
    setEditingId(null);
    setForm({
      ...emptyForm,
      document_types: base?.document_types || emptyForm.document_types,
      enabled_categories: base?.categories || emptyForm.enabled_categories,
    });
    setError("");
    setShowForm(true);
  }

  function startEdit(profile: EvaluationProfile) {
    setEditingId(profile.id);
    setForm({
      name: profile.name,
      description: profile.description,
      base_profile_id: profile.base_profile_id,
      document_types: profile.document_types,
      knowledge_pack_ids: profile.knowledge_pack_ids,
      reference_template_id: profile.reference_template_id,
      enabled_categories: profile.enabled_categories,
      ai_review_enabled: profile.ai_review_enabled,
      auto_fix_enabled: profile.auto_fix_enabled,
      scoring_profile: profile.scoring_profile,
      language: profile.language,
      review_mode: profile.review_mode,
      visibility: "private",
    });
    setError("");
    setShowForm(true);
  }

  function changeBase(baseId: string) {
    const base = options.base_profiles.find(item => item.id === baseId);
    setForm(current => ({
      ...current,
      base_profile_id: baseId,
      document_types: base?.document_types || [],
      enabled_categories: base?.categories || [],
      knowledge_pack_ids: current.knowledge_pack_ids.filter(packId => {
        const pack = options.knowledge_packs.find(item => item.id === packId);
        return !pack?.profile || pack.profile === baseId;
      }),
    }));
  }

  function toggleList(field: "document_types" | "knowledge_pack_ids" | "enabled_categories", value: string) {
    setForm(current => {
      const values = current[field];
      return {
        ...current,
        [field]: values.includes(value)
          ? values.filter(item => item !== value)
          : [...values, value],
      };
    });
  }

  async function save() {
    if (form.name.trim().length < 2) return;
    setSaving(true);
    setError("");
    try {
      const response = await apiFetch(
        `${apiUrl}/api/evaluation-profiles${editingId ? `/${editingId}` : ""}`,
        {
          method: editingId ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...form, name: form.name.trim(), description: form.description.trim() }),
        },
      );
      if (!response.ok) throw new Error(await response.text());
      const saved: EvaluationProfile = await response.json();
      setProfiles(current => editingId
        ? current.map(item => item.id === editingId ? saved : item)
        : [saved, ...current]);
      setShowForm(false);
      setEditingId(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("profiles.save_error"));
    } finally {
      setSaving(false);
    }
  }

  async function remove(profile: EvaluationProfile) {
    if (!window.confirm(t("profiles.delete_confirm", { name: profile.name }))) return;
    const response = await apiFetch(`${apiUrl}/api/evaluation-profiles/${profile.id}`, { method: "DELETE" });
    if (response.ok) setProfiles(current => current.filter(item => item.id !== profile.id));
    else setError(t("profiles.delete_error"));
  }

  const compatiblePacks = options.knowledge_packs.filter(
    item => !item.profile || item.profile === form.base_profile_id,
  );

  return (
    <section className="page-stack evaluation-profiles">
      <div className="page-header profiles-hero">
        <div>
          <div className="page-eyebrow"><Sparkles size={14} /> {t("profiles.eyebrow")}</div>
          <h2>{t("profiles.title")}</h2>
          <p className="page-subtitle">{t("profiles.subtitle")}</p>
        </div>
        <button className="btn-primary" onClick={showForm ? () => setShowForm(false) : startCreate}>
          {showForm ? <X size={16} /> : <Plus size={16} />}
          {showForm ? t("common.cancel") : t("profiles.create")}
        </button>
      </div>

      <div className="profile-principle">
        <ShieldCheck size={20} />
        <div>
          <strong>{t("profiles.principle_title")}</strong>
          <p>{t("profiles.principle_desc")}</p>
        </div>
      </div>

      {showForm && (
        <div className="profile-editor card">
          <div className="profile-editor-head">
            <div>
              <span className="step-badge">{editingId ? t("profiles.edit") : t("profiles.new")}</span>
              <h3>{t("profiles.configure_title")}</h3>
              <p>{t("profiles.configure_desc")}</p>
            </div>
          </div>

          <div className="profile-form-section">
            <div className="profile-form-heading"><FilePen size={17} /><span>{t("profiles.basic_info")}</span></div>
            <div className="profile-form-grid">
              <label className="field">
                <span>{t("profiles.name_label")}</span>
                <input className="form-input" value={form.name} maxLength={120}
                  placeholder={t("profiles.name_placeholder")}
                  onChange={event => setForm({ ...form, name: event.target.value })} />
              </label>
              <label className="field field-wide">
                <span>{t("profiles.desc_label")}</span>
                <textarea className="form-input" value={form.description} maxLength={1000}
                  placeholder={t("profiles.desc_placeholder")}
                  onChange={event => setForm({ ...form, description: event.target.value })} />
              </label>
            </div>
          </div>

          <div className="profile-form-section">
            <div className="profile-form-heading"><Layers3 size={17} /><span>{t("profiles.review_standard")}</span></div>
            <div className="profile-form-grid">
              <label className="field">
                <span>{t("profiles.base_profile")}</span>
                <select className="form-input" value={form.base_profile_id} onChange={event => changeBase(event.target.value)}>
                  {options.base_profiles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label className="field">
                <span>{t("profiles.template")}</span>
                <select className="form-input" value={form.reference_template_id || ""}
                  onChange={event => setForm({ ...form, reference_template_id: event.target.value || null })}>
                  <option value="">{t("profiles.no_template")}</option>
                  {options.templates.map(item => <option key={item.id} value={item.id}>{item.original_name}</option>)}
                </select>
              </label>
              <label className="field">
                <span>{t("profiles.scoring")}</span>
                <select className="form-input" value={form.scoring_profile}
                  onChange={event => setForm({ ...form, scoring_profile: event.target.value as "weighted" | "equal" })}>
                  <option value="weighted">{t("profiles.scoring_weighted")}</option>
                  <option value="equal">{t("profiles.scoring_equal")}</option>
                </select>
              </label>
              <label className="field">
                <span>{t("profiles.strictness")}</span>
                <select className="form-input" value={form.review_mode}
                  onChange={event => setForm({ ...form, review_mode: event.target.value as EvaluationProfile["review_mode"] })}>
                  <option value="strict">{t("profiles.strict")}</option>
                  <option value="standard">{t("profiles.standard")}</option>
                  <option value="relaxed">{t("profiles.relaxed")}</option>
                </select>
              </label>
              <label className="field">
                <span>{t("profiles.language")}</span>
                <select className="form-input" value={form.language}
                  onChange={event => setForm({ ...form, language: event.target.value as "vi" | "en" })}>
                  <option value="vi">{t("common.vietnamese")}</option>
                  <option value="en">{t("common.english")}</option>
                </select>
              </label>
              <div className="field">
                <span>{t("profiles.visibility")}</span>
                <div className="locked-value"><Lock size={14} /> {t("profiles.private")}</div>
              </div>
            </div>
          </div>

          <div className="profile-form-section">
            <div className="profile-form-heading"><BookOpen size={17} /><span>{t("profiles.rule_set")}</span></div>
            <div className="option-block">
              <span>{t("profiles.document_types")}</span>
              <div className="selectable-chips">
                {(selectedBase?.document_types || []).map(item => (
                  <button key={item} type="button" className={form.document_types.includes(item) ? "selected" : ""}
                    onClick={() => toggleList("document_types", item)}>
                    {form.document_types.includes(item) && <Check size={13} />}{item.replaceAll("_", " ")}
                  </button>
                ))}
              </div>
            </div>
            <div className="option-block">
              <span>{t("profiles.categories")}</span>
              <div className="selectable-chips">
                {(selectedBase?.categories || []).map(item => (
                  <button key={item} type="button" className={form.enabled_categories.includes(item) ? "selected" : ""}
                    onClick={() => toggleList("enabled_categories", item)}>
                    {form.enabled_categories.includes(item) && <Check size={13} />}{item}
                  </button>
                ))}
              </div>
            </div>
            <div className="option-block">
              <span>{t("profiles.knowledge_packs")}</span>
              <div className="profile-pack-grid">
                {compatiblePacks.map(pack => (
                  <button key={pack.id} type="button"
                    className={form.knowledge_pack_ids.includes(pack.id) ? "selected" : ""}
                    onClick={() => toggleList("knowledge_pack_ids", pack.id)}>
                    <WandSparkles size={15} />
                    <span><strong>{pack.name}</strong><small>{pack.description}</small></span>
                    {form.knowledge_pack_ids.includes(pack.id) && <Check size={15} />}
                  </button>
                ))}
                {compatiblePacks.length === 0 && <p className="muted">{t("profiles.no_packs")}</p>}
              </div>
            </div>
          </div>

          <div className="profile-capability-grid">
            <button type="button" className={form.ai_review_enabled ? "enabled" : ""}
              onClick={() => setForm({ ...form, ai_review_enabled: !form.ai_review_enabled })}>
              <Bot size={20} /><span><strong>{t("profiles.ai_review")}</strong><small>{t("profiles.ai_review_desc")}</small></span>
              <span className="status-pill">{t(form.ai_review_enabled ? "common.on" : "common.off")}</span>
            </button>
            <button type="button" className={form.auto_fix_enabled ? "enabled" : ""}
              onClick={() => setForm({ ...form, auto_fix_enabled: !form.auto_fix_enabled })}>
              <WandSparkles size={20} /><span><strong>{t("profiles.auto_fix")}</strong><small>{t("profiles.auto_fix_desc")}</small></span>
              <span className="status-pill">{t(form.auto_fix_enabled ? "common.on" : "common.off")}</span>
            </button>
          </div>

          {error && <div className="form-error">{error}</div>}
          <div className="profile-editor-actions">
            <button className="btn-secondary" onClick={() => setShowForm(false)}>{t("common.cancel")}</button>
            <button className="btn-primary" disabled={saving || form.name.trim().length < 2 || form.enabled_categories.length === 0}
              onClick={save}>
              <Save size={15} /> {saving ? t("common.saving") : t("profiles.save")}
            </button>
          </div>
        </div>
      )}

      {!showForm && profiles.length === 0 && (
        <div className="empty-state profile-empty">
          <Layers3 size={38} />
          <h3>{t("profiles.empty_title")}</h3>
          <p>{t("profiles.empty_desc")}</p>
          <button className="btn-primary" onClick={startCreate}><Plus size={15} /> {t("profiles.create_first")}</button>
        </div>
      )}

      <div className="evaluation-profile-grid">
        {profiles.map(profile => (
          <article className="evaluation-profile-card" key={profile.id}>
            <div className="ep-card-head">
              <div className="ep-icon"><Layers3 size={20} /></div>
              <div><strong>{profile.name}</strong><span>{profile.base_profile_id.replaceAll("_", " ")}</span></div>
              <div className="ep-actions">
                <button className="btn-icon" aria-label={t("common.edit")} onClick={() => startEdit(profile)}><Pencil size={14} /></button>
                <button className="btn-icon danger" aria-label={t("common.delete")} onClick={() => remove(profile)}><Trash2 size={14} /></button>
              </div>
            </div>
            <p>{profile.description || t("profiles.custom_desc")}</p>
            <div className="ep-config-row">
              <span><BookOpen size={13} /> {profile.enabled_categories.length} {t("profiles.rules_short")}</span>
              <span><WandSparkles size={13} /> {profile.knowledge_pack_ids.length} {t("profiles.packs_short")}</span>
              <span><FilePen size={13} /> {profile.template_name || t("profiles.no_template")}</span>
            </div>
            <div className="ep-footer">
              <span className={`feature-state ${profile.ai_review_enabled ? "on" : ""}`}><Bot size={12} /> {t("profiles.ai_review")}</span>
              <span className={`feature-state ${profile.auto_fix_enabled ? "on" : ""}`}><WandSparkles size={12} /> {t("profiles.auto_fix")}</span>
              <span className="mode-badge">{t(`profiles.${profile.review_mode}`)}</span>
              <span className="private-badge"><Lock size={11} /> {t("profiles.private")}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
