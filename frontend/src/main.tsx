import { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Issue = { id: string; severity: string; category: string; message: string; recommendation: string; confidence: number; evidence: { excerpt: string; location: string }; autofix_allowed: boolean };
type Result = { score: number; summary: string; category_scores: Record<string, number>; issues: Issue[]; report_markdown: string };
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const sample = "# Introduction\n\nThis is a deliberately very long sentence designed to show how the rule engine identifies prose that needs editorial attention because it contains too many words without a clear break while citing an unnamed source [1].";

function App() {
  const [text, setText] = useState(sample);
  const [profile, setProfile] = useState("academic");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  async function submit() {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/reviews`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, profile_id: profile }) });
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json());
    } catch (error) { alert(`Review failed: ${error instanceof Error ? error.message : "Unknown error"}`); }
    finally { setLoading(false); }
  }
  return <main>
    <header><p className="eyebrow">DOCUMENT REVIEW ENGINE</p><h1>ReviewMind</h1><p>Choose a profile, review the document, then inspect evidence-backed issues.</p></header>
    <section className="workspace"><div className="panel"><h2>Review setup</h2><label>Profile<select value={profile} onChange={e => setProfile(e.target.value)}><option value="academic">Academic</option><option value="business">Business Proposal</option><option value="sop">SOP & Compliance</option></select></label><div className="permission"><strong>Permission matrix</strong><p>Academic allows writing suggestions; SOP blocks rewriting by design.</p></div><label>Document text<textarea value={text} onChange={e => setText(e.target.value)} rows={15} /></label><button onClick={submit} disabled={loading}>{loading ? "Reviewing…" : "Start review"}</button></div>
      <div className="panel results"><h2>Review report</h2>{!result ? <p className="muted">Your score, category quality and evidence-backed issues will appear here.</p> : <><div className="score"><strong>{result.score}</strong><span>/100 overall quality</span></div><p>{result.summary}</p><div className="scores">{Object.entries(result.category_scores).map(([category, score]) => <div key={category}><span>{category}</span><b>{score}</b></div>)}</div><h3>Issues</h3>{result.issues.map(issue => <article className={`issue ${issue.severity}`} key={issue.id}><small>{issue.severity} · {issue.category} · {issue.confidence}% confidence</small><h4>{issue.message}</h4><blockquote>{issue.evidence.excerpt}</blockquote><p>{issue.recommendation}</p>{issue.autofix_allowed && <em>Auto-fix eligible</em>}</article>)}</>}</div></section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
