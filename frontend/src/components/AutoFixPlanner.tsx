import React, { useState, useEffect } from "react";
import { Zap, CheckCircle, CircleX, AlertTriangle, ChevronRight, X, Loader2, FilePen, Check } from "lucide-react";
import { useTranslation } from "react-i18next";

export function AutoFixPlanner({
  session,
  issues,
  apiFetch,
  API_URL,
  onClose,
  onApplied
}: {
  session: any;
  issues: any[];
  apiFetch: any;
  API_URL: string;
  onClose: () => void;
  onApplied: () => void;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [mode, setMode] = useState<"safe" | "selected" | "smart">("safe");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [summary, setSummary] = useState<any | null>(null);

  useEffect(() => {
    loadSuggestions();
  }, []);

  async function loadSuggestions() {
    setLoading(true);
    try {
      const resp = await apiFetch(`${API_URL}/api/sessions/${session.id}/autofix/suggestions`);
      if (resp.ok) {
        const data = await resp.json();
        setSuggestions(data.items || []);

        // Auto-select safe ones by default
        const safeIds = new Set<string>();
        for (const item of (data.items || [])) {
          if (!item.applied && item.fix_type === "safe" && item.confidence >= 90) {
            safeIds.add(item.id);
          }
        }
        setSelectedIds(safeIds);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const handleToggle = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleApply = async () => {
    if (selectedIds.size === 0) return;
    setApplying(true);
    try {
      const resp = await apiFetch(`${API_URL}/api/sessions/${session.id}/autofix/apply-bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suggestion_ids: Array.from(selectedIds) })
      });
      if (resp.ok) {
        const result = await resp.json();
        setSummary(result);
        onApplied();
      } else {
        alert(t("autofix.apply_failed"));
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      alert(t("autofix.apply_error"));
    } finally {
      setApplying(false);
    }
  };

  const pendingSuggestions = suggestions.filter(s => !s.applied);

  // Filter for modes
  let visibleSuggestions = pendingSuggestions;
  if (mode === "safe") {
    visibleSuggestions = pendingSuggestions.filter(s => s.fix_type === "safe" && s.confidence >= 90);
  }

  if (summary) {
    return (
      <div className="modal-overlay">
        <div className="modal-content autofix-planner-modal" style={{ maxWidth: 600 }}>
          <div className="modal-header">
            <h3>{t("autofix.summary")}</h3>
            <button className="btn-icon" onClick={onClose}><X size={20} /></button>
          </div>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ padding: 16, background: 'var(--success-bg, rgba(46, 204, 113, 0.1))', color: 'var(--success)', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
              <CheckCircle size={24} />
              <div>
                <strong>{t("autofix.success", { count: summary.applied })}</strong>
                {summary.failed > 0 && <div>{t("autofix.failed_count", { count: summary.failed })}</div>}
              </div>
            </div>

            <div className="autofix-list">
              {Array.from(selectedIds).map(id => {
                const s = suggestions.find(x => x.id === id);
                if (!s) return null;
                return (
                  <div key={id} className="autofix-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>{s.category}</div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{s.message}</div>
                    </div>
                    <CheckCircle size={16} style={{ color: 'var(--success)' }} />
                  </div>
                );
              })}
            </div>
          </div>
          <div className="modal-footer">
            <button className="btn-primary full-width" onClick={onClose}>{t("autofix.done")}</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay">
      <div className="modal-content autofix-planner-modal" style={{ width: '90%', maxWidth: 800, maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Zap size={24} style={{ color: 'var(--warning)' }} />
            <h3>{t("autofix.title")}</h3>
          </div>
          <button className="btn-icon" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="modal-body" style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200, gap: 12 }}>
              <Loader2 size={24} className="spin" /> {t("autofix.analyzing")}
            </div>
          ) : pendingSuggestions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
              <CheckCircle size={48} style={{ margin: '0 auto 16px', color: 'var(--success)', opacity: 0.5 }} />
              <h3>{t("autofix.no_fixes")}</h3>
              <p>{t("autofix.no_fixes_desc")}</p>
            </div>
          ) : (
            <>
              {/* Modes Selection */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                <div
                  className={`card action-tile ${mode === 'safe' ? 'active' : ''}`}
                  onClick={() => {
                    setMode("safe");
                    const safeIds = pendingSuggestions.filter(s => s.fix_type === "safe" && s.confidence >= 90).map(s => s.id);
                    setSelectedIds(new Set(safeIds));
                  }}
                  style={{ borderColor: mode === 'safe' ? 'var(--primary)' : 'var(--border)', cursor: 'pointer', padding: 16 }}
                >
                  <div className="tile-icon success"><CheckCircle size={20} /></div>
                  <strong style={{ display: 'block', margin: '8px 0 4px' }}>{t("autofix.safe_fix")} ⭐⭐⭐⭐⭐</strong>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>{t("autofix.safe_fix_desc")}</p>
                </div>

                <div
                  className={`card action-tile ${mode === 'selected' ? 'active' : ''}`}
                  onClick={() => {
                    setMode("selected");
                    // Keep current selections
                  }}
                  style={{ borderColor: mode === 'selected' ? 'var(--primary)' : 'var(--border)', cursor: 'pointer', padding: 16 }}
                >
                  <div className="tile-icon info"><FilePen size={20} /></div>
                  <strong style={{ display: 'block', margin: '8px 0 4px' }}>{t("autofix.fix_selected")}</strong>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>{t("autofix.fix_selected_desc")}</p>
                </div>

                <div
                  className={`card action-tile ${mode === 'smart' ? 'active' : ''}`}
                  onClick={() => {
                    setMode("smart");
                    setSelectedIds(new Set(pendingSuggestions.map(s => s.id)));
                  }}
                  style={{ borderColor: mode === 'smart' ? 'var(--primary)' : 'var(--border)', cursor: 'pointer', padding: 16 }}
                >
                  <div className="tile-icon warning"><Zap size={20} /></div>
                  <strong style={{ display: 'block', margin: '8px 0 4px' }}>{t("autofix.smart_fix")}</strong>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>{t("autofix.smart_fix_desc")}</p>
                </div>
              </div>

              {/* Summary Banner */}
              <div style={{ background: 'var(--bg-elevated)', padding: 16, borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong>{t("autofix.available", { count: visibleSuggestions.length, mode: t(`autofix.mode_${mode}`) })}</strong>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    {t("autofix.manual_count", { count: pendingSuggestions.length - visibleSuggestions.length })}
                  </div>
                </div>
                {mode === "selected" && (
                  <button className="btn-sm outline" onClick={() => {
                    if (selectedIds.size === visibleSuggestions.length) setSelectedIds(new Set());
                    else setSelectedIds(new Set(visibleSuggestions.map(s => s.id)));
                  }}>
                    {selectedIds.size === visibleSuggestions.length ? t("autofix.deselect_all") : t("autofix.select_all")}
                  </button>
                )}
              </div>

              {/* List */}
              <div className="autofix-list">
                {visibleSuggestions.map(s => {
                  const isSafe = s.fix_type === "safe" && s.confidence >= 90;
                  return (
                    <div key={s.id} className="autofix-item" style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                      <div style={{ paddingTop: 2 }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(s.id)}
                          onChange={() => handleToggle(s.id)}
                          disabled={mode === "safe" || mode === "smart"}
                          style={{ width: 16, height: 16 }}
                        />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span className="ss-tag" style={{ textTransform: 'capitalize' }}>{s.category}</span>
                          <strong style={{ fontSize: '0.95rem' }}>{s.message}</strong>
                          {isSafe && <span className="ss-tag pack" style={{ padding: '2px 6px', fontSize: '0.7rem' }}>{t("common.safe")}</span>}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 8, fontFamily: 'monospace', background: 'var(--bg)', padding: 8, borderRadius: 4 }}>
                          <div style={{ color: 'var(--danger)', textDecoration: 'line-through' }}>{s.original_text}</div>
                          <div style={{ color: 'var(--success)' }}>{s.suggested_text}</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        <div className="modal-footer" style={{ borderTop: '1px solid var(--border)', padding: 20, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <button className="btn-secondary" onClick={onClose} disabled={applying}>{t("autofix.cancel")}</button>
          <button
            className="btn-primary"
            onClick={handleApply}
            disabled={applying || selectedIds.size === 0 || pendingSuggestions.length === 0}
            style={{ minWidth: 140 }}
          >
            {applying ? <><Loader2 size={16} className="spin" /> {t("autofix.applying")}</> : `${t("autofix.apply_fixes")} (${selectedIds.size})`}
          </button>
        </div>
      </div>
    </div>
  );
}
