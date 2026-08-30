import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Notice from "@/components/Notice";
import PosterStack from "@/components/PosterStack";
import Rail from "@/components/Rail";
import Strip from "@/components/Strip";
import { getWall, errText } from "@/lib/api";
import { heldClock, countdown } from "@/lib/format";

const POLL_MS = 5000;
/* The transition itself is ~1.5s. The dethroned poster then lingers a beat longer,
   because a heckle nobody can read is a heckle that did not happen. */
const ANIM_MS = 3400;

export default function Wall() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [, setTick] = useState(0);
  const [anim, setAnim] = useState(null);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const seenId = useRef(null);
  const skew = useRef(0);
  const animTimer = useRef(null);

  const load = useCallback(async () => {
    try {
      const d = await getWall();
      if (d?.clock?.server_now) {
        skew.current = new Date(d.clock.server_now).getTime() - Date.now();
      }
      const newId = d?.current?.id || null;

      let expected = null;
      try {
        expected = JSON.parse(sessionStorage.getItem("lb_expect") || "null");
      } catch (e) {
        expected = null;
      }

      const changedInSession = seenId.current && newId && newId !== seenId.current;
      const changedFromCheckout = expected && newId && newId !== expected.prev;

      if (newId && (changedInSession || changedFromCheckout)) {
        const coveredId = changedInSession ? seenId.current : expected.prev;
        setAnim({ entering: newId, covered: coveredId });
        if (animTimer.current) clearTimeout(animTimer.current);
        animTimer.current = setTimeout(() => setAnim(null), ANIM_MS);
        sessionStorage.removeItem("lb_expect");
        if (params.get("took")) {
          params.delete("took");
          setParams(params, { replace: true });
        }
      }
      seenId.current = newId;
      setData(d);
      setErr(null);
    } catch (e) {
      setErr(errText(e, "The wall is not answering."));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, POLL_MS);
    return () => clearInterval(iv);
  }, [load]);

  useEffect(() => {
    const iv = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    document.title = data?.current
      ? `"${data.current.text}" \u2014 The Last Billboard`
      : "The Last Billboard";
  }, [data]);

  if (err && !data) {
    return (
      <>
        <Notice />
        <div className="loading" data-testid="wall-error">
          {err}
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Notice />
        <div className="loading" data-testid="wall-loading">
          Pasting&hellip;
        </div>
      </>
    );
  }

  const cur = data.current;
  const frozen = !!data.frozen;
  const held = cur ? heldClock(cur.started_at, null, skew.current) : "00:00";
  const cd = countdown(data.clock.ends_at, skew.current);

  return (
    <>
      <Notice takeovers={data.takeovers} totalLabel={data.total_paid_label} />

      <main className="wall" data-testid="the-wall">
        {cur ? (
          <PosterStack
            current={cur}
            behind={data.behind}
            entering={anim?.entering === cur.id}
            coveredId={anim?.covered}
            final={frozen}
          />
        ) : (
          <div className="stack">
            <article className="poster poster--top poster--ink-bg poster--tomato" style={{ "--rot": "-1deg" }}>
              <div className="poster__ink" aria-hidden="true" />
              <div className="poster__type">
                <div className="poster__msgbox">
                  <h1 className="poster__message" data-variant="short" style={{ fontSize: "clamp(28px,7vw,92px)" }}>
                    NOTHING YET
                  </h1>
                </div>
                <div className="poster__credit">The wall is bare</div>
              </div>
            </article>
          </div>
        )}
      </main>

      <Rail
        ink={cur?.ink || "tomato"}
        held={held}
        currentLabel={data.price.current_label}
        nextLabel={data.price.next_label}
        countdownLabel={cd}
        frozen={frozen}
        paused={data.clock.paused}
        pending={data.pending}
        holderName={cur?.name}
        onTakeover={() => {
          sessionStorage.setItem("lb_expect", JSON.stringify({ prev: cur?.id || null }));
          navigate("/take");
        }}
      />

      {frozen ? (
        <div className="frozen-note" data-testid="frozen-note">
          The wall is closed. The Last Billboard. Held by {cur?.name}. Forever, or until the server
          bill.
        </div>
      ) : null}

      <Strip items={data.recent} />
    </>
  );
}
