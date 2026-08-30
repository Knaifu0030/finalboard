export const TEARS = ["var(--tear-a)", "var(--tear-b)", "var(--tear-c)", "var(--tear-d)"];

export function hashOf(str) {
  let h = 0;
  for (let i = 0; i < (str || "").length; i++) h = (h * 31 + str.charCodeAt(i)) % 100000;
  return h;
}

export function tearFor(id) {
  return TEARS[hashOf(id) % TEARS.length];
}

export function jitterRotation(id, spread = 2.4) {
  const h = hashOf(id);
  const r = ((h % 1000) / 1000) * spread * 2 - spread;
  return Math.abs(r) < 0.4 ? (r >= 0 ? 0.8 : -0.8) : Number(r.toFixed(2));
}

export function heldClock(startedAtIso, endedAtIso, skewMs = 0) {
  const start = startedAtIso ? new Date(startedAtIso).getTime() : null;
  if (!start) return "00:00";
  const end = endedAtIso ? new Date(endedAtIso).getTime() : Date.now() + skewMs;
  let s = Math.max(0, Math.floor((end - start) / 1000));
  const d = Math.floor(s / 86400);
  s -= d * 86400;
  const h = Math.floor(s / 3600);
  s -= h * 3600;
  const m = Math.floor(s / 60);
  s -= m * 60;
  const p = (n) => String(n).padStart(2, "0");
  if (d > 0) return `${d}d ${p(h)}:${p(m)}:${p(s)}`;
  if (h > 0) return `${p(h)}:${p(m)}:${p(s)}`;
  return `${p(m)}:${p(s)}`;
}

export function countdown(endsAtIso, skewMs = 0) {
  if (!endsAtIso) return null;
  const end = new Date(endsAtIso).getTime();
  let s = Math.max(0, Math.floor((end - (Date.now() + skewMs)) / 1000));
  const h = Math.floor(s / 3600);
  s -= h * 3600;
  const m = Math.floor(s / 60);
  s -= m * 60;
  const p = (n) => String(n).padStart(2, "0");
  return `${p(h)}:${p(m)}:${p(s)}`;
}

export function reignWords(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  if (s >= 86400) return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
  if (s >= 3600) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${s}s`;
}
