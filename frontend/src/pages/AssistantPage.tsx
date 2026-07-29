import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, FileText, History, FolderOpen, Bot, Settings, Sun, Moon, Menu,
  Search, Download, Upload, Plus, X, Save, RefreshCw, FilePen, Wrench, Eye, Zap,
  CheckCircle, CircleX, AlertTriangle, Lightbulb, BarChart3, Target, Star, ThumbsUp,
  BookOpen, Bell, User, ChevronRight, Home, Database, Users, Sparkles, Shield,
  Briefcase, LogIn, LogOut, Trash2, AlertCircle, Clock, Activity, Sliders, Layers3,
  ShieldCheck, Check, ArrowRight, ArrowLeft, Mail, Lock, Loader2, Play, FastForward
} from "lucide-react";import { API_URL } from "../lib/config";
import type { ApiFetch, HistoryItem, SessionDetail } from "../domain/types";

export function AIAssistantView({ session, reviews, apiFetch, onSelectSession }: { session: SessionDetail | null; reviews: HistoryItem[]; apiFetch: ApiFetch; onSelectSession: (id: string) => void; }) {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [targetSessionId, setTargetSessionId] = useState(session?.id || "");
  useEffect(() => { if (session?.id) setTargetSessionId(session.id); }, [session?.id]);
  const target = reviews.find(item => item.id === targetSessionId);

  async function sendMessage() {
    const userMessage = input.trim();
    if (!userMessage) return;
    setInput("");
    setMessages(current => [...current, { role: "user", text: userMessage }]);
    setAiLoading(true);
    try {
      const response = await apiFetch(`${API_URL}/api/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, session_id: targetSessionId || null }),
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setMessages(current => [...current, { role: "assistant", text: data.response || t("assistant.processed") }]);
    } catch {
      setMessages(current => [...current, { role: "assistant", text: t("assistant.error") }]);
    } finally {
      setAiLoading(false);
    }
  }

  return <section className="assistant-page page-stack">
    <div className="page-header"><div><div className="page-eyebrow">{t("nav.workspace")}</div><h2>{t("assistant.title")}</h2><p className="page-subtitle">{t("assistant.subtitle")}</p></div><span className="ai-status">{aiLoading ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}{aiLoading ? t("assistant.thinking") : t("assistant.connected")}</span></div>
    <div className="assistant-context card">
      <div><label>{t("assistant.context_label")}</label><span>{t("assistant.context_desc")}</span></div>
      <select value={targetSessionId} onChange={event => { setTargetSessionId(event.target.value); setMessages([]); }}>
        <option value="">{t("assistant.general_context")}</option>
        {reviews.map(item => <option value={item.id} key={item.id}>{item.filename} · {item.score}/100</option>)}
      </select>
      {target && <button className="btn-sm outline" onClick={() => onSelectSession(target.id)}><Eye size={13} /> {t("assistant.open_review")}</button>}
    </div>
    <div className="ai-panel"><div className="ai-messages">{messages.length === 0 && <div className="empty-state small"><Sparkles size={28} /><p>{target ? t("assistant.empty_session", { filename: target.filename, score: target.score }) : t("assistant.empty")}</p></div>}{messages.map((message, index) => <div key={index} className={`ai-message ${message.role}`}>{message.text}</div>)}{aiLoading && <div className="ai-message assistant thinking"><Loader2 size={16} className="spin" /></div>}</div><div className="ai-input-bar"><input value={input} onChange={event => setInput(event.target.value)} placeholder={t("assistant.placeholder")} onKeyDown={event => event.key === "Enter" && !aiLoading && sendMessage()} disabled={aiLoading} maxLength={4000} /><button onClick={sendMessage} disabled={aiLoading || !input.trim()}><Zap size={14} /> {t("assistant.send")}</button></div></div>
  </section>;
}

