import React from "react";

const INK = { tomato: "var(--ink-tomato)", mustard: "var(--ink-mustard)", teal: "var(--ink-teal)" };

/* The hoarding edge. One mono line. The price is the button. */
export const Rail = ({
  ink = "tomato",
  held,
  currentLabel,
  nextLabel,
  countdownLabel,
  frozen,
  paused,
  pending,
  holderName,
  onTakeover,
  ctaHref,
}) => {
  const style = { "--rail-ink": INK[ink] || INK.tomato };

  return (
    <footer className="rail" style={style} data-testid="black-rail">
      <div className="rail__left">
        {frozen ? (
          <span className="rail__frozen" data-testid="rail-frozen">
            The Last Billboard. Held by {holderName}. Forever, or until the server bill.
          </span>
        ) : (
          <>
            <span className="rail__seg" data-testid="rail-held">
              Held {held}
            </span>
            <span className="rail__dot" aria-hidden="true">
              &middot;
            </span>
            <span className="rail__seg rail__hideable" data-testid="rail-current-price">
              {currentLabel || "unpasted"}
            </span>
            <span className="rail__dot rail__hideable" aria-hidden="true">
              &middot;
            </span>
            {pending ? (
              <span className="rail__pending" data-testid="rail-pending">
                Pending &middot; {pending.name} &middot; {pending.amount_label}
              </span>
            ) : (
              <button
                type="button"
                className="rail__cta"
                onClick={onTakeover}
                data-testid="rail-takeover-button"
              >
                <span className="rail__hideable">Paste over it for </span>
                <span className="rail__price">{nextLabel}</span>
              </button>
            )}
          </>
        )}
      </div>
      <div className="rail__right" data-testid="rail-countdown">
        {frozen ? "FROZEN" : paused ? "PAUSED" : countdownLabel || "--:--:--"}
      </div>
    </footer>
  );
};

export default Rail;
