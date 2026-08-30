"""Server-side render of the wall, so the OG card is the live page.

Same palette, same fonts, same geometry math as the React wall.
No gradients, no blur, no rounded corners. One hard 6px offset under the poster.
"""
import io
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageChops

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
DISPLAY = os.path.join(ASSETS, "ArchivoBlack-Regular.ttf")
MONO = os.path.join(ASSETS, "JetBrainsMono-Regular.ttf")
MONO_BOLD = os.path.join(ASSETS, "JetBrainsMono-Bold.ttf")
MONO_ITALIC = os.path.join(ASSETS, "JetBrainsMono-Italic.ttf")

CREAM = (243, 231, 211)
BLACK = (20, 20, 20)
INKS = {
    "tomato": (230, 63, 30),
    "mustard": (240, 180, 41),
    "teal": (30, 110, 120),
}
TOMATO = INKS["tomato"]
TEAL = INKS["teal"]

_font_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def _text_w(d, s, f):
    return d.textlength(s, font=f)


def _wrap(d, text, f, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            trial = (cur + " " + word).strip()
            if _text_w(d, trial, f) <= max_w or not cur:
                if _text_w(d, trial, f) > max_w and not cur:
                    # single word too long: hard break it
                    chunk = ""
                    for ch in word:
                        if _text_w(d, chunk + ch, f) <= max_w or not chunk:
                            chunk += ch
                        else:
                            lines.append(chunk)
                            chunk = ch
                    cur = chunk
                else:
                    cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def fit_display(d, text, max_w, max_h, max_lines, hi=190, lo=16):
    """Auto-fit display type. <=30 chars goes all caps and enormous."""
    caps = len(text.strip()) <= 30
    body = text.upper() if caps else text
    size = hi
    while size > lo:
        f = font(DISPLAY, size)
        lines = _wrap(d, body, f, max_w)
        lh = int(size * 1.02)
        if len(lines) <= (1 if caps and len(text.strip()) <= 14 else max_lines) and len(lines) * lh <= max_h:
            widest = max((_text_w(d, l, f) for l in lines), default=0)
            if widest <= max_w:
                return lines, f, lh
        size -= 2
    f = font(DISPLAY, lo)
    return _wrap(d, body, f, max_w), f, int(lo * 1.05)


def _uneven_ink(layer, seed=0):
    """Rubber-stamp unevenness through coarse alpha variance. No blur."""
    rnd = random.Random(seed)
    w, h = layer.size
    sw, sh = max(2, w // 14), max(2, h // 8)
    noise = Image.new("L", (sw, sh))
    noise.putdata([rnd.choice([255, 255, 240, 215, 190, 255, 165]) for _ in range(sw * sh)])
    noise = noise.resize((w, h), Image.NEAREST)
    a = layer.split()[3]
    layer.putalpha(ImageChops.multiply(a, noise))
    return layer


def stamp_image(line1, line2, max_w, color=TOMATO, angle=-8, seed=0, scale=1.0):
    f1 = font(MONO_BOLD, int(19 * scale))
    f2 = font(MONO_BOLD, int(15 * scale))
    pad = int(16 * scale)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    inner_w = max_w - pad * 2
    l1 = _wrap(probe, (line1 or "").upper(), f1, inner_w)
    l2 = _wrap(probe, (line2 or "").upper(), f2, inner_w) if line2 else []
    lh1, lh2 = int(24 * scale), int(19 * scale)
    content_h = len(l1) * lh1 + (int(8 * scale) + len(l2) * lh2 if l2 else 0)
    w = max_w
    h = content_h + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(2, int(3 * scale))
    d.rectangle([0, 0, w - 1, h - 1], outline=color + (255,), width=lw)
    ins = int(6 * scale)
    d.rectangle([ins, ins, w - 1 - ins, h - 1 - ins], outline=color + (255,), width=max(1, int(1.5 * scale)))
    y = pad
    for ln in l1:
        d.text((pad, y), ln, font=f1, fill=color + (255,))
        y += lh1
    if l2:
        y += int(8 * scale)
        for ln in l2:
            d.text((pad, y), ln, font=f2, fill=color + (255,))
            y += lh2
    img = _uneven_ink(img, seed)
    return img.rotate(angle, expand=True, resample=Image.BICUBIC)


def _fetch_square(url, size=96):
    try:
        import httpx

        r = httpx.get(url, timeout=4.0, follow_redirects=True)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        side = min(im.size)
        left = (im.width - side) // 2
        top = (im.height - side) // 2
        im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
        out = Image.new("RGBA", (size + 2, size + 2), BLACK + (255,))
        out.paste(im, (1, 1))
        return out
    except Exception:
        return None


def _place(st, w, h, fx, fy, margin=10):
    """Keep the stamp on the paper it was slammed onto."""
    x = min(int(w * fx), max(0, w - st.width - margin))
    y = min(int(h * fy), max(0, h - st.height - margin))
    return (max(margin, x), max(margin, y))


def _lum(rgb):
    def f(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2])


def _readable(desired, bg):
    """A stamp inked too close in tone to the poster it landed on is no stamp at all.
    Tomato on mustard is a real riso overprint. Tomato on teal is mud."""
    if abs(_lum(desired) - _lum(bg)) >= 0.12:
        return desired
    return CREAM if _lum(bg) < 0.35 else BLACK


def poster_image(msg, w, h, scale=1.0, with_stamp=True, final=False, with_image=True):
    """Returns RGBA of size (w+6, h+6) including the single hard offset shadow."""
    ink = INKS.get(msg.get("ink") or "tomato", TOMATO)
    mode = msg.get("mode") or "ink_bg"
    bg = ink if mode == "ink_bg" else BLACK
    fg = BLACK if mode == "ink_bg" else ink

    out = Image.new("RGBA", (w + 6, h + 6), (0, 0, 0, 0))
    ImageDraw.Draw(out).rectangle([6, 6, 6 + w - 1, 6 + h - 1], fill=BLACK + (255,))

    # two plates, the ink one misregistered by 2px: the riso tell
    rect = Image.new("RGBA", (w, h), bg + (255,))
    type_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(type_layer)

    pad = int(34 * scale)
    credit_h = int(30 * scale)
    stamped = bool(final or (with_stamp and msg.get("ended_at") and msg.get("heckle")))
    ad_h = int(26 * scale) if (msg.get("ad_line") and not stamped) else 0
    box_w = w - pad * 2
    box_h = h - pad * 2 - credit_h - ad_h
    if stamped:
        # once a stamp has landed on it, the message gives up the lower third
        box_h = int(box_h * 0.62)
    if with_image and msg.get("image_url"):
        box_w -= int(112 * scale)

    lines, f, lh = fit_display(d, msg.get("text", ""), box_w, box_h, 4,
                              hi=int(190 * scale), lo=max(10, int(14 * scale)))
    y = pad + max(0, (box_h - len(lines) * lh) // 2)
    for ln in lines:
        d.text((pad, y), ln, font=f, fill=fg + (255,))
        y += lh

    if msg.get("ad_line") and not stamped:
        fi = font(MONO_ITALIC, max(9, int(15 * scale)))
        ad = msg["ad_line"]
        while d.textlength(ad, font=fi) > box_w and len(ad) > 8:
            ad = ad[:-2]
        d.text((pad, h - pad - credit_h - int(20 * scale)), ad, font=fi, fill=fg + (215,))

    fm = font(MONO, max(9, int(14 * scale)))
    credit = (msg.get("name") or "anonymous").upper()
    d.text((pad, h - pad - int(6 * scale)), credit, font=fm, fill=fg + (235,))

    off = (2, 1)
    if mode == "ink_bg":
        out.paste(rect, off)
        out.alpha_composite(type_layer, (0, 0))
    else:
        out.paste(rect, (0, 0))
        out.alpha_composite(type_layer, off)

    if with_image and msg.get("image_url"):
        sq = _fetch_square(msg["image_url"], int(96 * scale))
        if sq:
            out.alpha_composite(sq, (w - pad - sq.width, pad))

    if final:
        st = stamp_image("FINAL HOLDER", "The wall is closed.", int(min(w - pad * 2, 420 * scale)),
                         color=_readable(TEAL, bg), angle=-8, seed=7, scale=scale)
        out.alpha_composite(st, _place(st, w, h, 0.12, 0.62))
    elif with_stamp and msg.get("ended_at") and msg.get("heckle"):
        l1 = "DETHRONED \u00b7 HELD %s" % (msg.get("reign_label") or "")
        st = stamp_image(l1, msg.get("heckle") or "", int(min(w - pad * 2, 520 * scale)),
                         color=_readable(TOMATO, bg), angle=-8, seed=len(msg.get("id", "x")), scale=scale)
        out.alpha_composite(st, _place(st, w, h, 0.12, 0.60))

    return out


def render_og(msg, rail_text, final=False, width=1200, height=630):
    """The share unit. Cream wall, poster at its rotation, stamp, black rail."""
    canvas = Image.new("RGB", (width, height), CREAM)
    rail_h = 66
    wall_h = height - rail_h

    pw, ph = 760, 400
    scale = 1.0
    poster = poster_image(msg, pw, ph, scale=scale, final=final)
    rot = float(msg.get("rotation") or 0)
    poster = poster.rotate(rot, expand=True, resample=Image.BICUBIC)
    px = (width - poster.width) // 2
    py = (wall_h - poster.height) // 2
    canvas.paste(poster, (px, py), poster)

    d = ImageDraw.Draw(canvas)
    d.rectangle([0, wall_h, width, height], fill=BLACK)
    ink = INKS.get(msg.get("ink") or "tomato", TOMATO)

    # rail_text may be a plain string or a list of (text, "cream"|"ink") segments,
    # so the price can carry the current poster's ink exactly like the live rail.
    segments = rail_text if isinstance(rail_text, (list, tuple)) else [(str(rail_text), "cream")]
    flat = "".join(s[0] for s in segments)
    fm = font(MONO_BOLD, 20)
    if d.textlength(flat, font=fm) > width - 60:
        fm = font(MONO_BOLD, 16)
    total = d.textlength(flat, font=fm)
    x = (width - total) / 2
    y = wall_h + (rail_h - 26) / 2
    for txt, kind in segments:
        d.text((x, y), txt, font=fm, fill=(ink if kind == "ink" else CREAM))
        x += d.textlength(txt, font=fm)
    d.rectangle([0, wall_h, width, wall_h + 4], fill=ink)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
