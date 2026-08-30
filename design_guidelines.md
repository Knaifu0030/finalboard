{
  "project": {
    "name": "The Last Billboard",
    "north_star": "A single physical object on the internet: a wheat-pasted wall with one live poster and a black hoarding rail. No app chrome. Visual fidelity is the product.",
    "non_negotiables": {
      "no_rounded_corners": true,
      "no_gradients": true,
      "no_noise_or_grain": true,
      "no_icons_or_emoji": true,
      "no_component_library_look": true,
      "only_shadow": "Top poster hard offset shadow only",
      "only_texture": "1–2px riso misregistration on ink plate only",
      "only_motion": "Takeover drop-in + tear + stamp sequence; otherwise only HELD timer",
      "two_typefaces_only": ["Archivo Black", "JetBrains Mono"],
      "palette_fixed": {
        "paper": "#F3E7D3",
        "black": "#141414",
        "tomato": "#E63F1E",
        "mustard": "#F0B429",
        "teal": "#1E6E78"
      }
    }
  },

  "design_tokens": {
    "css_custom_properties": {
      ":root": {
        "--paper": "#F3E7D3",
        "--ink-black": "#141414",
        "--ink-tomato": "#E63F1E",
        "--ink-mustard": "#F0B429",
        "--ink-teal": "#1E6E78",

        "--font-display": "'Archivo Black', system-ui, -apple-system, 'Segoe UI', sans-serif",
        "--font-mono": "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",

        "--mono-size": "13px",
        "--mono-size-sm": "12px",
        "--mono-leading": "1.25",

        "--display-leading": "0.92",
        "--display-tracking": "0.01em",

        "--space-1": "4px",
        "--space-2": "8px",
        "--space-3": "12px",
        "--space-4": "16px",
        "--space-5": "24px",
        "--space-6": "32px",
        "--space-7": "48px",

        "--rule-1": "1px",
        "--rule-2": "2px",
        "--rule-6": "6px",

        "--poster-shadow": "6px 6px 0 var(--ink-black)",
        "--poster-rotate-min": "-1.5deg",
        "--poster-rotate-max": "1.5deg",

        "--misreg": "2px",
        "--misreg-y": "1px",

        "--rail-height": "52px",
        "--rail-height-sm": "56px",

        "--wall-max": "1120px",
        "--poster-w-desktop": "65vw",
        "--poster-w-max": "760px",
        "--poster-w-mobile": "calc(100vw - 2 * var(--space-4))",

        "--poster-aspect": "3 / 4",
        "--poster-pad": "clamp(16px, 2.2vw, 26px)",
        "--poster-margin-bottom": "clamp(12px, 1.6vw, 18px)",

        "--focus-outline": "2px solid var(--ink-black)",
        "--focus-offset": "2px"
      }
    },
    "global_css_rules": {
      "html_body": [
        "html, body { height: 100%; background: var(--paper); color: var(--ink-black); }",
        "body { margin: 0; font-family: var(--font-mono); font-size: var(--mono-size); line-height: var(--mono-leading); }",
        "* { box-sizing: border-box; }",
        "::selection { background: var(--ink-black); color: var(--paper); }"
      ],
      "links_buttons": [
        "a { color: inherit; text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 2px; }",
        "button { font: inherit; color: inherit; background: transparent; border: 0; padding: 0; }",
        "button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible { outline: var(--focus-outline); outline-offset: var(--focus-offset); }"
      ],
      "no_tailwind_component_look": [
        "Avoid shadcn Button/Card/etc. Use plain semantic HTML + custom CSS modules/classes.",
        "Tailwind may be used only for layout utilities if it does not introduce rounding/shadows/rings. Prefer plain CSS for fidelity."
      ]
    }
  },

  "layout": {
    "page_structure": {
      "routes": {
        "/": "Wall (current poster + 2–3 behind) + Black Rail + below-fold last 10 strip",
        "/take": "Takeover Sheet (print-shop order form) + Razorpay modal",
        "/m/[id]": "Permalink poster view matching OG renderer + rail + CTA",
        "/fallen": "Hall of the Fallen masonry paste-up",
        "/admin": "Mono-only clipboard console"
      },
      "wall_container": {
        "max_width": "var(--wall-max)",
        "padding": "var(--space-4)",
        "alignment": "Left-aligned reading flow; poster stack centered within wall area only (not the whole app)."
      }
    },
    "grid_responsive": {
      "mobile_first": [
        "Poster fills width: width: var(--poster-w-mobile)",
        "Rail sticks to bottom: position: sticky; bottom: 0",
        "Countdown must not wrap on 360px: use CSS grid with fixed right column"
      ],
      "desktop": [
        "Poster width ~65% viewport with max: min(var(--poster-w-desktop), var(--poster-w-max))",
        "Rail sits beneath wall content (not floating), but can remain sticky if desired"
      ]
    }
  },

  "components": {
    "component_path": {
      "primary": "Avoid shadcn/ui for visible primitives (explicit failure condition).",
      "allowed_shadcn": [
        "/app/frontend/src/components/ui/dialog.jsx (Razorpay modal wrapper if needed)",
        "/app/frontend/src/components/ui/sheet.jsx (only if it can be made perfectly square + no shadow; otherwise avoid)",
        "/app/frontend/src/components/ui/textarea.jsx and input.jsx (only if fully restyled to square, no ring, no rounding)",
        "/app/frontend/src/components/ui/sonner.jsx (DO NOT USE; toasts are forbidden by spec)"
      ],
      "custom_components_to_build": [
        "PosterStack.js",
        "Poster.js (ink plate + type plate + optional image)",
        "BlackRail.js",
        "DethroneStamp.js",
        "TakeoverSheet.js",
        "FallenMasonry.js",
        "AdminConsole.js"
      ]
    },

    "poster_dom_structure": {
      "notes": "Two-layer approach: ink plate (misregistered) + type plate (crisp). No rounded corners. Only top poster gets the 6px offset shadow.",
      "jsx_skeleton": "<article className=\"poster poster--top poster--ink-bg poster--tomato\" data-testid=\"poster-current\">\n  <div className=\"poster__ink\" aria-hidden=\"true\" />\n  <div className=\"poster__type\">\n    <header className=\"poster__header\">\n      <h1 className=\"poster__message\" data-testid=\"poster-message\">MESSAGE</h1>\n      <p className=\"poster__adline\" data-testid=\"poster-adline\"><em>ad_line in italic mono</em></p>\n    </header>\n\n    <div className=\"poster__credit\" data-testid=\"poster-credit\">PRINTED FOR NAME</div>\n\n    <img className=\"poster__image\" alt=\"\" src=\"...\" data-testid=\"poster-image\" />\n  </div>\n</article>"
    }
  },

  "implementation_blueprint": {
    "1_tokens_and_type_scale": {
      "display_autofit_tokens": {
        "--display-max": "clamp(44px, 8.5cqw, 92px)",
        "--display-mid": "clamp(34px, 6.8cqw, 72px)",
        "--display-min": "clamp(26px, 5.2cqw, 54px)",
        "note": "Use container queries (cqw) by setting container-type: inline-size on .poster__type."
      },
      "poster_base_css": "/* Poster base */\n.poster {\n  position: relative;\n  aspect-ratio: var(--poster-aspect);\n  border: var(--rule-2) solid var(--ink-black);\n  background: transparent;\n  transform: rotate(var(--rot, 0deg));\n  transform-origin: 50% 50%;\n}\n\n.poster--top {\n  box-shadow: var(--poster-shadow);\n}\n\n.poster__type {\n  position: relative;\n  z-index: 2;\n  padding: var(--poster-pad);\n  padding-bottom: calc(var(--poster-pad) + var(--poster-margin-bottom));\n  container-type: inline-size;\n}\n\n.poster__message {\n  font-family: var(--font-display);\n  line-height: var(--display-leading);\n  letter-spacing: var(--display-tracking);\n  margin: 0;\n  text-wrap: balance;\n}\n\n.poster__adline {\n  margin: var(--space-2) 0 0;\n  font-family: var(--font-mono);\n  font-size: var(--mono-size-sm);\n  line-height: 1.2;\n}\n\n.poster__adline em {\n  font-style: italic;\n}\n\n.poster__credit {\n  position: absolute;\n  left: var(--poster-pad);\n  right: var(--poster-pad);\n  bottom: var(--space-2);\n  font-family: var(--font-mono);\n  font-size: var(--mono-size-sm);\n  text-transform: uppercase;\n  letter-spacing: 0.06em;\n}\n\n.poster__image {\n  position: absolute;\n  top: var(--poster-pad);\n  right: var(--poster-pad);\n  width: 96px;\n  height: 96px;\n  object-fit: cover;\n  border: var(--rule-1) solid var(--ink-black);\n  background: var(--paper);\n }"
    },

    "2_torn_edges_clip_path": {
      "goal": "Behind posters look cropped + torn like paste-up. Use clip-path polygons (hard edges). No noise textures. Provide 4 reusable tear polygons; keep vertex count constant per animation set.",
      "how_to_apply": [
        "Only apply torn edges to the 2–3 previous posters (not the current top poster).",
        "Use a wrapper .posterWrap that sets overflow hidden and positions each poster with translate/rotate so only edges peek.",
        "Apply clip-path to the poster element itself: .poster--torn { clip-path: var(--tear-a); }",
        "To make them peek: offset each behind poster by translate(-18px, 14px) etc and reduce scale slightly (0.985, 0.97)."
      ],
      "clip_path_polygons": {
        "--tear-a": "polygon(0% 0%, 100% 0%, 100% 86%, 96% 88%, 92% 86%, 88% 90%, 84% 87%, 80% 91%, 76% 88%, 72% 92%, 68% 89%, 64% 93%, 60% 90%, 56% 94%, 52% 91%, 48% 95%, 44% 92%, 40% 96%, 36% 93%, 32% 97%, 28% 94%, 24% 98%, 20% 95%, 16% 99%, 12% 96%, 8% 100%, 4% 97%, 0% 99%)",
        "--tear-b": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 14%, 3% 12%, 6% 15%, 9% 11%, 12% 16%, 15% 12%, 18% 17%, 21% 13%, 24% 18%, 27% 14%, 30% 19%, 33% 15%, 36% 20%, 39% 16%, 42% 21%, 45% 17%, 48% 22%, 51% 18%, 54% 23%, 57% 19%, 60% 24%, 63% 20%, 66% 25%, 69% 21%, 72% 26%, 75% 22%, 78% 27%, 81% 23%, 84% 28%, 87% 24%, 90% 29%, 93% 25%, 96% 30%, 100% 28%, 100% 0%)",
        "--tear-c": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, 0% 92%, 4% 94%, 8% 91%, 12% 95%, 16% 92%, 20% 96%, 24% 93%, 28% 97%, 32% 94%, 36% 98%, 40% 95%, 44% 99%, 48% 96%, 52% 100%, 56% 97%, 60% 99%, 64% 96%, 68% 98%, 72% 95%, 76% 97%, 80% 94%, 84% 96%, 88% 93%, 92% 95%, 96% 92%, 100% 94%, 100% 0%)",
        "--tear-d": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, 0% 100%, 0% 78%, 2% 80%, 5% 77%, 8% 81%, 11% 76%, 14% 82%, 17% 75%, 20% 83%, 23% 74%, 26% 84%, 29% 73%, 32% 85%, 35% 72%, 38% 86%, 41% 71%, 44% 87%, 47% 70%, 50% 88%, 53% 71%, 56% 86%, 59% 72%, 62% 85%, 65% 73%, 68% 84%, 71% 74%, 74% 83%, 77% 75%, 80% 82%, 83% 76%, 86% 81%, 89% 77%, 92% 80%, 95% 78%, 98% 79%, 100% 77%, 100% 100%)"
      },
      "cropping_peek_recipe": "/* Stack wrapper */\n.posterStack { position: relative; width: min(var(--poster-w-desktop), var(--poster-w-max)); max-width: 100%; }\n\n.posterLayer { position: absolute; inset: 0; }\n.posterLayer--back3 { transform: translate(-26px, 22px) rotate(var(--rot3)); }\n.posterLayer--back2 { transform: translate(-14px, 12px) rotate(var(--rot2)); }\n.posterLayer--back1 { transform: translate(-6px, 6px) rotate(var(--rot1)); }\n.posterLayer--top { position: relative; transform: rotate(var(--rot0)); }\n\n.poster--torn { clip-path: var(--tear); }\n\n/* Ensure behind posters are visually cropped by the top poster footprint */\n.posterStack::before {\n  content: '';\n  position: absolute;\n  inset: 0;\n  pointer-events: none;\n  /* no shadow, no gradient; this is just a stacking context helper */\n}"
    },

    "3_riso_misregistration": {
      "principle": "Two layers: ink plate (background color or ink text) is offset by 1–2px; type plate is crisp black. No blur, no noise.",
      "dom": [
        ".poster__ink (absolute fill) = the ink plate",
        ".poster__type (relative) = the type plate"
      ],
      "css": "/* Ink plate */\n.poster__ink {\n  position: absolute;\n  inset: 0;\n  transform: translate(var(--misreg), var(--misreg-y));\n  z-index: 1;\n}\n\n/* Mode A: ink background, black type */\n.poster--ink-bg {\n  background: var(--paper);\n}\n.poster--ink-bg.poster--tomato .poster__ink { background: var(--ink-tomato); }\n.poster--ink-bg.poster--mustard .poster__ink { background: var(--ink-mustard); }\n.poster--ink-bg.poster--teal .poster__ink { background: var(--ink-teal); }\n\n.poster--ink-bg .poster__type { color: var(--ink-black); }\n\n/* Mode B: black background, ink type */\n.poster--black-bg {\n  background: var(--paper);\n}\n.poster--black-bg .poster__ink { background: var(--ink-black); }\n\n.poster--black-bg.poster--tomato .poster__type { color: var(--ink-tomato); }\n.poster--black-bg.poster--mustard .poster__type { color: var(--ink-mustard); }\n.poster--black-bg.poster--teal .poster__type { color: var(--ink-teal); }\n\n/* Ensure borders remain crisp black (type plate world) */\n.poster { border-color: var(--ink-black); }",
      "adjacent_ink_rule": "Enforce in JS when selecting next ink: never choose same ink as immediate previous poster. Also avoid same ink for the 2–3 visible behind posters if you want stricter adjacency."
    },

    "4_rubber_stamp_component": {
      "dom": "<div className=\"stamp stamp--dethroned\" data-testid=\"poster-stamp\">\n  <div className=\"stamp__inner\">\n    <div className=\"stamp__line1\">DETHRONED · HELD 4M 12S</div>\n    <div className=\"stamp__line2\">AI HECKLE HERE</div>\n  </div>\n</div>",
      "css": "/* Stamp: hollow double-line box, tomato ink, rotated -8deg */\n.stamp {\n  position: absolute;\n  left: 10%;\n  top: 58%;\n  transform: rotate(-8deg);\n  color: var(--ink-tomato);\n  font-family: var(--font-mono);\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n  width: min(78%, 520px);\n  pointer-events: none;\n}\n\n.stamp__inner {\n  position: relative;\n  padding: 10px 12px;\n  border: 2px solid currentColor;\n}\n\n/* inner line for double-box */\n.stamp__inner::before {\n  content: '';\n  position: absolute;\n  inset: 4px;\n  border: 2px solid currentColor;\n}\n\n.stamp__line1 {\n  font-size: 12px;\n  line-height: 1.15;\n}\n\n.stamp__line2 {\n  margin-top: 6px;\n  font-size: 12px;\n  line-height: 1.15;\n}\n\n/* Uneven ink WITHOUT noise textures: layered opacity variance via repeating-linear-gradient mask */\n.stamp {\n  opacity: 0.92;\n}\n\n@supports (mask-image: repeating-linear-gradient(#000, #000)) {\n  .stamp {\n    -webkit-mask-image: repeating-linear-gradient(\n      0deg,\n      rgba(0,0,0,0.92) 0px,\n      rgba(0,0,0,0.92) 2px,\n      rgba(0,0,0,0.72) 3px,\n      rgba(0,0,0,0.92) 5px\n    );\n    mask-image: repeating-linear-gradient(\n      0deg,\n      rgba(0,0,0,0.92) 0px,\n      rgba(0,0,0,0.92) 2px,\n      rgba(0,0,0,0.72) 3px,\n      rgba(0,0,0,0.92) 5px\n    );\n  }\n}\n\n/* Fallback: slight per-line opacity differences */\n.stamp__line1 { opacity: 0.92; }\n.stamp__line2 { opacity: 0.82; }",
      "final_holder_stamp_variant": {
        "text": "FINAL HOLDER",
        "ink": "var(--ink-teal)",
        "placement": "Top poster upper third; keep rotation -8deg"
      }
    },

    "5_one_transition_takeover": {
      "sequence": [
        "New poster drops from above, lands with 60ms overshoot, settles by ~0.8s.",
        "300ms after settle begins, previous poster corner tear animates (4-frame mask swap).",
        "Stamp slams on (no blur) and persists.",
        "Total ~1.5s. prefers-reduced-motion: instant cut."
      ],
      "keyframes_css": "/* Drop-in: use translateY + slight scale; no easing elsewhere */\n@keyframes posterDrop {\n  0% { transform: translateY(-120vh) rotate(var(--rot0)) scale(1); }\n  78% { transform: translateY(0) rotate(var(--rot0)) scale(1); }\n  85% { transform: translateY(10px) rotate(var(--rot0)) scale(1); } /* overshoot ~60ms window */\n  100% { transform: translateY(0) rotate(var(--rot0)) scale(1); }\n}\n\n/* Stamp slam: comes from slightly above, hits, tiny rebound */\n@keyframes stampSlam {\n  0% { transform: translateY(-18px) rotate(-8deg) scale(1.02); opacity: 0; }\n  60% { transform: translateY(0) rotate(-8deg) scale(1); opacity: 0.92; }\n  78% { transform: translateY(2px) rotate(-8deg) scale(0.995); opacity: 0.92; }\n  100% { transform: translateY(0) rotate(-8deg) scale(1); opacity: 0.92; }\n}\n\n/* 4-frame tear: swap clip-path variables (hard cut) */\n@keyframes tearFrames {\n  0% { clip-path: var(--tear-f1); }\n  33% { clip-path: var(--tear-f2); }\n  66% { clip-path: var(--tear-f3); }\n  100% { clip-path: var(--tear-f4); }\n}\n\n/* Apply only during takeover */\n.poster--enter {\n  animation: posterDrop 0.8s cubic-bezier(0.2, 0.9, 0.2, 1) both;\n}\n\n.poster--being-covered {\n  animation: tearFrames 0.22s steps(1, end) both;\n  animation-delay: 1.1s; /* 0.8s drop + 0.3s delay */\n}\n\n.stamp--slam {\n  animation: stampSlam 0.28s steps(1, end) both;\n  animation-delay: 1.1s;\n}\n\n@media (prefers-reduced-motion: reduce) {\n  .poster--enter, .poster--being-covered, .stamp--slam {\n    animation: none !important;\n  }\n}",
      "tear_frame_polygons": {
        "--tear-f1": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, 0% 100%, 0% 92%, 6% 94%, 12% 91%, 18% 95%, 24% 92%, 30% 96%, 36% 93%, 42% 97%, 48% 94%, 54% 98%, 60% 95%, 66% 99%, 72% 96%, 78% 100%, 84% 97%, 90% 99%, 96% 96%, 100% 98%, 100% 0%)",
        "--tear-f2": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, 0% 100%, 0% 90%, 6% 93%, 12% 89%, 18% 94%, 24% 90%, 30% 95%, 36% 91%, 42% 96%, 48% 92%, 54% 97%, 60% 93%, 66% 98%, 72% 94%, 78% 99%, 84% 95%, 90% 98%, 96% 94%, 100% 97%, 100% 0%)",
        "--tear-f3": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, 0% 100%, 0% 88%, 6% 92%, 12% 87%, 18% 93%, 24% 88%, 30% 94%, 36% 89%, 42% 95%, 48% 90%, 54% 96%, 60% 91%, 66% 97%, 72% 92%, 78% 98%, 84% 93%, 90% 97%, 96% 92%, 100% 96%, 100% 0%)",
        "--tear-f4": "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%, 0% 100%, 0% 86%, 6% 91%, 12% 85%, 18% 92%, 24% 86%, 30% 93%, 36% 87%, 42% 94%, 48% 88%, 54% 95%, 60% 89%, 66% 96%, 72% 90%, 78% 97%, 84% 91%, 90% 96%, 96% 90%, 100% 95%, 100% 0%)"
      }
    },

    "6_autofit_display_type": {
      "rules": [
        "If message length ≤ 30: render ALL CAPS, maximize size to fit (single block), allow up to 3 lines if needed but aim huge.",
        "If > 30: sentence case, max 4 lines, auto-fit down.",
        "Always keep within poster safe area (avoid image top-right)."
      ],
      "css_first": "/* Container query sizing baseline */\n.poster__message[data-variant='short'] {\n  text-transform: uppercase;\n  font-size: var(--display-max);\n  max-width: calc(100% - 112px); /* reserve for 96px image + padding */\n}\n\n.poster__message[data-variant='long'] {\n  text-transform: none;\n  font-size: var(--display-mid);\n  display: -webkit-box;\n  -webkit-line-clamp: 4;\n  -webkit-box-orient: vertical;\n  overflow: hidden;\n  max-width: calc(100% - 112px);\n}",
      "js_binary_search_fallback": {
        "notes": "Use ResizeObserver on poster container. Binary search font-size so scrollHeight <= allowedHeight and line count <= 4. Keep it deterministic for OG match.",
        "pseudo": "function fitMessage(el, {min=22, max=110, maxLines=4}) {\n  const container = el.closest('.poster__type');\n  const allowed = container.clientHeight * 0.62; // tune to match Pillow renderer\n  let lo=min, hi=max;\n  while (lo <= hi) {\n    const mid = Math.floor((lo+hi)/2);\n    el.style.fontSize = mid + 'px';\n    const ok = el.scrollHeight <= allowed;\n    if (ok) lo = mid + 1; else hi = mid - 1;\n  }\n  el.style.fontSize = hi + 'px';\n}\n\n// call on mount + on resize\nconst ro = new ResizeObserver(() => fitMessage(msgEl, opts));\nro.observe(container);"
      }
    },

    "7_black_rail_layout": {
      "rail_dom": "<footer className=\"rail\" data-testid=\"black-rail\">\n  <div className=\"rail__left\">\n    <span className=\"rail__held\" data-testid=\"rail-held\">HELD 04:12</span>\n    <span className=\"rail__dot\" aria-hidden=\"true\">·</span>\n    <span className=\"rail__price\" data-testid=\"rail-current-price\">$6.50</span>\n    <span className=\"rail__dot\" aria-hidden=\"true\">·</span>\n    <button className=\"rail__cta\" data-ink=\"tomato\" data-testid=\"rail-takeover-button\">PASTE OVER IT FOR <span className=\"rail__ctaPrice\">$7.00</span></button>\n  </div>\n  <div className=\"rail__right\" data-testid=\"rail-countdown\">47:12:09</div>\n</footer>",
      "css": "/* Rail */\n.rail {\n  background: var(--ink-black);\n  color: var(--paper);\n  height: var(--rail-height-sm);\n  display: grid;\n  grid-template-columns: 1fr auto;\n  align-items: center;\n  padding: 0 var(--space-4);\n  gap: var(--space-3);\n  font-family: var(--font-mono);\n  font-size: var(--mono-size);\n  line-height: 1;\n}\n\n.rail__left {\n  min-width: 0;\n  display: flex;\n  align-items: baseline;\n  gap: 10px;\n  white-space: nowrap;\n  overflow: hidden;\n  text-overflow: ellipsis;\n}\n\n.rail__cta {\n  white-space: nowrap;\n  text-decoration: underline;\n  text-decoration-thickness: 2px;\n  text-underline-offset: 3px;\n}\n\n/* Price in current poster ink */\n.rail__ctaPrice { color: var(--ink-tomato); }\n.rail__cta[data-ink='mustard'] .rail__ctaPrice { color: var(--ink-mustard); }\n.rail__cta[data-ink='teal'] .rail__ctaPrice { color: var(--ink-teal); }\n\n.rail__right {\n  font-variant-numeric: tabular-nums;\n  white-space: nowrap;\n}\n\n/* Mobile sticky bottom */\n@media (max-width: 640px) {\n  .rail {\n    position: sticky;\n    bottom: 0;\n    height: var(--rail-height-sm);\n    padding: 0 var(--space-3);\n  }\n  .rail__left {\n    gap: 8px;\n  }\n}",
      "pending_state": {
        "copy": "PENDING · [name] · $7.00",
        "treatment": "Stencil-like mono caps on rail left; keep rail black; price still in ink color; disable CTA button (still a button element)"
      },
      "no_wrap_strategy_360px": "Use grid-template-columns: 1fr auto; rail__left overflow hidden; rail__right fixed. Ensure CTA text short; if needed, hide 'PASTE OVER IT FOR' on very small widths via CSS and keep only price as button label (still matches spec: price text IS the takeover button)."
    },

    "8_hall_of_fallen_masonry": {
      "goal": "Dense paste-up with overlaps, varied rotations, torn edges, no gutters that read as a grid; still scrolls with 200+ posters.",
      "approach": [
        "Use CSS columns for flow density (column-count) + absolutely-positioned overlaps inside each column item.",
        "Each poster item is a relatively positioned wrapper with negative margins to overlap neighbors.",
        "Randomize rotation per poster deterministically from id hash (e.g., -2.5deg..2.5deg) and slight translate.",
        "Virtualize list for performance (react-window) OR paginate/infinite load; keep DOM under ~80 posters at once."
      ],
      "css": "/* Masonry via columns */\n.fallen {\n  padding: var(--space-4);\n}\n\n.fallen__masonry {\n  column-count: 2;\n  column-gap: 0;\n}\n\n@media (min-width: 900px) {\n  .fallen__masonry { column-count: 3; }\n}\n\n@media (min-width: 1200px) {\n  .fallen__masonry { column-count: 4; }\n}\n\n.fallen__item {\n  break-inside: avoid;\n  margin: 0 0 -28px; /* overlap */\n  position: relative;\n}\n\n.fallen__item .poster {\n  width: 100%;\n  transform: rotate(var(--rot, 0deg)) translate(var(--tx, 0px), var(--ty, 0px));\n}\n\n/* Obituary: mono italic under poster, tight */\n.fallen__obituary {\n  font-family: var(--font-mono);\n  font-size: var(--mono-size-sm);\n  font-style: italic;\n  margin: 6px 0 18px;\n  max-width: 52ch;\n}",
      "controls": {
        "sort_toggle": "Mono-only, square checkboxes/radios; no pills. Use <fieldset> with legend.",
        "data_testids": [
          "fallen-sort-select",
          "fallen-toggle-price",
          "fallen-toggle-reign"
        ]
      }
    },

    "9_take_sheet_and_admin": {
      "take_sheet_world": "Print shop order form: ruled lines, hard borders, mono labels, no rounded corners, no shadows.",
      "take_sheet_css": "/* Sheet */\n.sheet {\n  padding: var(--space-4);\n  max-width: 720px;\n}\n\n.sheet__panel {\n  border: var(--rule-2) solid var(--ink-black);\n  padding: var(--space-4);\n  background: transparent;\n}\n\n.sheet label {\n  display: block;\n  font-family: var(--font-mono);\n  font-size: var(--mono-size-sm);\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n  margin: 0 0 6px;\n}\n\n.sheet input, .sheet textarea {\n  width: 100%;\n  border: var(--rule-2) solid var(--ink-black);\n  border-radius: 0;\n  background: transparent;\n  padding: 10px 10px;\n  font-family: var(--font-mono);\n  font-size: var(--mono-size);\n  line-height: 1.25;\n}\n\n.sheet textarea {\n  min-height: 120px;\n  resize: vertical;\n}\n\n.sheet input::placeholder, .sheet textarea::placeholder {\n  color: rgba(20,20,20,0.65);\n}\n\n.sheet__error {\n  margin-top: 8px;\n  border-left: 4px solid var(--ink-black);\n  padding-left: 10px;\n  font-family: var(--font-mono);\n  font-size: var(--mono-size-sm);\n}\n\n.sheet__submit {\n  margin-top: var(--space-4);\n  border: var(--rule-2) solid var(--ink-black);\n  padding: 12px 14px;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n  background: var(--ink-black);\n  color: var(--paper);\n}\n\n.sheet__submit:active {\n  transform: translate(1px, 1px);\n}\n\n/* No hover animations; only state changes allowed */\n.sheet__submit:hover {\n  background: var(--ink-black);\n}",
      "take_sheet_copy_fixed": {
        "placeholder": "Say something. It won't last.",
        "min_bid_error": "Someone already paid more than that.",
        "moderation_block": "The wall has standards. Barely, but it has them."
      },
      "admin_treatment": {
        "tone": "Functional, ugly-on-purpose, mono-only, like a site foreman's clipboard.",
        "css": "/* Admin */\n.admin {\n  padding: var(--space-4);\n  font-family: var(--font-mono);\n}\n\n.admin h1, .admin h2 {\n  font-family: var(--font-mono);\n  font-size: 14px;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n  margin: 0 0 12px;\n}\n\n.admin__table {\n  width: 100%;\n  border-collapse: collapse;\n}\n\n.admin__table th, .admin__table td {\n  border: 1px solid var(--ink-black);\n  padding: 8px;\n  vertical-align: top;\n}\n\n.admin__btn {\n  border: 1px solid var(--ink-black);\n  padding: 6px 8px;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n}\n\n.admin__btn:active { transform: translate(1px, 1px); }"
      }
    },

    "10_states_focus_hover_final": {
      "focus_states": [
        "Use hard outline only: 2px solid black with 2px offset.",
        "No glow, no ring, no box-shadow focus.",
        "For rail CTA: underline thickens on focus-visible (not on hover)."
      ],
      "hover_active": {
        "hover": "No hover animations anywhere. At most: underline thickness change on links/buttons (instant).",
        "active": "Physical press: translate(1px,1px) on form submit/admin buttons only. Do not apply to poster or rail."
      },
      "frozen_final_state": {
        "copy": "The Last Billboard. Held by [name]. Forever, or until the server bill.",
        "treatment": [
          "Disable takeover CTA (still render as button but disabled).",
          "Stamp top poster with FINAL HOLDER in teal.",
          "Rail still black; countdown replaced with 00:00:00 or 'FROZEN'."
        ]
      }
    }
  },

  "image_urls": {
    "note": "No decorative images. Only optional user-provided 96px square image inside poster top-right. Do not fetch stock imagery."
  },

  "instructions_to_main_agent": [
    "Replace CRA starter App.css styles; ensure html/body background is #F3E7D3 to avoid white flash.",
    "Load Google Fonts: Archivo Black + JetBrains Mono only.",
    "Do not use shadcn Button/Card/Toast. No toasts. No icons. No rounded corners. No gradients. No extra shadows.",
    "Implement Poster as two layers (ink plate + type plate) with 2px misregistration on ink plate only.",
    "Only top poster gets box-shadow: 6px 6px 0 #141414.",
    "Implement torn edges via clip-path polygons for behind posters only; use provided polygons and deterministic selection.",
    "Implement takeover animation exactly once: posterDrop + tearFrames + stampSlam; honor prefers-reduced-motion.",
    "All interactive and key informational elements must include data-testid attributes (kebab-case).",
    "Ensure /m/[id] matches server OG renderer composition (rotation, padding ratios, stamp placement, rail)."
  ],

  "general_ui_ux_design_guidelines_appendix": "<General UI UX Design Guidelines>  \n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
