import React from "react";
import { useAutoFit } from "@/lib/useAutoFit";
import Stamp from "@/components/Stamp";
import { reignWords } from "@/lib/format";

/* Two plates: the ink plate is misregistered by 2px. The riso tell. */
export const Poster = ({
  msg,
  top = false,
  size = "lg", // lg = the wall, md = hall of the fallen, sm = the strip
  torn = false,
  tear,
  rotation,
  entering = false,
  covered = false,
  slamStamp = false,
  showStamp = true,
  final = false,
  testId,
}) => {
  const text = msg?.text || "";
  const short = text.trim().length <= 30;
  const { boxRef, elRef } = useAutoFit(text, [size, torn, showStamp, final]);
  const rot = rotation !== undefined ? rotation : msg?.rotation || 0;

  const dethronedEarly = showStamp && !!msg?.ended_at && !!msg?.heckle;
  const stampedEarly = dethronedEarly || final;
  const cls = [
    "poster",
    top ? "poster--top" : "",
    size === "sm" ? "poster--sm" : "",
    size === "md" ? "poster--md" : "",
    torn ? "poster--torn" : "",
    msg?.mode === "black_bg" ? "poster--black-bg" : "poster--ink-bg",
    `poster--${msg?.ink || "tomato"}`,
    msg?.image_url ? "poster--has-image" : "",
    entering ? "poster--enter" : "",
    covered ? "poster--covered" : "",
    stampedEarly ? "poster--stamped" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const style = { "--rot": `${rot}deg` };
  if (tear) style["--tear"] = tear;

  const dethroned = dethronedEarly;

  return (
    <article className={cls} style={style} data-testid={testId}>
      <div className="poster__ink" aria-hidden="true" />
      <div className="poster__type">
        <div className="poster__msgbox" ref={boxRef}>
          <h1
            className="poster__message"
            data-variant={short ? "short" : "long"}
            ref={elRef}
            data-testid={testId ? `${testId}-message` : "poster-message"}
          >
            {short ? text.toUpperCase() : text}
          </h1>
        </div>
        {msg?.ad_line && size === "lg" && !stampedEarly ? (
          <p className="poster__adline" data-testid="poster-adline">
            <em>{msg.ad_line}</em>
          </p>
        ) : null}
        <div className="poster__credit" data-testid="poster-credit">
          {msg?.name || "anonymous"}
          {size === "sm" ? "" : ` \u00b7 ${msg?.price_label || ""}`}
        </div>
      </div>
      {msg?.image_url ? (
        <img
          className="poster__image"
          src={msg.image_url}
          alt=""
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
          data-testid="poster-image"
        />
      ) : null}
      {final ? (
        <Stamp
          line1="Final holder"
          line2="The wall is closed."
          msg={msg}
          ink="teal"
          size={size}
          testId="final-holder-stamp"
        />
      ) : dethroned ? (
        <Stamp
          line1={`Dethroned \u00b7 Held ${msg.reign_label || reignWords(msg.reign_seconds)}`}
          line2={msg.heckle}
          msg={msg}
          ink="tomato"
          size={size}
          slam={slamStamp}
        />
      ) : null}
    </article>
  );
};

export default Poster;
