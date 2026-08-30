import React from "react";

const INK = { tomato: "#e63f1e", mustard: "#f0b429", teal: "#1e6e78", black: "#141414", cream: "#f3e7d3" };

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const f = (v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
};

/* A stamp inked too close in tone to the poster it landed on is no stamp at all.
   Tomato on mustard is a real riso overprint. Tomato on teal is mud. */
function readable(desired, msg) {
  const bg = msg.mode === "ink_bg" ? INK[msg.ink] || INK.tomato : INK.black;
  const bgL = lum(bg);
  const wanted = INK[desired] || INK.tomato;
  if (Math.abs(lum(wanted) - bgL) >= 0.12) return desired;
  return bgL < 0.35 ? "cream" : "black";
}

export const Stamp = ({ line1, line2, msg, ink = "tomato", size = "lg", slam = false, testId }) => {
  const tone = readable(ink, msg || {});
  return (
    <div
      className={["stamp", `stamp--${tone}`, `stamp--${size}`, slam ? "stamp--slam" : ""]
        .filter(Boolean)
        .join(" ")}
      data-testid={testId || "poster-stamp"}
      aria-hidden={size === "sm" ? "true" : undefined}
    >
      <div className="stamp__box">
        <div className="stamp__l1">{line1}</div>
        {line2 && size !== "sm" ? <div className="stamp__l2">{line2}</div> : null}
      </div>
    </div>
  );
};

export default Stamp;
