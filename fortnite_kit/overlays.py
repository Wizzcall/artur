"""Fortnite-style pseudo-3D overlay elements, modern look (PIL RGBA).

Design language: chunky extruded display type, dark ink outlines, glossy
gradients, frosted-glass cards with neon edge glow, rounded corners.
Palette = Fortnite rarities (legendary gold, epic purple, rare blue).
Every function returns an RGBA image to composite over a video frame.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_MAIN = os.path.join(HERE, "fonts", "LuckiestGuy-Regular.ttf")
FONT_ALT = os.path.join(HERE, "fonts", "Bangers-Regular.ttf")

YELLOW = (255, 220, 40)
GOLD = (255, 150, 0)
BLUE = (40, 150, 255)
CYAN = (70, 235, 255)
PURPLE = (160, 70, 255)
MAGENTA = (240, 80, 255)
PINK = (255, 60, 170)
GREEN = (70, 240, 120)
RED = (255, 70, 70)
WHITE = (255, 255, 255)
INK = (14, 10, 38)

RARITY = {
    "legendary": (GOLD, YELLOW),
    "epic": (PURPLE, MAGENTA),
    "rare": (BLUE, CYAN),
    "uncommon": ((30, 170, 80), GREEN),
}


def font(size, alt=False):
    return ImageFont.truetype(FONT_ALT if alt else FONT_MAIN, size)


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size, top, bottom, horizontal=False):
    w, h = size
    g = Image.new("RGBA", size)
    d = ImageDraw.Draw(g)
    n = w if horizontal else h
    for i in range(n):
        c = _mix(top, bottom, i / max(1, n - 1)) + (255,)
        d.line([(i, 0), (i, h)] if horizontal else [(0, i), (w, i)], fill=c)
    return g


def _pad(img, m):
    out = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    out.alpha_composite(img, (m, m))
    return out


def glow(img, color, radius=14, strength=1.0, margin=40):
    """Neon glow behind the opaque parts of img."""
    img = _pad(img, margin)
    a = img.split()[3].filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: min(255, int(v * 1.6 * strength)))
    g = Image.new("RGBA", img.size, color + (0,))
    g.putalpha(a)
    g.alpha_composite(img)
    return g


def shadow(img, offset=(8, 12), blur=10, alpha=140, margin=30):
    img = _pad(img, margin)
    m = Image.new("L", img.size, 0)
    m.paste(img.split()[3], offset)
    m = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha // 255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.putalpha(m)
    out.alpha_composite(img)
    return out


def _mask_paste(dst, src, mask_fn):
    m = Image.new("L", dst.size, 0)
    mask_fn(ImageDraw.Draw(m))
    dst.paste(src, (0, 0), m)


# ----------------------------------------------------------------- text
def text_3d(text, size=140, top=YELLOW, bottom=GOLD, depth=None, outline=None,
            alt=False, tilt=0.0, glow_color=None):
    """Extruded 3D text: gradient face, dark extrusion, ink outline, gloss band,
    optional neon glow."""
    f = font(size, alt)
    depth = depth if depth is not None else max(4, size // 11)
    outline = outline if outline is not None else max(4, size // 13)
    l, t, r, b = f.getbbox(text)
    w, h = r - l + 2 * outline + depth + 20, b - t + 2 * outline + depth + 20
    ox, oy = outline + 10 - l, outline + 10 - t

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(depth, 0, -1):  # extrusion, lit from the top
        c = _mix(_shade(bottom, .28), _shade(bottom, .55), 1 - i / depth)
        d.text((ox + i * .45, oy + i), text, font=f, fill=c + (255,), stroke_width=outline, stroke_fill=INK)
    d.text((ox, oy), text, font=f, fill=INK, stroke_width=outline, stroke_fill=INK)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((ox, oy), text, font=f, fill=255)
    img.paste(_gradient((w, h), top, bottom), (0, 0), mask)
    # glossy band + thin rim light along the top edge of glyphs
    band = Image.new("L", (w, h), 0)
    ImageDraw.Draw(band).rectangle([0, 0, w, oy + (b - t) * .40], fill=90)
    img.paste(Image.new("RGBA", (w, h), WHITE + (255,)), (0, 0), ImageChops.multiply(band, mask))
    rim = ImageChops.subtract(mask, ImageChops.offset(mask, 0, max(2, size // 40)))
    img.paste(Image.new("RGBA", (w, h), WHITE + (255,)), (0, 0), rim.point(lambda v: v * 200 // 255))
    if tilt:
        img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
    if glow_color:
        img = glow(img, glow_color, radius=max(8, size // 9), strength=.8)
    return shadow(img)


# ----------------------------------------------------------------- cards
def glass_card(w, h, accent=PURPLE, accent2=MAGENTA, radius=34, skew=0, depth=14):
    """Modern frosted-glass card with gradient border, neon edge glow and depth."""
    W, H = w + skew + depth + 4, h + depth + 4

    def shape(dx=0, dy=0):
        if not skew:
            return lambda dr: dr.rounded_rectangle([dx, dy, dx + w, dy + h], radius, fill=255)
        pts = [(skew + dx, dy), (w + skew + dx, dy), (w + dx, h + dy), (dx, h + dy)]
        return lambda dr: dr.polygon(pts, fill=255)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _mask_paste(img, Image.new("RGBA", (W, H), _shade(accent, .25) + (255,)), shape(depth * .5, depth))
    # body: deep gradient + diagonal sheen
    body = _gradient((W, H), _mix(accent, accent2, .55), _mix(INK, accent, .62))
    sheen = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).polygon([(W * .05, 0), (W * .45, 0), (W * .25, H), (-W * .15, H)], fill=(255, 255, 255, 34))
    body.alpha_composite(sheen.filter(ImageFilter.GaussianBlur(6)))
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(top).rectangle([0, 0, W, h * .45], fill=(255, 255, 255, 26))
    body.alpha_composite(top)
    _mask_paste(img, body, shape())
    # gradient border
    border_full = _gradient((W, H), accent2, accent, horizontal=True)
    outer = Image.new("L", (W, H), 0); shape()(ImageDraw.Draw(outer))
    inner = outer.filter(ImageFilter.MinFilter(9))
    img.paste(border_full, (0, 0), ImageChops.subtract(outer, inner))
    ink = ImageChops.subtract(outer, outer.filter(ImageFilter.MinFilter(3)))
    img.paste(Image.new("RGBA", (W, H), INK + (255,)), (0, 0), ink)
    return glow(img, accent2, radius=16, strength=.55, margin=30)


def box_3d(text, sub=None, rarity="epic", size=64, pad=40):
    """Slanted glass panel with title + optional subtitle (spot title card)."""
    c1, c2 = RARITY.get(rarity, RARITY["epic"])
    title = text_3d(text, size, WHITE, (205, 225, 255), depth=4, outline=max(4, size // 14))
    subimg = text_3d(sub, int(size * .78), YELLOW, GOLD, depth=4, outline=4) if sub else None
    m = 30  # shadow margin inside rendered text
    tw, th = title.width - 2 * m, title.height - 2 * m
    sw, sh = (subimg.width - 2 * m, subimg.height - 2 * m) if subimg else (0, 0)
    w = max(tw, sw) + pad * 2
    h = th + sh + pad
    skew = 28
    card = glass_card(w, h, c1, c2, skew=skew)
    off = 30  # glass_card glow margin
    cx = off + (w + skew) // 2
    card.alpha_composite(title, (cx - title.width // 2, off + pad // 2 - m))
    if subimg:
        card.alpha_composite(subimg, (cx - subimg.width // 2, off + pad // 2 + th - 6 - m))
    # accent tag on the left
    d = ImageDraw.Draw(card)
    d.polygon([(off + skew - 4, off + 14), (off + skew + 10, off + 14), (off + 14, off + h - 14), (off, off + h - 14)], fill=c2)
    return shadow(card, blur=10)


# ----------------------------------------------------------------- chest
def chest_icon(size=120, open_=False):
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gold_a, gold_b = (255, 225, 90), (230, 140, 10)
    wood_a, wood_b = (175, 95, 40), (105, 52, 20)
    body = [(s*.12, s*.50), (s*.80, s*.50), (s*.80, s*.92), (s*.12, s*.92)]
    side = [(s*.80, s*.50), (s*.92, s*.42), (s*.92, s*.84), (s*.80, s*.92)]
    _mask_paste(img, _gradient((s, s), wood_a, wood_b), lambda m: m.polygon(body, fill=255))
    d.polygon(side, fill=_shade(wood_b, .8))
    d.polygon(body, outline=INK, width=max(3, s // 30)); d.polygon(side, outline=INK, width=max(3, s // 30))
    if open_:
        g = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([s*.15, s*.18, s*.88, s*.62], fill=YELLOW + (230,))
        img = Image.alpha_composite(g.filter(ImageFilter.GaussianBlur(s * .07)), img)
        d = ImageDraw.Draw(img)
        lid = [(s*.12, s*.50), (s*.80, s*.50), (s*.92, s*.12), (s*.26, s*.12)]
        d.polygon(lid, fill=wood_b, outline=INK, width=max(3, s // 30))
        for k in range(6):  # sparkle rays
            a = -math.pi * (.15 + .7 * k / 5)
            d.line([(s*.5, s*.42), (s*.5 + s*.45*math.cos(a), s*.42 + s*.45*math.sin(a))], fill=(255, 255, 200, 200), width=max(2, s // 40))
    else:
        _mask_paste(img, _gradient((s, s), wood_a, wood_b), lambda m: m.pieslice([s*.12, s*.20, s*.80, s*.78], 180, 360, fill=255))
        d.arc([s*.12, s*.20, s*.80, s*.78], 180, 360, fill=INK, width=max(3, s // 30))
        d.line([(s*.12, s*.50), (s*.80, s*.50)], fill=INK, width=max(3, s // 30))
    for x in (.20, .64):
        _mask_paste(img, _gradient((s, s), gold_a, gold_b), lambda m, x=x: m.rectangle([s*x, s*.50, s*(x+.08), s*.92], fill=255))
        d.rectangle([s*x, s*.50, s*(x+.08), s*.92], outline=INK, width=max(2, s // 45))
    _mask_paste(img, _gradient((s, s), gold_a, gold_b), lambda m: m.rounded_rectangle([s*.38, s*.52, s*.54, s*.70], s//30, fill=255))
    d.rounded_rectangle([s*.38, s*.52, s*.54, s*.70], s // 30, outline=INK, width=max(2, s // 45))
    return img


def chest_counter(count, label="COFFRES", pop=0.0):
    """Chest counter card. pop: 0..1 progress of the increment animation
    (chest opens, number bounces, '+1' floats up)."""
    w, h = 430, 150
    card = glass_card(w, h, PURPLE, MAGENTA, radius=36)
    off = 30
    card.alpha_composite(chest_icon(132, open_=0 < pop < 1), (off + 6, off + 6))
    lab = text_3d(label, 38, WHITE, (215, 210, 255), depth=2, outline=4, alt=True)
    card.alpha_composite(lab, (off + 140 - 30, off + 4 - 30))
    scale = 1 + .4 * math.sin(math.pi * pop) if 0 < pop < 1 else 1
    num = text_3d(str(count), int(92 * scale), YELLOW, GOLD, glow_color=GOLD if 0 < pop < 1 else None)
    cx, cy = off + 320, off + 92
    card.alpha_composite(num, (int(cx - num.width / 2), int(cy - num.height / 2)))
    if 0 < pop < 1:
        plus = text_3d("+1", 46, GREEN, (20, 170, 70), depth=3, outline=4)
        alpha = max(0.0, 1 - pop ** 3)
        plus.putalpha(plus.split()[3].point(lambda v: int(v * alpha)))
        card.alpha_composite(plus, (off + w - 110, int(off - 55 - 50 * pop)))
    return shadow(card, blur=10)


# ----------------------------------------------------------------- timers
def circular_timer(remaining, total=210.0, size=230):
    """Neon circular countdown (3:30 default), colour shifts green->yellow->red."""
    S = size
    frac = max(0.0, min(1.0, remaining / total))
    col = GREEN if frac > .5 else (YELLOW if frac > .2 else RED)
    img = Image.new("RGBA", (S + 20, S + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 22, S + 10, S + 22], fill=INK)                       # depth
    _mask_paste(img, _gradient(img.size, (60, 50, 130), (22, 18, 60)),
                lambda m: m.ellipse([10, 10, S + 10, S + 10], fill=255))
    d.ellipse([10, 10, S + 10, S + 10], outline=INK, width=6)
    d.arc([18, 18, S + 2, S + 2], 200, 340, fill=(255, 255, 255, 70), width=4)  # gloss
    pad = 26
    box = [10 + pad, 10 + pad, S + 10 - pad, S + 10 - pad]
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    R = (box[2] - box[0]) / 2
    for k in range(60):  # tick marks
        a = math.radians(-90 + 6 * k)
        r1 = R + 13 if k % 5 else R + 9
        d.line([(cx + (R + 17) * math.cos(a), cy + (R + 17) * math.sin(a)),
                (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], fill=(255, 255, 255, 90), width=2)
    d.arc(box, 0, 360, fill=(55, 50, 105), width=22)
    if frac > 0:
        ring = Image.new("RGBA", img.size, (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.arc(box, -90, -90 + 360 * frac, fill=col, width=22)
        img.alpha_composite(ring.filter(ImageFilter.GaussianBlur(9)))
        img.alpha_composite(ring)
        d.arc([box[0] + 5, box[1] + 5, box[2] - 5, box[3] - 5], -90, -90 + 360 * frac,
              fill=_mix(col, WHITE, .55), width=5)
        a = math.radians(-90 + 360 * frac)
        kx, ky = cx + R * math.cos(a) - 11 * math.cos(a), cy + R * math.sin(a) - 11 * math.sin(a)
        d.ellipse([kx - 14, ky - 14, kx + 14, ky + 14], fill=WHITE, outline=INK, width=4)
    m, s = divmod(int(math.ceil(remaining)), 60)
    txt = text_3d(f"{m}:{s:02d}", int(S * .26), WHITE, (200, 220, 255), depth=4, outline=5)
    img.alpha_composite(txt, ((img.width - txt.width) // 2, (S + 20 - txt.height) // 2))
    return shadow(glow(img, col, 12, .35), blur=10)


def progress_bar(frac, width=900, label=None, segments=7):
    """Segmented neon progress bar (alternative to the circular timer)."""
    h, depth = 50, 10
    W, H = width + depth + 10, h + depth + 60
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y0 = 50
    d.rounded_rectangle([depth * .5, y0 + depth, width + depth * .5, y0 + h + depth], 25, fill=INK)
    d.rounded_rectangle([0, y0, width, y0 + h], 25, fill=(40, 34, 92), outline=INK, width=5)
    fw = int((width - 12) * max(0, min(1, frac)))
    if fw > 30:
        bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _mask_paste(bar, _gradient((W, H), YELLOW, GOLD, horizontal=False),
                    lambda m: m.rounded_rectangle([6, y0 + 6, 6 + fw, y0 + h - 6], 19, fill=255))
        img.alpha_composite(glow(bar, GOLD, 10, .5, 0))
        d.line([(20, y0 + 13), (fw - 8, y0 + 13)], fill=(255, 255, 255, 160), width=5)
    for k in range(1, segments):
        x = width * k / segments
        d.line([(x, y0 + 6), (x - 8, y0 + h - 6)], fill=INK + (170,), width=4)
    if label:
        img.alpha_composite(text_3d(label, 40, WHITE, (210, 220, 255), depth=3, outline=4, alt=True), (-10, -40))
    return shadow(img, blur=6)


# ----------------------------------------------------------------- pointers
def arrow_3d(length=260, color=YELLOW, angle=0.0):
    """Extruded 3D arrow pointing right (rotate with `angle`, degrees CCW)."""
    L, T = length, length * .42
    sh = T * .42
    pts = [(0, T/2 - sh/2), (L*.58, T/2 - sh/2), (L*.58, 0), (L, T/2), (L*.58, T), (L*.58, T/2 + sh/2), (0, T/2 + sh/2)]
    depth = int(L * .07)
    img = Image.new("RGBA", (int(L + depth + 40), int(T + depth + 40)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    P = lambda dx, dy: [(x + 20 + dx, y + 20 + dy) for x, y in pts]
    for i in range(depth, 0, -1):
        d.polygon(P(i * .5, i), fill=_shade(color, .4 + .2 * (1 - i / depth)) + (255,))
    d.polygon(P(depth * .5, depth), outline=INK, width=6)
    _mask_paste(img, _gradient(img.size, _mix(color, WHITE, .45), color), lambda m: m.polygon(P(0, 0), fill=255))
    d.polygon(P(0, 0), outline=INK, width=6)
    d.line([(28, 20 + T/2 - sh/2 + 7), (20 + L*.56, 20 + T/2 - sh/2 + 7)], fill=(255, 255, 255, 190), width=4)
    img = glow(img, color, 12, .45)
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
    return shadow(img, blur=8)


def ring_3d(radius=120, color=CYAN, t=0.0):
    """Perspective highlight ring with rising light beams, animated by t (s)."""
    pulse = 1 + .07 * math.sin(t * 2 * math.pi * 1.5)
    rx, ry = radius * pulse, radius * .42 * pulse
    W, H = int(rx * 2 + 90), int(ry * 2 + 150)
    cx, cy = W / 2, H - ry - 40
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    bd.polygon([(cx - rx, cy), (cx + rx, cy), (cx + rx * .8, cy - 110), (cx - rx * .8, cy - 110)], fill=color + (45,))
    for i in range(12):
        a = 2 * math.pi * i / 12 + t
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        bd.line([(x, y), (x, y - 50 - 35 * (.5 + .5 * math.sin(t * 5 + i)))], fill=color + (150,), width=4)
    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(4)))
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ring)
    d.ellipse([cx - rx, cy - ry + 12, cx + rx, cy + ry + 12], outline=INK, width=16)
    d.ellipse([cx - rx + 3, cy - ry + 15, cx + rx - 3, cy + ry + 9], outline=_shade(color, .4) + (255,), width=9)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=INK, width=16)
    d.ellipse([cx - rx + 3, cy - ry + 3, cx + rx - 3, cy + ry - 3], outline=color + (255,), width=9)
    d.arc([cx - rx + 5, cy - ry + 5, cx + rx - 5, cy + ry - 5], 200, 330, fill=(255, 255, 255, 220), width=3)
    img.alpha_composite(glow(ring, color, 14, .6, 0))
    return img
