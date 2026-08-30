import React from "react";
import { Link } from "react-router-dom";

/* Stencilled site notice along the top of the hoarding. */
export const Notice = ({ takeovers, totalLabel }) => (
  <nav className="notice" data-testid="site-notice">
    <Link to="/" className="notice__title" data-testid="nav-home">
      The Last Billboard
    </Link>
    {takeovers !== undefined ? (
      <span className="notice__meta" data-testid="notice-meta">
        {takeovers} takeovers &middot; {totalLabel} pasted
      </span>
    ) : (
      <span className="notice__meta">One wall. One message.</span>
    )}
    <span className="notice__links">
      <Link to="/fallen" data-testid="nav-fallen">
        Hall of the Fallen
      </Link>
    </span>
  </nav>
);

export default Notice;
