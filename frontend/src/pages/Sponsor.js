import React, { useState } from "react";
import { Link } from "react-router-dom";
import Notice from "@/components/Notice";
import { createCampaign, checkoutCampaign, verifyCampaign, errText } from "@/lib/api";
import { openCheckout } from "@/lib/razorpay";

const initial = {
  company_name: "", product_name: "", product_description: "", product_url: "",
  product_image_url: "", logo_url: "", target_customer: "", brief: "",
  prohibited_claims: "", disclosure: "", sponsor_email: "", event_at: "",
  duration_minutes: 30, platform_fee_paise: 500000, prize_paise: 2500000,
};

export default function Sponsor() {
  const [form, setForm] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const campaign = await createCampaign({ ...form, event_at: new Date(form.event_at).toISOString(),
        duration_minutes: Number(form.duration_minutes), platform_fee_paise: Number(form.platform_fee_paise),
        prize_paise: Number(form.prize_paise) });
      const order = await checkoutCampaign(campaign.id);
      if (order.mode === "manual") { setDone({ ...campaign, manual: true }); return; }
      const payment = await openCheckout({ ...order, display_label: campaign.total_label,
        name: form.company_name, email: form.sponsor_email, reference: campaign.id });
      if (payment.dismissed) throw new Error("Checkout closed. Your campaign remains unpaid.");
      if (payment.failed) throw new Error(payment.failed);
      await verifyCampaign(campaign.id, payment);
      setDone(campaign);
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };

  if (done) return <><Notice /><main className="page sponsor-success" data-testid="sponsor-success">
    <p className="arena-kicker">Payment received · campaign {done.id}</p>
    <h1 className="page__title">The product is at the paste table.</h1>
    <p className="page__sub">It stays private until the keeper verifies the product, destination, claims, prize, and event schedule.</p>
    <div className="sheet"><p>{done.manual ? "Payments are in manual mode. The keeper can approve this demo campaign without a charge." : "You will receive the event link after approval."}</p>
      <div className="sheet__foot"><Link className="btn" to="/">Return to the wall</Link></div></div>
  </main></>;

  return <><Notice /><main className="page page--wide sponsor-page" data-testid="sponsor-page">
    <header className="sponsor-hero"><p className="arena-kicker">Fund the fight</p><h1 className="page__title">Give your product to the internet.</h1>
      <p className="page__sub">Creators and AI build the ads. A live audience decides which one survives. You get every approved idea, reaction, and click.</p></header>
    <form className="sheet sponsor-form" onSubmit={submit}>
      <div className="sheet__hd"><span>Sponsored event order</span><span>Reviewed before publication</span></div>
      <div className="sponsor-grid">
        <label className="field"><span className="field__label">Company</span><input required {...field("company_name")} /></label>
        <label className="field"><span className="field__label">Product</span><input required {...field("product_name")} /></label>
        <label className="field sponsor-span"><span className="field__label">What is it?</span><textarea required {...field("product_description")} /></label>
        <label className="field"><span className="field__label">Product HTTPS link</span><input type="url" required {...field("product_url")} /></label>
        <label className="field"><span className="field__label">Product image HTTPS link</span><input type="url" required {...field("product_image_url")} /></label>
        <label className="field"><span className="field__label">Logo HTTPS link</span><input type="url" {...field("logo_url")} /></label>
        <label className="field"><span className="field__label">Sponsor email</span><input type="email" required {...field("sponsor_email")} /></label>
        <label className="field sponsor-span"><span className="field__label">Who should want it?</span><textarea required {...field("target_customer")} /></label>
        <label className="field sponsor-span"><span className="field__label">The brief</span><textarea required {...field("brief")} /></label>
        <label className="field"><span className="field__label">Claims creators must not make</span><textarea {...field("prohibited_claims")} /></label>
        <label className="field"><span className="field__label">Required disclosure</span><textarea {...field("disclosure")} /></label>
        <label className="field"><span className="field__label">Event date and time</span><input type="datetime-local" required {...field("event_at")} /></label>
        <label className="field"><span className="field__label">Event length in minutes</span><input type="number" min="12" max="180" {...field("duration_minutes")} /></label>
      </div>
      <div className="sponsor-money"><div><span>Platform fee</span><strong>₹{(form.platform_fee_paise / 100).toLocaleString()}</strong></div>
        <label><span>Creator prize</span><input type="number" min="100" step="100" value={form.prize_paise / 100} onChange={(e) => setForm({ ...form, prize_paise: Math.round(Number(e.target.value) * 100) })} /><small>The final King takes it.</small></label>
        <div className="sponsor-total"><span>Total</span><strong>₹{((Number(form.platform_fee_paise) + Number(form.prize_paise)) / 100).toLocaleString()}</strong></div></div>
      {error ? <p className="sheet__error">{error}</p> : null}
      <div className="sheet__foot"><button className="btn" disabled={busy}>{busy ? "Opening the till…" : "Fund this fight"}</button><span>No campaign goes live without review.</span></div>
    </form>
  </main></>;
}
