"""Fortnite-style pseudo-3D overlay elements rendered with PIL (RGBA).

Every function returns a PIL RGBA image that can be composited over a
video frame. Style: thick dark outline, extruded depth, top highlight,
yellow / electric-blue / purple palette (Fortnite rarity colours).
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_MAIN = os.path.join(HERE, "fonts", "LuckiestGuy-Regular.ttf")
FONT_ALT = os.path.join(HERE, "fonts", "Bangers-Regular.ttf")

YELLOW = (255, 214, 10)
GOLD = (255, 160, 0)
BLUE = (30, 160, 255)
CYAN = (60, 230, 255)
PURPLE = (170, 70, 255)
PINK = (255, 60, 170)
GREEN = (80, 230, 90)
WHITE = (255, 255, 255)
INK = (16, 12, 40)

RARITY = {
    "legendary": (GOLD, YELLOW),
    "epic": (PURPLE, (215, 140, 255)),
    "rare": (BLUE, CYAN),
    "uncommon": ((40, 170, 60), GREEN),
}


def font(size, alt=False):
    return ImageFont.truetype(FONT_ALT if alt else FONT_MAIN, size)


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def _gradient(size, top, bottom):
    w, h = size
    g = Image.new("RGBA", size)
    d = ImageDraw.Draw(g)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return g


def _drop_shadow(img, offset=(10, 14), blur=10, alpha=150):
    a = img.split()[3]
    sh = Image.new("RGBA", (img.width + 60, img.height + 60), (0, 0, 0, 0))
    mask = Image.new("L", sh.size, 0)
    mask.paste(a, (30 + offset[0], 30 + offset[1]))
    mask = mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: v * alpha // 255)
    sh.putalpha(mask)
    sh.alpha_composite(img, (30, 30))
    return sh


def text_3d(text, size=140, top=YELLOW, bottom=GOLD, depth=None, outline=None, alt=False, tilt=0.0):
    """Extruded 3D text: gradient face, dark extrusion, thick outline, gloss."""
    f = font(size, alt)
    depth = depth if depth is not None else max(4, size // 12)
    outline = outline if outline is not None else max(4, size // 14)
    l, t, r, b = f.getbbox(text)
    w, h = r - l + 2 * outline + depth + 20, b - t + 2 * outline + depth + 20
    ox, oy = outline + 10 - l, outline + 10 - t

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # extrusion (stacked copies, darker towards the back)
    for i in range(depth, 0, -1):
        d.text((ox + i * 0.6, oy + i), text, font=f, fill=_shade(bottom, 0.35 + 0.15 * (1 - i / depth)) + (255,),
               stroke_width=outline, stroke_fill=INK)
    # face mask
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((ox, oy), text, font=f, fill=255)
    d.text((ox, oy), text, font=f, fill=INK, stroke_width=outline, stroke_fill=INK)
    face = _gradient((w, h), top, bottom)
    img.paste(face, (0, 0), mask)
    # gloss on upper half of the letters
    gloss = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(gloss)
    gd.rectangle([0, 0, w, oy + (b - t) * 0.42], fill=80)
    gloss = Image.composite(gloss, Image.new("L", (w, h), 0), mask)
    white = Image.new("RGBA", (w, h), WHITE + (255,))
    img.paste(white, (0, 0), gloss)
    if tilt:
        img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
    return _drop_shadow(img)


def box_3d(text, sub=None, rarity="rare", size=64, pad=34):
    """Slanted 3D panel (Fortnite UI card) with text on it."""
    c1, c2 = RARITY.get(rarity, RARITY["rare"])
    title = text_3d(text, size, WHITE, (220, 235, 255), depth=3, outline=max(3, size // 16))
    subimg = text_3d(sub, int(size * 0.8), YELLOW, GOLD, depth=3, outline=4) if sub else None
    w = max(title.width, subimg.width if subimg else 0) + pad * 2
    th = title.height - 60
    sh = (subimg.height - 60) if subimg else 0
    h = th + sh + pad
    depth, skew = 16, 26
    img = Image.new("RGBA", (w + skew + depth + 10, h + depth + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    poly = lambda dx, dy: [(skew + dx, dy), (w + skew + dx, dy), (w + dx, h + dy), (dx, h + dy)]
    d.polygon(poly(depth, depth), fill=_shade(c1, 0.35) + (255,))
    face = _gradient((img.width, img.height), c2, c1)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon(poly(0, 0), fill=255)
    img.paste(face, (0, 0), m)
    d.polygon(poly(0, 0), outline=INK, width=6)
    d.line([(skew + 8, 8), (w + skew - 8, 8)], fill=(255, 255, 255, 140), width=5)
    img.alpha_composite(title, ((w + skew - title.width) // 2, -30 + pad // 3))
    if subimg:
        img.alpha_composite(subimg, ((w + skew - subimg.width) // 2, th - 30 + pad // 3))
    return _drop_shadow(img, blur=8)


def chest_icon(size=120, open_=False):
    """Little 3D golden chest drawn with polygons."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    wood, wood_d = (150, 80, 30), (95, 48, 18)
    # body (front + side for 3D)
    d.polygon([(s*.14, s*.48), (s*.80, s*.48), (s*.80, s*.92), (s*.14, s*.92)], fill=wood, outline=INK, width=4)
    d.polygon([(s*.80, s*.48), (s*.92, s*.40), (s*.92, s*.84), (s*.80, s*.92)], fill=wood_d, outline=INK, width=4)
    # lid
    if open_:
        d.polygon([(s*.14, s*.48), (s*.80, s*.48), (s*.90, s*.10), (s*.26, s*.10)], fill=wood_d, outline=INK, width=4)
        glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([s*.2, s*.25, s*.85, s*.6], fill=YELLOW + (200,))
        img = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s * .06)), img)
        d = ImageDraw.Draw(img)
    else:
        d.pieslice([s*.14, s*.22, s*.80, s*.74], 180, 360, fill=wood, outline=INK, width=4)
        d.polygon([(s*.80, s*.48), (s*.92, s*.40), (s*.92, s*.36), (s*.80, s*.40)], fill=wood_d)
    # gold trims + lock
    for x in (.22, .66):
        d.rectangle([s*x, s*.48, s*(x+.07), s*.92], fill=YELLOW, outline=INK, width=3)
    d.rectangle([s*.40, s*.50, s*.54, s*.66], fill=YELLOW, outline=INK, width=3)
    return img


