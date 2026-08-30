import React, { useEffect, useState } from "react";
import { getAudience, releaseAudience, errText } from "@/lib/api";

const labels = { attention: "Attention", clarity: "Clarity", desire: "Desire", trust: "Trust",
  originality: "Originality", brand_fit: "Brand fit" };

export default function AIAudience({ roundId }) {
  const [run, setRun] = useState(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setRun(null); setOpen(false); setError(""); }, [roundId]);
  useEffect(() => {
    if (!run || run.status === "complete") return;
    const id = setInterval(() => getAudience(roundId).then(setRun).catch(() => {}), 1500);
    return () => clearInterval(id);
  }, [run, roundId]);
  const release = async () => { setOpen(true); setError(""); try { setRun(await releaseAudience(roundId)); } catch (e) { setError(errText(e)); } };
  if (!open) return <button className="audience-release" onClick={release} data-testid="release-ai-audience">
    <span>Release</span><strong>100</strong><span>synthetic customers</span>
  </button>;
  const people = run?.people || [];
  return <aside className="ai-audience" data-testid="ai-audience-panel">
    <header><div><p className="arena-kicker">Simulated panel · not market research</p><h2>100 customers enter the wall.</h2></div><button onClick={() => setOpen(false)} aria-label="Close AI panel">×</button></header>
    {error ? <p className="sheet__error">{error}</p> : null}
    <div className="audience-progress"><span style={{ width: `${run?.completed || 0}%` }} /><b>{run?.completed || 0}/100 interviewed</b></div>
    <div className="audience-feed">{people.slice(-18).reverse().map((p, i) => <article key={p.id || i} style={{ "--delay": `${Math.min(i, 8) * 30}ms` }}>
      <div><strong>{p.archetype}</strong><span>backs {p.favored}</span></div><p>{p.reaction}</p><small>{p.model?.label}</small></article>)}</div>
    {run?.summary ? <div className="audience-report"><div className="audience-ratings">{Object.entries(run.summary.ratings || {}).map(([key, value]) => <div key={key}><span>{labels[key] || key}</span><b>{value}</b><i><em style={{ width: `${value}%` }} /></i></div>)}</div>
      <div className="audience-verdict"><p><strong>{run.summary.favored?.king}</strong> keep the king</p><p><strong>{run.summary.favored?.challenger}</strong> paste the challenger</p>
        <blockquote>{run.summary.suggested_improvement}</blockquote><small>{run.summary.research_note}</small></div></div> : null}
  </aside>;
}
