import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import Notice from "@/components/Notice";
import ArenaPoster from "@/components/ArenaPoster";
import AIAudience from "@/components/AIAudience";
import { eventStreamUrl, getEvent, trackedProductUrl, voteRound, errText } from "@/lib/api";

const phaseCopy = { waiting: "The paste crew is waiting", reveal: "Meet the challenger", voting: "The wall is taking sides",
  panel: "The vote is locked", result: "One ad survives", complete: "Round complete" };
const clock = (seconds) => `${String(Math.floor((seconds || 0) / 60)).padStart(2, "0")}:${String((seconds || 0) % 60).padStart(2, "0")}`;

export default function Event() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [voted, setVoted] = useState("");
  const [tick, setTick] = useState(0);
  const reduce = useReducedMotion();
  const load = useCallback(() => getEvent(slug).then(setData).catch((e) => setError(errText(e))), [slug]);
  useEffect(() => { load(); const es = new EventSource(eventStreamUrl(slug), { withCredentials: true }); es.addEventListener("state", (e) => { try { setData(JSON.parse(e.data)); } catch (_) {} });
    es.onerror = () => {}; const fallback = setInterval(load, 8000); return () => { es.close(); clearInterval(fallback); }; }, [load, slug]);
  useEffect(() => { const id = setInterval(() => setTick((x) => x + 1), 1000); return () => clearInterval(id); }, []);
  useEffect(() => { setVoted(""); }, [data?.round?.id]);
  const remaining = useMemo(() => Math.max(0, Number(data?.round?.remaining_seconds || 0) - (tick % 2)), [data?.round?.remaining_seconds, tick]);
  const vote = async (side) => { setError(""); try { await voteRound(data.round.id, side); setVoted(side); } catch (e) { setError(errText(e)); } };
  if (!data) return <><Notice /><div className="loading">{error || "Opening the arena…"}</div></>;
  const { event, campaign, round, ads } = data;
  if (!round) return <><Notice /><main className="event-wait"><img src={campaign.product_image_url} alt={campaign.product_name} /><div><p className="arena-kicker">{campaign.company_name} presents</p>
    <h1>{campaign.product_name}<br />enters the wall.</h1><p>{event.status === "completed" ? "The fight is over." : `The live fight begins ${new Date(event.scheduled_at).toLocaleString()}.`}</p>
    <Link className="btn" to={`/campaign/${campaign.slug}`}>Enter a challenger</Link></div></main></>;
  const king = ads[round.king_id], challenger = ads[round.challenger_id];
  const revealScores = ["result", "complete"].includes(round.phase);
  return <><Notice /><main className={`arena arena--${round.phase}`} data-testid="live-event">
    <header className="arena-scoreboard"><div><span>{campaign.company_name} presents</span><strong>{campaign.product_name}</strong></div>
      <div className="arena-round"><span>Round {round.number}</span><strong>{phaseCopy[round.phase]}</strong></div><time>{clock(remaining)}</time></header>
    <section className="arena-fight">
      <div className="arena-corner arena-corner--king"><div className="corner-label"><b>Current king</b><span>{king?.creator_name}</span></div>
        <ArenaPoster ad={king} campaign={campaign} side="king" winner={event.status === "completed" && event.king_id === king?.id} />
        <a className="product-hit" href={trackedProductUrl(round.id, king?.id)} target="_blank" rel="noreferrer">See the product through this ad <span>clicks count 30%</span></a></div>
      <div className="arena-versus" aria-hidden="true">VS</div>
      <AnimatePresence mode="wait"><motion.div key={challenger?.id} className="arena-corner arena-corner--challenger"
        initial={reduce ? false : { y: -600, rotate: -3 }} animate={{ y: 0, rotate: 0 }} exit={reduce ? {} : { x: 700, rotate: 7 }} transition={{ duration: 0.65, ease: [0.23, 1, 0.32, 1] }}>
        <div className="corner-label"><b>Challenger</b><span>{challenger?.creator_name}</span></div><ArenaPoster ad={challenger} campaign={campaign} side="challenger" entering />
        <a className="product-hit" href={trackedProductUrl(round.id, challenger?.id)} target="_blank" rel="noreferrer">See the product through this ad <span>clicks count 30%</span></a></motion.div></AnimatePresence>
    </section>
    {round.phase === "voting" ? <section className="arena-vote"><button disabled={!!voted} onClick={() => vote("king")}>Keep the king</button><p>{voted ? `Your ticket backs the ${voted}.` : "One browser. One vote. Actual product clicks matter too."}</p>
      <button disabled={!!voted} onClick={() => vote("challenger")}>Paste the challenger</button></section> : null}
    {error ? <p className="arena-error">{error}</p> : null}
    {revealScores && round.scores ? <section className="arena-result"><div><span>King</span><strong>{round.scores.king}%</strong><small>{round.counts?.votes?.king || 0} votes · {round.counts?.clicks?.king || 0} clicks</small></div>
      <h2>{round.winner_id === round.challenger_id ? "THE CHALLENGER TAKES THE WALL" : "THE KING HOLDS"}</h2><div><span>Challenger</span><strong>{round.scores.challenger}%</strong><small>{round.counts?.votes?.challenger || 0} votes · {round.counts?.clicks?.challenger || 0} clicks</small></div></section> : null}
    <AIAudience roundId={round.id} />
    <footer className="arena-disclosure">AI audience reactions are synthetic creative hypotheses. Human vote: 70%. Unique product clicks: 30%.</footer>
  </main></>;
}
