import React, { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import Notice from "@/components/Notice";
import Poster from "@/components/Poster";
import { getMessage, errText, ogUrl } from "@/lib/api";

const INK = { tomato: "var(--ink-tomato)", mustard: "var(--ink-mustard)", teal: "var(--ink-teal)" };

export default function Permalink() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setData(null);
    setErr(null);
    getMessage(id)
      .then(setData)
      .catch((e) => setErr(errText(e)));
  }, [id]);

  useEffect(() => {
    if (!data) return;
    const m = data.message;
    document.title = `"${m.text}" \u2014 The Last Billboard`;
    const set = (sel, attr, val) => {
      let el = document.head.querySelector(sel);
      if (!el) {
        el = document.createElement("meta");
        const [k, v] = sel.replace(/[[\]']/g, "").split("=");
        el.setAttribute(k.replace("meta", "").trim() || "property", v);
        document.head.appendChild(el);
      }
      el.setAttribute(attr, val);
    };
    set("meta[property='og:title']", "content", document.title);
    set("meta[property='og:image']", "content", ogUrl(m.id));
  }, [data]);

  if (err) {
    return (
      <>
        <Notice />
        <div className="page" data-testid="permalink-error">
          <h1 className="page__title">Gone</h1>
          <p className="page__sub">{err}</p>
          <Link to="/" className="btn">
            Back to the wall
          </Link>
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Notice />
        <div className="loading">Looking it up&hellip;</div>
      </>
    );
  }

  const m = data.message;
  const isFinal = data.frozen && data.is_current;
  const share = data.share_url;

  return (
    <>
      <Notice />
      <main className="wall" data-testid="permalink-wall">
        <div className="stack">
          <div className="stack__top">
            <Poster msg={m} top final={isFinal} testId="permalink-poster" />
          </div>
        </div>
      </main>

      <footer className="rail" style={{ "--rail-ink": INK[m.ink] || INK.tomato }} data-testid="permalink-rail">
        <div className="rail__left">
          {data.rail.map(([t, kind], i) => (
            <span key={i} className={kind === "ink" ? "rail__price" : "rail__seg"}>
              {t}
            </span>
          ))}
        </div>
        <div className="rail__right">
          {data.frozen ? (
            "FROZEN"
          ) : (
            <button
              type="button"
              className="rail__cta"
              onClick={() => navigate("/take")}
              data-testid="permalink-takeover-button"
            >
              Take it
            </button>
          )}
        </div>
      </footer>

      <div className="page" data-testid="permalink-detail">
        <table className="admin__table admin" style={{ width: "100%" }}>
          <tbody>
            <tr>
              <th>Held by</th>
              <td data-testid="detail-name">{m.name}</td>
            </tr>
            <tr>
              <th>Paid</th>
              <td data-testid="detail-price">{m.price_label}</td>
            </tr>
            <tr>
              <th>Reign</th>
              <td data-testid="detail-reign">
                {m.reign_label}
                {m.ended_at ? "" : " and counting"}
              </td>
            </tr>
            {m.dethroned_by ? (
              <tr>
                <th>Dethroned by</th>
                <td data-testid="detail-dethroned-by">{m.dethroned_by}</td>
              </tr>
            ) : null}
            {m.heckle ? (
              <tr>
                <th>The wall said</th>
                <td data-testid="detail-heckle">{m.heckle}</td>
              </tr>
            ) : null}
            {m.obituary ? (
              <tr>
                <th>Obituary</th>
                <td data-testid="detail-obituary">{m.obituary}</td>
              </tr>
            ) : null}
          </tbody>
        </table>

        <hr className="rule" />

        <div className="copyline">
          <span>Share link</span>
          <code data-testid="share-url">{share}</code>
          <button
            type="button"
            className="btn btn--sm btn--ghost"
            onClick={() => {
              navigator.clipboard?.writeText(share);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }}
            data-testid="copy-share"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="admin__note" style={{ marginTop: 12 }}>
          That link previews as the wall itself. This is the card people see.
        </p>
        <img
          src={ogUrl(m.id)}
          alt="share card"
          style={{ marginTop: 16, width: "100%", border: "2px solid var(--ink-black)" }}
          data-testid="og-preview"
        />

        <hr className="rule" />
        <Link to="/fallen" data-testid="permalink-fallen-link">
          Hall of the Fallen
        </Link>
      </div>
    </>
  );
}
