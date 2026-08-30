import React, { useCallback, useEffect, useRef, useState } from "react";
import { getChat, postChat, errText } from "@/lib/api";

const POLL_MS = 4000;
const MAX_TEXT = 140;
const NAME_KEY = "lb_chat_name";

const wide = () =>
  typeof window !== "undefined" &&
  window.matchMedia &&
  window.matchMedia("(min-width: 1180px)").matches;

/* Chatter on the hoarding. People yelling next to the wall while the money fight happens.
   Every line passes the same moderation gate as a poster. */
export const Chatter = () => {
  const [open, setOpen] = useState(wide());
  const [msgs, setMsgs] = useState([]);
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) || "");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const logRef = useRef(null);
  const stick = useRef(true);

  const load = useCallback(async () => {
    try {
      const d = await getChat();
      setMsgs(d.messages || []);
    } catch (e) {
      /* the wall is quiet; keep what we have */
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, POLL_MS);
    return () => clearInterval(iv);
  }, [load]);

  useEffect(() => {
    const el = logRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [msgs, open]);

  const onScroll = () => {
    const el = logRef.current;
    if (!el) return;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  const submit = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true);
    setNote(null);
    const nm = name.trim().slice(0, 24);
    if (nm) localStorage.setItem(NAME_KEY, nm);
    try {
      const posted = await postChat({ name: nm, text: t });
      setMsgs((m) => [...m, posted]);
      setText("");
      stick.current = true;
    } catch (err) {
      setNote(errText(err, "The wall did not take that."));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="chatter-tab"
        onClick={() => setOpen(true)}
        data-testid="chatter-open"
        aria-label="Open the chatter"
      >
        Chatter
      </button>
    );
  }

  return (
    <aside className="chatter" data-testid="chatter-panel">
      <div className="chatter__hd">
        <span className="chatter__title">
          Chatter <span className="chatter__live">live</span>
        </span>
        <button
          type="button"
          className="chatter__close"
          onClick={() => setOpen(false)}
          data-testid="chatter-close"
          aria-label="Close the chatter"
        >
          &times;
        </button>
      </div>

      <div className="chatter__log" ref={logRef} onScroll={onScroll} data-testid="chatter-log">
        {msgs.length === 0 ? (
          <p className="chatter__empty">Nobody has said anything yet. The wall is used to it.</p>
        ) : (
          msgs.map((m) => (
            <p className="chatter__line" key={m.id} data-testid="chatter-line">
              <span className="chatter__name">{m.name}</span>
              <span className="chatter__dot" aria-hidden="true">
                &middot;
              </span>
              <span className="chatter__text">{m.text}</span>
            </p>
          ))
        )}
      </div>

      {note ? (
        <p className="chatter__note" data-testid="chatter-note">
          {note}
        </p>
      ) : null}

      <form className="chatter__form" onSubmit={submit}>
        <input
          className="chatter__name-in"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="name"
          maxLength={24}
          aria-label="Your name"
          data-testid="chatter-name-input"
        />
        <div className="chatter__row">
          <input
            className="chatter__text-in"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX_TEXT))}
            placeholder="say something to the wall"
            maxLength={MAX_TEXT}
            aria-label="Message"
            data-testid="chatter-text-input"
          />
          <button
            type="submit"
            className="chatter__send"
            disabled={busy || !text.trim()}
            data-testid="chatter-send"
          >
            {busy ? "\u2026" : "Post"}
          </button>
        </div>
      </form>
    </aside>
  );
};

export default Chatter;
