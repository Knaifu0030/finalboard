import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Notice from "@/components/Notice";
import { getWall, createOrder, verifyPayment, paymentFailed, errText } from "@/lib/api";
import { openCheckout } from "@/lib/razorpay";

const MAX_TEXT = 120;
const MAX_NAME = 24;

export default function Take() {
  const [wall, setWall] = useState(null);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getWall()
      .then((d) => {
        setWall(d);
        setAmount(String(d.price.next_paise / d.price.unit_paise));
      })
      .catch((e) => setError(errText(e)));
  }, []);

  const sym = wall?.currency === "INR" ? "\u20b9" : "$";
  const unit = wall?.price?.unit_paise || 8800;
  const minUnits = wall ? wall.price.next_paise / unit : 0;
  const amountPaise = useMemo(() => {
    const n = parseFloat(amount);
    if (!Number.isFinite(n)) return 0;
    return Math.round(n * unit);
  }, [amount, unit]);

  const tooLow = !!wall && amountPaise < wall.price.next_paise;

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!text.trim()) {
      setError("Say something. It won't last.");
      return;
    }
    if (!name.trim()) {
      setError("Sign it. Printers always sign.");
      return;
    }
    if (tooLow) {
      setError("Someone already paid more than that.");
      return;
    }
    setBusy(true);
    try {
      sessionStorage.setItem(
        "lb_expect",
        JSON.stringify({ prev: wall?.current?.id || null })
      );
      const order = await createOrder({
        text: text.trim(),
        name: name.trim(),
        email: email.trim(),
        image_url: imageUrl.trim(),
        amount_paise: amountPaise,
      });

      if (order.mode === "pending") {
        setPending(order);
        setBusy(false);
        return;
      }

      const res = await openCheckout(order);
      if (res.dismissed) {
        setError("You closed the till. The wall is unchanged.");
        setBusy(false);
        return;
      }
      if (res.failed) {
        await paymentFailed({ order_id: order.order_id, reason: res.failed });
        setError(res.failed);
        setBusy(false);
        return;
      }
      const done = await verifyPayment(res);
      navigate(`/m/${done.message_id}?fresh=1`);
    } catch (err) {
      setError(errText(err));
      setBusy(false);
    }
  };

  if (pending) {
    return (
      <>
        <Notice />
        <div className="page" data-testid="take-pending">
          <h1 className="page__title">Pending</h1>
          <p className="page__sub">{pending.copy}</p>
          <div className="sheet">
            <div className="field">
              <p style={{ margin: 0 }}>
                Your poster is stencilled on the rail and waits for the wall's keeper to approve it.
                Nothing has been charged.
              </p>
            </div>
            <div className="sheet__foot">
              <Link to="/" className="btn" data-testid="pending-back">
                Back to the wall
              </Link>
              <span className="admin__note">Reference {pending.reference}</span>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Notice takeovers={wall?.takeovers} totalLabel={wall?.total_paid_label} />
      <div className="page" data-testid="take-page">
        <h1 className="page__title">Paste over it</h1>
        <p className="page__sub">
          {wall?.frozen
            ? "The wall is closed. Nothing more goes up."
            : `Currently held by ${wall?.current?.name || "nobody"} at ${
                wall?.price?.current_label || wall?.price?.start_label || ""
              }. Minimum ${wall?.price?.next_label || ""}.`}
        </p>

        <form className="sheet" onSubmit={submit} data-testid="take-form">
          <div className="sheet__hd">
            <span>Order form &middot; one poster</span>
            <span>No accounts. No refunds unless you ask.</span>
          </div>

          <div className="field">
            <div className="field__label">
              <span>The message</span>
              <span className="counter">
                {text.length}/{MAX_TEXT}
              </span>
            </div>
            <textarea
              value={text}
              maxLength={MAX_TEXT}
              onChange={(e) => setText(e.target.value)}
              placeholder="Say something. It won't last."
              data-testid="input-message"
            />
          </div>

          <div className="field">
            <div className="field__label">
              <span>Printer's credit</span>
              <span className="counter">
                {name.length}/{MAX_NAME}
              </span>
            </div>
            <input
              value={name}
              maxLength={MAX_NAME}
              onChange={(e) => setName(e.target.value)}
              placeholder="the name in the bottom margin"
              data-testid="input-name"
            />
          </div>

          <div className="field">
            <div className="field__label">
              <span>Email</span>
              <span className="field__hint">only used to tell you when you lose it</span>
            </div>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@somewhere"
              data-testid="input-email"
            />
          </div>

          <div className="field">
            <div className="field__label">
              <span>Image url</span>
              <span className="field__hint">optional &middot; pasted 96px square, top right</span>
            </div>
            <input
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              placeholder="https://"
              data-testid="input-image"
            />
          </div>

          <div className="field field--amount">
            <div className="grow">
              <div className="field__label">
                <span>Amount</span>
                <span className="field__hint">
                  minimum {sym}
                  {minUnits ? minUnits.toFixed(2) : "--"} &middot; pay more if you want it to hold
                </span>
              </div>
              <input
                type="number"
                step="0.5"
                min={minUnits || 0}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                data-testid="input-amount"
              />
            </div>
            <div className="admin__note">
              charged in INR by Razorpay
              {wall?.currency === "USD" ? " at the day's rate" : ""}
            </div>
          </div>

          {error ? (
            <p className="sheet__error" data-testid="take-error">
              {error}
            </p>
          ) : null}

          <div className="sheet__foot">
            <button
              type="submit"
              className="btn"
              disabled={busy || wall?.frozen || !wall}
              data-testid="take-submit"
            >
              {busy
                ? "Working\u2026"
                : `Paste it over for ${sym}${
                    Number.isFinite(parseFloat(amount)) ? parseFloat(amount).toFixed(2) : ""
                  }`}
            </button>
            <Link to="/" data-testid="take-cancel">
              Leave the wall alone
            </Link>
          </div>
        </form>
      </div>
    </>
  );
}
