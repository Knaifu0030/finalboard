import React from "react";
import Poster from "@/components/Poster";
import { tearFor } from "@/lib/format";

/* A real paste-up: the ones underneath still peek out, torn at the edges. */
export const PosterStack = ({ current, behind = [], entering, coveredId, final }) => {
  if (!current) return null;
  const layers = behind.slice(0, 3);
  return (
    <div className="stack" data-testid="poster-stack">
      {layers.map((m, i) => (
        <div
          key={m.id}
          className={[
            "stack__layer",
            `stack__layer--${i + 1}`,
            coveredId === m.id ? "stack__layer--covering" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <Poster
            msg={m}
            torn
            tear={tearFor(m.id)}
            covered={coveredId === m.id}
            slamStamp={coveredId === m.id}
            testId={`poster-behind-${i}`}
          />
        </div>
      ))}
      <div className="stack__top">
        <Poster
          msg={current}
          top
          entering={entering}
          final={final}
          testId="poster-current"
        />
      </div>
    </div>
  );
};

export default PosterStack;
