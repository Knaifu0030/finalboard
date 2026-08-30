import { useEffect, useLayoutEffect, useRef } from "react";

/* Auto-fit the display type inside the poster.
   <=30 chars: all caps, as large as fits. Longer: sentence case, max 4 lines.
   Binary search on font-size, same intent as the server-side Pillow renderer. */
export function useAutoFit(text, deps = []) {
  const boxRef = useRef(null);
  const elRef = useRef(null);
  const lastKey = useRef("");

  const fit = () => {
    const box = boxRef.current;
    const el = elRef.current;
    if (!box || !el) return;
    const cs = window.getComputedStyle(box);
    const availH =
      box.clientHeight - (parseFloat(cs.paddingTop) || 0) - (parseFloat(cs.paddingBottom) || 0);
    const availW =
      box.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
    if (availH < 10 || availW < 10) return;

    const key = `${text}|${Math.round(availW)}x${Math.round(availH)}`;
    const short = (text || "").trim().length <= 30;
    const maxLines = short ? 3 : 4;

    const height = () => el.getBoundingClientRect().height;
    const overflowsWidth = () => el.scrollWidth > Math.ceil(availW) + 2;

    let lo = 8;
    let hi = Math.min(520, Math.max(12, Math.floor(availH * 1.25)));
    let best = lo;
    el.style.whiteSpace = "normal";
    for (let i = 0; i < 24 && lo <= hi; i++) {
      const mid = Math.floor((lo + hi) / 2);
      el.style.fontSize = mid + "px";
      const h = height();
      const lines = Math.max(1, Math.round(h / (mid * 0.94)));
      if (h <= availH + 1 && lines <= maxLines && !overflowsWidth()) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    el.style.fontSize = best + "px";
    lastKey.current = key;
  };

  useLayoutEffect(fit);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(fit, [text, ...deps]);

  // the display face loads after first paint; refit once it is actually there
  useEffect(() => {
    let dead = false;
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => {
        if (!dead) fit();
      });
    }
    const t1 = setTimeout(fit, 120);
    const t2 = setTimeout(fit, 600);
    return () => {
      dead = true;
      clearTimeout(t1);
      clearTimeout(t2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  useEffect(() => {
    const box = boxRef.current;
    if (!box || typeof ResizeObserver === "undefined") return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(fit);
    });
    ro.observe(box);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return { boxRef, elRef };
}
