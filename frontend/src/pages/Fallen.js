import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Notice from "@/components/Notice";
import Poster from "@/components/Poster";
import { getMessages, errText } from "@/lib/api";
import { tearFor, jitterRotation, hashOf } from "@/lib/format";

export default function Fallen() {
  const [sort, setSort] = useState("reign");
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null);
    getMessages(sort)
      .then(setData)
      .catch((e) => setErr(errText(e)));
  }, [sort]);

  return (
    <>
      <Notice />
      <div className="page page--wide" style={{ paddingBottom: 0 }}>
        <h1 className="page__title">Hall of the Fallen</h1>
        <p className="page__sub">
          Every poster that ever went up. The wall keeps all of them.
          {data ? ` ${data.count} so far.` : ""}
        </p>
      </div>

      <div className="fallen__controls" data-testid="fallen-controls">
        <span>Sort</span>
        <button
          type="button"
          className="toggle"
          aria-pressed={sort === "reign"}
          onClick={() => setSort("reign")}
          data-testid="fallen-toggle-reign"
        >
          By reign
        </button>
        <button
          type="button"
          className="toggle"
          aria-pressed={sort === "price"}
          onClick={() => setSort("price")}
          data-testid="fallen-toggle-price"
        >
          By price paid
        </button>
        <button
          type="button"
          className="toggle"
          aria-pressed={sort === "recent"}
          onClick={() => setSort("recent")}
          data-testid="fallen-toggle-recent"
        >
          Newest first
        </button>
      </div>

      {err ? (
        <div className="loading" data-testid="fallen-error">
          {err}
        </div>
      ) : !data ? (
        <div className="loading">Peeling them off&hellip;</div>
      ) : !data.messages.length ? (
        <div className="loading" data-testid="fallen-empty">
          Nothing has fallen yet.
        </div>
      ) : (
        <div className="masonry" data-testid="fallen-masonry">
          {data.messages.map((m, i) => (
            <Link
              key={m.id}
              to={`/m/${m.id}`}
              className="masonry__item"
              style={{
                "--rot": `${jitterRotation(m.id, 2.5)}deg`,
                "--tx": `${(hashOf(m.id) % 13) - 6}px`,
              }}
              data-testid={`fallen-item-${i}`}
            >
              <Poster msg={m} size="md" torn={!m.is_current} tear={tearFor(m.id)} rotation={0} />
              {m.obituary ? <p className="masonry__obit">{m.obituary}</p> : null}
              <div className="masonry__meta">
                {m.price_label} &middot; held {m.reign_label}
                {m.is_current ? " \u00b7 on the wall now" : ""}
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="page">
        <Link to="/" className="btn" data-testid="fallen-back">
          Back to the wall
        </Link>
      </div>
    </>
  );
}
