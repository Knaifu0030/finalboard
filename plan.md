# plan.md — The Last Billboard (Fly-poster edition) — UPDATED

## 1) Objectives
- Prove the **core workflow** works end-to-end in isolation: **price ladder + atomic takeover**, **Razorpay Standard Checkout order+verify math**, **Anthropic (via Emergent) moderation + voice JSON**, and **server-rendered OG card** that matches the wall. ✅ **DONE (Phase 1: 64/64 checks)**
- Ship a V1 web app that looks like a **real paste-up wall** (not a component library) and supports the full 48h loop: takeovers, pending, stamp, hall, permalinks, admin controls, freeze. ✅ **DONE (Phase 2: built + verified)**
- Keep code extensible for future features (sponsor rail, Season 2, real email sending). ✅ **Architecture ready; Phase 3 backlog defined**
- New objective after testing: **cross-page stability** (no console/page errors, no failed API requests) and **OG parity** (same fonts/files and same stamp rules between live wall and card). ✅ **DONE**

## 2) Implementation Steps

### Phase 1 — Core POC in isolation (must pass before app work)
**Status:** ✅ COMPLETE

**User stories (completed)**
1. Run one script to create a Razorpay order and see a valid order_id returned. ✅
2. Verify a Razorpay payment signature locally using HMAC-SHA256 and see PASS/FAIL deterministically. ✅
3. Send sample messages to moderation and see ALLOW/BLOCK match the nuanced rules. ✅
4. Generate ad_line/heckle/obituary JSON in the wall’s voice with strict parsing. ✅
5. Render a PNG OG card that visually matches the fly-poster spec (ink poster, rotation, stamp, rail). ✅
6. Simulate competing bids and confirm **price ladder** + **atomic swap** are correct in MongoDB. ✅

**Implementation delivered (key artifacts)**
- `/app/test_core.py` — green run **64/64** proving:
  - Razorpay order creation + signature verification + webhook signature verification
  - Moderation edge cases (promote yes / attack no)
  - Voice JSON (strict parse) in the billboard’s dry register
  - Atomic takeover logic under concurrency
  - Freeze + FINAL HOLDER logic
  - Outbox email queueing
  - OG PNG rendering via Pillow (Archivo Black + JetBrains Mono)

**Exit criteria (Phase 1)**
- `python /app/test_core.py` passes and generates OG PNGs for inspection. ✅

---

### Phase 2 — V1 App Development (build around proven core)
**Status:** ✅ COMPLETE AND VERIFIED

**User stories (completed)**
1. Visitor lands on `/` and understands: one wall, one message, one price to paste over. ✅
2. Bidder opens `/take`, enters message/name/email/image, sees moderation feedback, and pays via Razorpay modal. ✅
3. Viewer opens `/m/[id]` and sees the poster as it looked, with a shareable OG preview. ✅
4. Competitor sees the current price and minimum bump in their local display currency (₹ India, $ elsewhere). ✅
5. Admin can approve/reject pending, pause/unpause/edit countdown, revert/delete, recap, and freeze works at expiry. ✅
6. Dethroned holders get an email **queued** (Resend not configured) and a permalink. ✅

**Backend (API + jobs) — implemented**
Location: `/app/backend/server.py` + `/app/backend/core/*`

- Public wall state
  - `GET /api/wall` — current + behind + recent + price ladder + pending rail state + clock state.
  - `GET /api/messages` — used by `/fallen`, supports sort by `reign` and `price`.
  - `GET /api/message/{id}` — message detail for `/m/:id`.
- Takeover pipeline
  - `POST /api/moderate` — word-list pre-gate + Claude ALLOW/BLOCK.
  - `POST /api/create-order` — validates min bid + self-dethrone, runs moderation, creates pending doc; creates Razorpay order when configured.
  - `POST /api/verify-payment` — verifies HMAC signature; executes takeover; idempotent.
  - `POST /api/payment-failed` — marks pending failed.
  - `POST /api/webhook/razorpay` — signature-verified webhook handler (built, not yet registered in Razorpay dashboard).
- OG/share
  - `GET /api/og/{id}.png` — Pillow renderer.
  - `GET /api/m/{id}` — crawler share page w/ OG meta tags + JS bounce to `/m/{id}`.
  - Note: share link is `/api/m/<id>` (meta) rather than `/m/<id>` due to SPA non-SSR constraint.
