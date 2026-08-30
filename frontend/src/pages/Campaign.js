import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Notice from "@/components/Notice";
import ArenaPoster from "@/components/ArenaPoster";
import { getCampaign, generateCampaignAds, submitCampaignAd, errText } from "@/lib/api";

export default function Campaign() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ creator_name: "", creator_email: "", angle: "", model_id: "" });
  const [generation, setGeneration] = useState(null);
  const [chosen, setChosen] = useState(0);
  const [headline, setHeadline] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);

  useEffect(() => { getCampaign(slug).then((d) => { setData(d); setForm((f) => ({ ...f, model_id: d.models?.[0]?.id || "" })); }).catch((e) => setError(errText(e))); }, [slug]);
  const campaign = data?.campaign;
  const generate = async (e) => { e.preventDefault(); setBusy(true); setError("");
    try { const result = await generateCampaignAds(campaign.id, form); setGeneration(result); setChosen(0); setHeadline(result.concepts[0].headline); }
    catch (e2) { setError(errText(e2)); } finally { setBusy(false); } };
  const submit = async () => { setBusy(true); setError(""); try {
    const result = await submitCampaignAd(campaign.id, { generation_id: generation.generation_id, concept_index: chosen, headline }); setDone(result);
  } catch (e) { setError(errText(e)); } finally { setBusy(false); } };

  if (!data && !error) return <><Notice /><div className="loading">Loading the brief…</div></>;
  if (done) return <><Notice /><main className="page"><p className="arena-kicker">Submission {done.id}</p><h1 className="page__title">Your ad is at the paste table.</h1>
    <p className="page__sub">The keeper will review the claims and decide whether it enters the live challenger queue.</p>
    <Link className="btn" to={data.event_slug ? `/event/${data.event_slug}` : "/"}>See the arena</Link></main></>;
  if (error && !data) return <><Notice /><div className="page"><p className="sheet__error">{error}</p></div></>;

  return <><Notice /><main className="campaign-page" data-testid="campaign-page">
    <section className="campaign-brief"><div><p className="arena-kicker">Sponsored challenge · ₹{(campaign.prize_paise / 100).toLocaleString()} prize</p>
      <h1>Sell us<br />{campaign.product_name}.</h1><p>{campaign.brief}</p>
      <dl><div><dt>For</dt><dd>{campaign.target_customer}</dd></div><div><dt>Event</dt><dd>{new Date(campaign.event_at).toLocaleString()}</dd></div></dl></div>
      <img src={campaign.product_image_url} alt={campaign.product_name} /></section>
    {!generation ? <form className="sheet campaign-entry" onSubmit={generate}><div className="sheet__hd"><span>Your angle</span><span>AI makes three posters</span></div>
      <label className="field"><span className="field__label">Creator name</span><input required value={form.creator_name} onChange={(e) => setForm({ ...form, creator_name: e.target.value })} /></label>
      <label className="field"><span className="field__label">Private email</span><input required type="email" value={form.creator_email} onChange={(e) => setForm({ ...form, creator_email: e.target.value })} /></label>
      <label className="field"><span className="field__label">How would you sell it?</span><textarea required value={form.angle} onChange={(e) => setForm({ ...form, angle: e.target.value })} placeholder="One sharp thought. Not finished copy." /></label>
      <label className="field"><span className="field__label">Creative model</span><select value={form.model_id} onChange={(e) => setForm({ ...form, model_id: e.target.value })}>{data.models.map((m) => <option value={m.id} key={m.id}>{m.label}</option>)}</select></label>
      {error ? <p className="sheet__error">{error}</p> : null}<div className="sheet__foot"><button className="btn" disabled={busy}>{busy ? "The models are arguing…" : "Draw a constraint and make three ads"}</button></div>
    </form> : <section className="concept-room"><header><p className="arena-kicker">Your constraint</p><h2>{generation.constraint}</h2><p>Choose one direction. You may change the headline; everything else stays as the model committed it.</p></header>
      <div className="concept-grid">{generation.concepts.map((concept, i) => <button type="button" className={chosen === i ? "concept-choice concept-choice--active" : "concept-choice"} onClick={() => { setChosen(i); setHeadline(concept.headline); }} key={i}>
        <ArenaPoster ad={{ creative: concept, creator_name: form.creator_name, constraint: generation.constraint }} campaign={campaign} side={`concept ${i + 1}`} /><span>{chosen === i ? "Selected" : "Choose this"}</span></button>)}</div>
      <div className="concept-submit"><label className="field"><span className="field__label">Final headline</span><input maxLength="100" value={headline} onChange={(e) => setHeadline(e.target.value)} /></label>
        {error ? <p className="sheet__error">{error}</p> : null}<button className="btn" onClick={submit} disabled={busy}>{busy ? "Sending to review…" : "Submit this challenger"}</button></div>
    </section>}
  </main></>;
}
