import React from "react";

/* A big, unmissable paste-up button pinned to the margin.
   Same world as the wall: ink ground, black keyline, one hard shadow, no radius. */
export const SideTake = ({ nextLabel, pending, frozen, onTakeover }) => {
  if (frozen) return null;

  if (pending) {
    return (
      <div className="side-take side-take--pending" data-testid="side-take-pending">
        <span className="side-take__kicker">Someone is at the counter</span>
        <span className="side-take__price">PENDING</span>
        <span className="side-take__sub">{pending.amount_label}</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      className="side-take"
      onClick={onTakeover}
      data-testid="side-take-button"
    >
      <span className="side-take__kicker">Paste over it for</span>
      <span className="side-take__price">{nextLabel}</span>
      <span className="side-take__sub">Take the wall &rarr;</span>
    </button>
  );
};

export default SideTake;
