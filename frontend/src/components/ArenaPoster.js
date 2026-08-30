import React from "react";

export default function ArenaPoster({ ad, campaign, side, entering = false, winner = false }) {
  const creative = ad?.creative || {};
  const cls = ["arena-poster", `arena-poster--${creative.ink || "tomato"}`,
    `arena-poster--${creative.template || "type_monument"}`, entering ? "arena-poster--enter" : "",
    winner ? "arena-poster--winner" : ""].filter(Boolean).join(" ");
  return <article className={cls} data-side={side} data-testid={`arena-poster-${side || "preview"}`}>
    <div className="arena-poster__ink" aria-hidden="true" />
    <div className="arena-poster__body">
      <div className="arena-poster__provenance"><span>{side || "candidate"}</span><span>{creative.model?.label || "AI assisted"}</span></div>
      <h2>{creative.headline || "THE WALL IS WAITING"}</h2>
      <p className="arena-poster__support">{creative.supporting_line}</p>
      {campaign?.product_image_url ? <img src={campaign.product_image_url} alt={campaign.product_name || "Sponsored product"} /> : null}
      <div className="arena-poster__foot"><strong>{campaign?.product_name}</strong><span>{ad?.creator_name || "anonymous creator"}</span></div>
      <div className="arena-poster__constraint">{ad?.constraint}</div>
      {winner ? <div className="arena-poster__stamp">LAST AD STANDING</div> : null}
    </div>
  </article>;
}
