import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Notice from "@/components/Notice";
import { adminLogin, adminState, adminPost, errText } from "@/lib/api";

const KEY = "lb_admin_pw";

export default function Admin() {
  const [pw, setPw] = useState(() => localStorage.getItem(KEY) || "");
  const [authed, setAuthed] = useState(false);
  const [state, setState] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [recap, setRecap] = useState("");
  const [hours, setHours] = useState("48");
  const [seed, setSeed] = useState({ text: "", name: "", email: "", amount: "" });

  const refresh = useCallback(
    async (password) => {
      try {
        const d = await adminState(password || pw);
        setState(d);
        setAuthed(true);
        setErr(null);
      } catch (e) {
        setErr(errText(e));
        if (e?.response?.status === 401) setAuthed(false);
      }
    },
    [pw]
  );

  useEffect(() => {
    if (pw) refresh(pw);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!authed) return;
    const iv = setInterval(() => refresh(), 10000);
    return () => clearInterval(iv);
  }, [authed, refresh]);

  const login = async (e) => {
    e.preventDefault();
    setErr(null);
    try {
      await adminLogin(pw);
      localStorage.setItem(KEY, pw);
      await refresh(pw);
    } catch (e2) {
      setErr(errText(e2));
    }
  };

  const act = async (path, body, note) => {
    setMsg(null);
    setErr(null);
    try {
      const r = await adminPost(pw, path, body);
      setMsg(note || "Done.");
      await refresh();
      return r;
    } catch (e) {
      setErr(errText(e));
      return null;
    }
  };

  if (!authed) {
    return (
      <>
        <Notice />
        <div className="page" data-testid="admin-login">
          <h1 className="page__title">Keeper</h1>
          <p className="page__sub">The wall does not know you yet.</p>
          <form className="sheet" onSubmit={login}>
            <div className="field">
              <div className="field__label">
                <span>Password</span>
              </div>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                data-testid="admin-password"
              />
            </div>
            {err ? (
              <p className="sheet__error" data-testid="admin-error">
                {err}
              </p>
            ) : null}
            <div className="sheet__foot">
              <button type="submit" className="btn" data-testid="admin-login-submit">
                Unlock
              </button>
              <Link to="/">Back to the wall</Link>
            </div>
          </form>
        </div>
      </>
    );
  }

  const s = state?.state;
  const clock = s?.clock;

  return (
    <>
      <Notice />
      <div className="page page--wide admin" data-testid="admin-console">
        <h1 className="page__title">Keeper</h1>
        <p><Link to="/admin/games">Open the sponsored games desk →</Link></p>
        <p className="page__sub">
          {`${s?.takeovers} takeovers \u00b7 ${s?.total_paid_label} pasted \u00b7 clock ${
            clock?.paused ? "not started" : s?.frozen ? "frozen" : "running"
          } \u00b7 razorpay ${s?.razorpay_ready ? "live" : "off"} \u00b7 resend ${
            state?.resend_ready ? "live" : "queued only"
          }`}
        </p>

        {msg ? (
          <p className="admin__pre" data-testid="admin-message">
            {msg}
          </p>
        ) : null}
        {err ? (
          <p className="sheet__error" data-testid="admin-error">
            {err}
          </p>
        ) : null}

        <h2>The clock</h2>
        <div className="admin__row">
          <span data-testid="admin-clock-state">
            ends_at: {clock?.ends_at || "not set"} &middot; paused: {String(clock?.paused)}
          </span>
        </div>
        <div className="admin__row">
          <button
            className="btn btn--sm"
            onClick={() => act("/admin/pause", { paused: !clock?.paused }, clock?.paused ? "Clock running." : "Paused.")}
            data-testid="admin-toggle-pause"
          >
            {clock?.paused ? "Start the 48 hours" : "Pause"}
          </button>
          <input
            style={{ width: 90, border: "1px solid var(--ink-black)", padding: 6, background: "transparent" }}
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            data-testid="admin-hours"
          />
          <button
            className="btn btn--sm"
            onClick={() => act("/admin/clock", { hours: parseFloat(hours) }, "Countdown reset.")}
            data-testid="admin-set-clock"
          >
            Set countdown (hours from now)
          </button>
          <button
            className="btn btn--sm btn--ghost"
            onClick={() => {
              if (window.confirm(`Reset the next takeover to ${s?.price?.start_label}? Existing posters and their paid amounts will stay unchanged.`)) {
                act("/admin/reset-price", {}, `Next takeover reset to ${s?.price?.start_label}. Poster history was kept.`);
              }
            }}
            data-testid="admin-reset-price"
          >
            Reset next price to {s?.price?.start_label}
          </button>
        </div>
        <p className="admin__note">
          This changes only the next takeover price. After someone takes the wall, the normal price ladder resumes.
        </p>

        <h2>Pending</h2>
        {!state?.pending?.length ? (
          <p className="admin__note" data-testid="admin-no-pending">
            Nothing waiting.
          </p>
        ) : (
          <table data-testid="admin-pending-table">
            <thead>
              <tr>
                <th>Ref</th>
                <th>Message</th>
                <th>Name</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Do</th>
              </tr>
            </thead>
            <tbody>
              {state.pending.map((p) => (
                <tr key={p.id} data-testid={`admin-pending-${p.id}`}>
                  <td>{p.id}</td>
                  <td>{p.text}</td>
                  <td>{p.name}</td>
                  <td>{(p.amount_paise / 8800).toFixed(2)} usd</td>
                  <td>
                    <span className="tag">{p.status}</span>
                  </td>
                  <td>
                    {["created", "paid", "awaiting_approval"].includes(p.status) ? (
                      <>
                        <button
                          className="btn btn--sm btn--ghost"
                          onClick={() => act(`/admin/pending/${p.id}/approve`, {}, "Approved and pasted.")}
                          data-testid={`admin-approve-${p.id}`}
                        >
                          Approve
                        </button>{" "}
                        <button
                          className="btn btn--sm btn--ghost"
                          onClick={() => act(`/admin/pending/${p.id}/reject`, {}, "Rejected.")}
                          data-testid={`admin-reject-${p.id}`}
                        >
                          Reject
                        </button>
                      </>
                    ) : (
                      "\u2014"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <h2>The wall</h2>
        <div className="admin__row">
          <button
            className="btn btn--sm"
            onClick={() => act("/admin/revert", {}, "Reverted. The previous holder is back up.")}
            data-testid="admin-revert"
          >
            Revert the last takeover
          </button>
        </div>
        <table data-testid="admin-messages-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Message</th>
              <th>Name / email</th>
              <th>Paid</th>
              <th>Reign</th>
              <th>State</th>
              <th>Do</th>
            </tr>
          </thead>
          <tbody>
            {(state?.messages || []).map((m) => (
              <tr key={m.id}>
                <td>{m.seq}</td>
                <td>
                  {m.text}
                  {m.heckle ? (
                    <>
                      <br />
                      <em>{m.heckle}</em>
                    </>
                  ) : null}
                </td>
                <td>
                  {m.name}
                  <br />
                  <span className="admin__note">{m.email}</span>
                </td>
                <td>{m.price_label}</td>
                <td>{m.reign_label}</td>
                <td>
                  {m.is_current ? (
                    <span className="tag tag--live">on the wall</span>
                  ) : m.reverted ? (
                    <span className="tag tag--dead">removed</span>
                  ) : (
                    <span className="tag">dethroned</span>
                  )}
                </td>
                <td>
                  <Link to={`/m/${m.id}`}>view</Link>
                  <br />
                  <button
                    className="btn btn--sm btn--ghost"
                    onClick={() => act(`/admin/message/${m.id}/delete`, {}, "Removed from the wall.")}
                    data-testid={`admin-delete-${m.seq}`}
                  >
                    Delete
                  </button>
                  {m.payment?.payment_id ? (
                    <button
                      className="btn btn--sm btn--ghost"
                      onClick={() => act(`/admin/refund/${m.payment.payment_id}`, {}, "Refund sent.")}
                      data-testid={`admin-refund-${m.seq}`}
                    >
                      Refund
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2>Paste one on by hand</h2>
        <div className="admin__row">
          <input
            placeholder="message"
            value={seed.text}
            onChange={(e) => setSeed({ ...seed, text: e.target.value })}
            style={{ flex: "1 1 240px", border: "1px solid var(--ink-black)", padding: 6, background: "transparent" }}
            data-testid="admin-seed-text"
          />
          <input
            placeholder="name"
            value={seed.name}
            onChange={(e) => setSeed({ ...seed, name: e.target.value })}
            style={{ width: 130, border: "1px solid var(--ink-black)", padding: 6, background: "transparent" }}
            data-testid="admin-seed-name"
          />
          <input
            placeholder="email"
            value={seed.email}
            onChange={(e) => setSeed({ ...seed, email: e.target.value })}
            style={{ width: 180, border: "1px solid var(--ink-black)", padding: 6, background: "transparent" }}
            data-testid="admin-seed-email"
          />
          <button
            className="btn btn--sm"
            onClick={() =>
              act(
                "/admin/takeover",
                {
                  text: seed.text,
                  name: seed.name || "the keeper",
                  email: seed.email || "keeper@thelastbillboard.test",
                },
                "Pasted."
              ).then(() => setSeed({ text: "", name: "", email: "", amount: "" }))
            }
            data-testid="admin-seed-submit"
          >
            Paste it
          </button>
        </div>
        <p className="admin__note">
          Goes up at the current minimum, no charge. Used for seeding and for putting a reverted
          poster back.
        </p>

        <h2>Last hour on the wall</h2>
        <div className="admin__row">
          <button
            className="btn btn--sm"
            onClick={async () => {
              const r = await act("/admin/recap", {}, "Recap written.");
              if (r) setRecap(r.recap);
            }}
            data-testid="admin-recap"
          >
            Write the recap
          </button>
          {recap ? (
            <button
              className="btn btn--sm btn--ghost"
              onClick={() => navigator.clipboard?.writeText(recap)}
              data-testid="admin-recap-copy"
            >
              Copy
            </button>
          ) : null}
        </div>
        {recap ? (
          <pre className="admin__pre" data-testid="admin-recap-text">
            {recap}
          </pre>
        ) : null}

        <h2>Outbox</h2>
        <div className="admin__row">
          <button
            className="btn btn--sm"
            onClick={() => act("/admin/drain-outbox", {}, "Tried to send.")}
            data-testid="admin-drain"
          >
            Send queued mail
          </button>
          <span className="admin__note">
            {state?.resend_ready
              ? "Resend is wired. Mail goes out on dethronement."
              : "No Resend key yet, so every dethrone email is written and stored here instead of sent."}
          </span>
        </div>
        <table data-testid="admin-outbox-table">
          <thead>
            <tr>
              <th>To</th>
              <th>Subject</th>
              <th>Body</th>
              <th>Sent</th>
            </tr>
          </thead>
          <tbody>
            {(state?.outbox || []).map((o) => (
              <tr key={o.id}>
                <td>{o.to}</td>
                <td>{o.subject}</td>
                <td>
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 11 }}>{o.body}</pre>
                </td>
                <td>{o.sent ? "yes" : o.error ? `no: ${o.error}` : "queued"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <hr className="rule" />
        <Link to="/" className="btn">
          Back to the wall
        </Link>
      </div>
    </>
  );
}
