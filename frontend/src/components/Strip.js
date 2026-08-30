import React from "react";
import { Link } from "react-router-dom";
import Poster from "@/components/Poster";
import { tearFor, jitterRotation } from "@/lib/format";

/* The last ten, still stuck to the wall further along. */
export const Strip = ({ items = [] }) => {
  if (!items.length) return null;
  return (
    <section className="strip" data-testid="poster-strip">
      <div className="strip__head">
        <span>Pasted over</span>
        <Link to="/fallen" data-testid="strip-all-link">
          All of them
        </Link>
      </div>
      <div className="strip__scroll">
        {items.map((m, i) => (
          <Link
            key={m.id}
            to={`/m/${m.id}`}
            className="strip__item"
            data-testid={`strip-item-${i}`}
          >
            <Poster
              msg={m}
              size="sm"
              torn
              tear={tearFor(m.id)}
              rotation={jitterRotation(m.id, 1.8)}
            />
            <div className="strip__caption">
              <span>{m.price_label}</span>
              <span>{m.reign_label}</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
};

export default Strip;