- Clock + expiry
  - Clock starts **paused**; admin flips it live.
  - Background loop freezes wall when expired and queues final holder email.
- Admin
  - `/api/admin/*`: login, state, pending approve/reject, revert, delete, pause, clock, recap, manual takeover, refund, drain outbox.
- Persistence
  - MongoDB collections: `messages`, `settings`, `pending`, `outbox`.
  - Atomic takeover via settings pointer guard (`find_one_and_update`).

**Frontend (fly-poster UI) — implemented**
Location: `/app/frontend/src`

- Pages
  - `/` (Wall): paste-up stack, black rail, strip.
  - `/take`: print-shop form + Razorpay modal open/dismiss/fail handling.
  - `/m/:id`: permalink view + share link + OG preview.
  - `/fallen`: dense paste-up masonry with stamps + obituary.
  - `/admin`: foreman clipboard console.
- Components
  - `Poster` (sizes: lg/md/sm), `PosterStack`, `Stamp`, `Rail`, `Strip`, `Notice`.
- Styling (index.css)
  - **Two typefaces only**; no rounded corners; no gradients; **only one shadow** (top poster).
  - Torn edges via clip-path; riso misregistration (exactly one plate offset).
  - Rubber stamp with hard-edged uneven ink mask (no blur/no noise image).
  - One takeover transition: drop-in + tear + stamp slam; `prefers-reduced-motion` disables.
- Fonts
  - **Self-hosted TTFs** (same files used by server-side OG renderer) to guarantee parity.

**Testing (Phase 2) — completed + remediated**
- Testing agent iteration 1: backend suite passed.
- Testing agent iteration 2: frontend issues found; all fixed.
- Final regression sweep:
  - **0 console errors**, **0 page errors**, **0 failed API requests** across `/`, `/take`, `/fallen`, `/admin`, `/m/:id`, and 404 fallback.
  - Art-direction audit: no border-radius; no gradients (except stamp mask); only top poster has shadow; paper background correct; fonts correct.

**Key bug fixes applied during Phase 2 hardening**
1. Google Fonts not loading → self-hosted the exact TTFs used by OG renderer.
2. Auto-fit oversizing on stamped posters due to percentage padding vs width → explicit height allocation + computed-padding subtraction.
3. Stamp collisions → stamped posters yield lower third; credit pinned; stamp repositioned.
4. Paste-up stack ordering and offsets corrected.
5. Dethronement beat visibility → covered poster hangs below + lingers long enough to read.
6. Stamp legibility → softened uneven mask + divider between lines.
7. Stamp color mud on teal posters → luminance-based readable ink rule in both frontend + OG renderer.
8. Misregistration double-offset fix → only one plate is offset.
9. Fixed system copy casing → `.sheet__error` no longer uppercases.
10. Mobile rail wrap/overlap → ellipsis + shorter labels.
11. Torn edges too aggressive → regenerated with lower amplitude.

**Exit criteria (Phase 2)**
- Real user can paste over via Razorpay; pending rail state works; `/api/m` share works; OG renders; admin can operate the wall; freeze works. ✅

---

### Phase 3 — Polish + extensibility hooks (post-V1)
**Status:** ⏳ Backlog / not started

**User stories (next)**
1. As the operator, I can enable real sending (Resend) without changing business logic.
2. As the operator, I can register Razorpay webhooks and reconcile captured payments reliably.
3. As the admin, I can remove+refund quickly with a single action (with audit log).
4. As a promoter, I can buy “Sponsor the rail” (positive/promotional only, max 3 lines).
5. As a returning visitor, I can browse a very large Hall fast (pagination / virtualization).
6. As the creator, I can run Season 2 with carry-over rules.

**Steps (planned)**
- **Resend wiring** (when key arrives)
  - Add `RESEND_API_KEY` + `RESEND_FROM`, restart backend.
  - Confirm `/admin` → Outbox drains and marks `sent=true`.
- **Razorpay webhook registration**
  - Register `/api/webhook/razorpay` in Razorpay dashboard.
  - Add event reconciliation rules (payment.captured is the source of truth).