def chest_counter(count, label="COFFRES", pop=0.0):
    """Animated chest counter; `pop` 0..1 gives a bounce scale on increment."""
    card = Image.new("RGBA", (470, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([10, 18, 460, 160], 28, fill=_shade(PURPLE, 0.35) + (255,))
    face = _gradient(card.size, (120, 60, 230), (60, 20, 140))
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 6, 450, 148], 28, fill=255)
    card.paste(face, (0, 0), m)
    d.rounded_rectangle([0, 6, 450, 148], 28, outline=INK, width=6)
    card.alpha_composite(chest_icon(130, open_=pop > 0), (14, 10))
    lab = text_3d(label, 40, WHITE, (210, 210, 255), depth=2, outline=4, alt=True)
    card.alpha_composite(lab, (135, -14))
    scale = 1 + 0.45 * math.sin(math.pi * min(1, pop)) if pop else 1
    num = text_3d(str(count), int(92 * scale), YELLOW, GOLD)
    cx, cy = 335, 98
    card.alpha_composite(num, (int(cx - num.width / 2 + 5), int(cy - num.height / 2 + 8)))
    return _drop_shadow(card, blur=8)


def circular_timer(remaining, total=210.0, size=230):
    """Circular 3D countdown ring (3:30 default) with mm:ss in the middle."""
    S = size
    img = Image.new("RGBA", (S + 20, S + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    frac = max(0.0, min(1.0, remaining / total))
    col = GREEN if frac > 0.5 else (YELLOW if frac > 0.2 else (255, 70, 60))
    # depth disc
    d.ellipse([10, 22, S + 10, S + 22], fill=_shade(INK, 1) + (255,))
    d.ellipse([10, 10, S + 10, S + 10], fill=(35, 30, 80, 255), outline=INK, width=6)
    # ring track + progress
    pad = 22
    box = [10 + pad, 10 + pad, S + 10 - pad, S + 10 - pad]
    d.arc(box, 0, 360, fill=(70, 65, 120), width=26)
    if frac > 0:
        d.arc(box, -90, -90 + 360 * frac, fill=_shade(col, 0.6), width=26)
        inner = [box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3]
        d.arc(inner, -90, -90 + 360 * frac, fill=col, width=16)
        # end knob
        ang = math.radians(-90 + 360 * frac)
        cx, cy, rr = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2 - 10
        kx, ky = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
        d.ellipse([kx - 15, ky - 15, kx + 15, ky + 15], fill=WHITE, outline=INK, width=4)
    m, s = divmod(int(math.ceil(remaining)), 60)
    txt = text_3d(f"{m}:{s:02d}", int(S * 0.27), WHITE, (200, 220, 255), depth=4, outline=5)
    img.alpha_composite(txt, ((img.width - txt.width) // 2, (S + 20 - txt.height) // 2))
    return _drop_shadow(img, blur=8)


def progress_bar(frac, width=900, label=None):
    """Thick 3D progress bar (alternative to the circular timer)."""
    h, depth = 54, 12
    img = Image.new("RGBA", (width + depth + 10, h + depth + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y0 = 50
    d.rounded_rectangle([depth, y0 + depth, width + depth, y0 + h + depth], 20, fill=INK)
    d.rounded_rectangle([0, y0, width, y0 + h], 20, fill=(45, 40, 95), outline=INK, width=5)
    fw = int((width - 10) * max(0, min(1, frac)))
    if fw > 30:
        bar = _gradient((fw, h - 10), YELLOW, GOLD)
        m = Image.new("L", bar.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, fw - 1, h - 11], 16, fill=255)
        img.paste(bar, (5, y0 + 5), m)
        d.line([(16, y0 + 12), (fw - 10, y0 + 12)], fill=(255, 255, 255, 150), width=5)
    if label:
        img.alpha_composite(text_3d(label, 42, WHITE, (210, 220, 255), depth=3, outline=4, alt=True), (0, -30))
    return _drop_shadow(img, blur=6)


def arrow_3d(length=260, color=YELLOW, angle=0.0, bob=0.0):
    """Extruded 3D arrow pointing right (rotate with `angle`, degrees CCW)."""
    L, T = length, length * 0.42
    shaft = T * 0.42
    pts = [(0, T/2 - shaft/2), (L*0.6, T/2 - shaft/2), (L*0.6, 0), (L, T/2), (L*0.6, T), (L*0.6, T/2 + shaft/2), (0, T/2 + shaft/2)]
    depth = int(L * 0.07)
    img = Image.new("RGBA", (int(L + depth + 40), int(T + depth + 40)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(depth, 0, -1):
        d.polygon([(x + 20 + i * .5, y + 20 + i) for x, y in pts], fill=_shade(color, 0.45) + (255,))
    d.polygon([(x + 20 + depth * .5, y + 20 + depth) for x, y in pts], outline=INK, width=6)
    face = _gradient(img.size, _shade(color, 1.15) if max(color) < 230 else WHITE, color)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon([(x + 20, y + 20) for x, y in pts], fill=255)
    img.paste(_gradient(img.size, tuple(min(255, v + 60) for v in color), color), (0, 0), m)
    d.polygon([(x + 20, y + 20) for x, y in pts], outline=INK, width=6)
    d.line([(26, 20 + T/2 - shaft/2 + 6), (20 + L*0.6, 20 + T/2 - shaft/2 + 6)], fill=(255, 255, 255, 170), width=4)
    img = _drop_shadow(img, blur=8)
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
    return img


def ring_3d(radius=120, color=CYAN, t=0.0):
    """Perspective (tilted) highlight ring, pulsing with time `t` in seconds."""
    pulse = 1 + 0.08 * math.sin(t * 2 * math.pi * 1.5)
    rx, ry = radius * pulse, radius * 0.45 * pulse
    W, H = int(rx * 2 + 80), int(ry * 2 + 120)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cx, cy = W / 2, H / 2 + 20
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=color + (220,), width=22)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    for k, (yoff, col) in enumerate([(14, _shade(color, 0.4)), (0, color)]):
        d.ellipse([cx - rx, cy - ry + yoff, cx + rx, cy + ry + yoff], outline=INK, width=16)
        d.ellipse([cx - rx + 3, cy - ry + yoff + 3, cx + rx - 3, cy + ry + yoff - 3], outline=col + (255,), width=9)
    # vertical beam lines rising from the ring
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    for i in range(10):
        a = 2 * math.pi * i / 10 + t
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        if math.sin(a) > -0.2:
            bd.line([(x, y), (x, y - 60 - 20 * math.sin(t * 4 + i))], fill=color + (120,), width=5)
    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(2)))
    return img