- **Admin safety tools**
  - One-click remove+refund flow; optional audit log collection.
- **Performance**
  - Cache OG renders; paginate `/fallen` beyond ~400; lazy-load images.
- **Extensibility**
  - Feature flags for sponsor rail + Season 2; schema versioning.

---

## 3) Next Actions (immediate)
**Status:** ✅ Completed / Ready for next feature tranche

1. Phase 1 POC shipped and proven (64/64). ✅
2. Phase 2 full app shipped with Razorpay + AI + OG + admin tools. ✅
3. DB reset + seeded launch fight + clock paused. ✅
4. Prepare for launch:
   - (Optional) register Razorpay webhook URL + secret in dashboard.
   - Provide Resend key later if you want real dethrone emails.

## 4) Success Criteria
- Phase 1: one command produces Razorpay order_id, deterministic signature verify, moderation correctness, strict JSON voice, OG PNG render, and atomic DB takeover. ✅
- Phase 2: users can pay to paste over; pending/approved works; `/api/m` shares with correct OG; freeze after countdown; admin can pause/approve/revert; no cross-page runtime errors. ✅
- Phase 3: can enable Resend by env vars; webhook reconciliation hardened; sponsor rail + Season 2 hooks ship without rewrites. ⏳

---

## Post-launch fix — user-reported error overlay (verified, iteration_3: 100%)

**Reported:** a full-screen red "Uncaught runtime errors: Cannot read properties of undefined
(reading 'M_ID')" overlay covering the whole wall.

**Root cause:** not an app bug. Every stack frame was inside a Chrome extension
(`chrome-extension://almalgbpmcfpdaopimbdchdliminoign/executors/200.js`) that monkey-patches
`XMLHttpRequest` and throws on its own internal `M_ID`. webpack-dev-server 5's runtime-error
overlay listens to *every* window error event, including third-party ones, so it slabbed the
overlay over the wall.

**Fix:**
1. `frontend/craco.config.js` — `devServer.client.overlay.runtimeErrors` is now a predicate that
   suppresses only errors whose stack/message/filename/sourceURL sit in a browser extension.
   The predicate is **fully self-contained**, because webpack-dev-server stringifies it and
   evaluates it in the browser (my first attempt referenced a helper from the config's Node scope,
   which silently suppressed *all* runtime errors — caught by an explicit guard-rail test).
2. `frontend/src/index.js` — capture-phase `error` / `unhandledrejection` listeners that
   `preventDefault()` + `stopImmediatePropagation()` for extension-origin throws only.

**Verified:** extension error → no overlay, wall stays usable. Genuine app error from our own
bundle → overlay still shown, so real bugs are not hidden. Zero console/page errors and zero
failed `/api/*` requests across `/`, `/take`, `/fallen`, `/admin`, `/m/:id` and the 404 fallback.
Currency detection confirmed (Asia/Kolkata → ₹, America/New_York → $).

---

## Phase 4 — Session 2 requests (Status: ✅ COMPLETE, verified iteration_4)

User asked for three things:

1. **Admin password change** → `ADMIN_PASSWORD=Kaneki1#` in `backend/.env`. Old password now
   rejected; new one accepted. (No code change — env only.)
2. **Prominent side takeover button** → new `components/SideTake.js`, a big fly-poster button
   pinned to the left margin (ink-tomato ground, black keyline, hard shadow, Archivo Black price).
   Reflects live state: clickable price, PENDING (mustard), or hidden when frozen. Shares the same
   `goTake()` handler as the rail. Visible on wide screens (≥1280px); below that the rail keeps the
   CTA so nothing is lost.
3. **Moderated live chat** → new `components/Chatter.js` side panel + backend `GET/POST /api/chat`.
   Every posted line runs through the existing `ai.moderate` gate (wordlist + Claude); abusive
   lines are rejected (422) and never stored. Panel polls every 4s, docks open on wide screens,
   collapses to a reopen tab / full-screen drawer on smaller screens. New `chat` Mongo collection
   with a `created_at` index.

Layout note: on ≥1280px the paste-up stack narrows to `min(50vw,900px)` so both margins hold a side
element without touching the poster; strip gets right padding to clear the docked chatter. Art
direction untouched (no radius, no gradients, two typefaces, single poster shadow).
