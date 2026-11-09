"""
Procedural 2D textures drawn with Pillow (no external assets needed):
  - jolly_roger.png   straw-hat skull emblem (transparent background)
  - flag.png          the emblem on a black pirate flag
  - token_face.png    the Pirate Shop Token coin face
  - vbuck.png         blue "V" coin
  - sail.png          sail with a big emblem
Re-generated on every build, so editing colors here is enough.
"""
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config as C


def _rgb(c, a=255):
    """config color (0..1 linear-ish) -> 8-bit sRGB-ish tuple."""
    return tuple(int(max(0, min(1, v)) ** (1 / 2.2) * 255) for v in c) + (a,)


def _font(size):
    for p in C.FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_emblem(d, cx, cy, s, bone=(255, 255, 255, 255), dark=(15, 10, 10, 255)):
    """Straw-hat skull + crossbones, centered at (cx, cy), size s."""
    yellow = _rgb(C.COLORS["straw_yellow"])
    red = _rgb(C.COLORS["luffy_red"])
    w = int(0.11 * s)
    # crossbones
    for sx in (-1, 1):
        x0, y0 = cx - sx * 0.55 * s, cy - 0.35 * s
        x1, y1 = cx + sx * 0.55 * s, cy + 0.55 * s
        d.line((x0, y0, x1, y1), fill=bone, width=w)
        for (x, y) in ((x0, y0), (x1, y1)):
            for o in (-1, 1):
                ox = o * 0.06 * s
                d.ellipse((x + ox - 0.075 * s, y - ox - 0.075 * s,
                           x + ox + 0.075 * s, y - ox + 0.075 * s), fill=bone)
    # skull
    d.ellipse((cx - 0.34 * s, cy - 0.40 * s, cx + 0.34 * s, cy + 0.22 * s), fill=bone)
    d.rounded_rectangle((cx - 0.21 * s, cy + 0.02 * s, cx + 0.21 * s, cy + 0.36 * s),
                        radius=int(0.08 * s), fill=bone)
    for sx in (-1, 1):
        ex = cx + sx * 0.14 * s
        d.ellipse((ex - 0.10 * s, cy - 0.10 * s, ex + 0.10 * s, cy + 0.09 * s), fill=dark)
    d.polygon([(cx, cy + 0.06 * s), (cx - 0.05 * s, cy + 0.15 * s),
               (cx + 0.05 * s, cy + 0.15 * s)], fill=dark)
    for i in range(-2, 3):
        x = cx + i * 0.07 * s
        d.line((x, cy + 0.22 * s, x, cy + 0.34 * s), fill=dark, width=max(2, int(0.02 * s)))
    # straw hat
    d.ellipse((cx - 0.55 * s, cy - 0.40 * s, cx + 0.55 * s, cy - 0.20 * s), fill=yellow)
    d.chord((cx - 0.33 * s, cy - 0.78 * s, cx + 0.33 * s, cy - 0.10 * s), 180, 360, fill=yellow)
    d.rectangle((cx - 0.33 * s, cy - 0.47 * s, cx + 0.33 * s, cy - 0.36 * s), fill=red)


def make_jolly_roger(path, size=1024):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_emblem(ImageDraw.Draw(im), size / 2, size * 0.54, size * 0.62)
    im.save(path)


def make_flag(path, w=1024, h=700):
    im = Image.new("RGBA", (w, h), (12, 10, 12, 255))
    draw_emblem(ImageDraw.Draw(im), w / 2, h * 0.55, h * 0.62)
    im.save(path)


def make_sail(path, w=1024, h=1024):
    im = Image.new("RGBA", (w, h), (238, 232, 215, 255))
    d = ImageDraw.Draw(im)
    for i in range(0, w, 128):                       # canvas seams
        d.line((i, 0, i, h), fill=(215, 205, 185, 255), width=3)
    draw_emblem(d, w / 2, h * 0.55, h * 0.55, bone=(20, 16, 16, 255), dark=(238, 232, 215, 255))
    im.save(path)


def _coin(size, rim, face, ring_text, center_draw):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    d.ellipse((0, 0, size - 1, size - 1), fill=rim)
    d.ellipse((size * 0.07, size * 0.07, size * 0.93, size * 0.93), fill=face)
    # subtle radial shine
    shine = Image.new("L", (size, size), 0)
    sd = ImageDraw.Draw(shine)
    for i in range(40):
        r = size * 0.43 * (1 - i / 40)
        sd.ellipse((c - r - size * 0.08, c - r - size * 0.08, c + r - size * 0.08, c + r - size * 0.08),
                   fill=int(3 * i))
    im = Image.composite(Image.new("RGBA", (size, size), (255, 255, 255, 255)), im,
                         shine.filter(ImageFilter.GaussianBlur(size / 30)).point(lambda v: v // 3))
    d = ImageDraw.Draw(im)
    d.ellipse((size * 0.07, size * 0.07, size * 0.93, size * 0.93), outline=rim, width=int(size * 0.02))
    # text around the ring
    if ring_text:
        f = _font(int(size * 0.055))
        n = len(ring_text)
        for i, ch in enumerate(ring_text):
            a = math.radians(-150 + 300 * i / max(1, n - 1)) - math.pi / 2
            x = c + math.cos(a) * size * 0.40
            y = c + math.sin(a) * size * 0.40
            g = Image.new("RGBA", (int(size * 0.1), int(size * 0.1)), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((size * 0.05, size * 0.05), ch, font=f, fill=(255, 245, 200, 255),
                                   anchor="mm")
            g = g.rotate(-math.degrees(a) - 90, resample=Image.BICUBIC)
            im.alpha_composite(g, (int(x - g.width / 2), int(y - g.height / 2)))
    center_draw(ImageDraw.Draw(im), c, size)
    return im


def make_token(path, size=1024):
    gold = _rgb(C.COLORS["gold"])
    dark = (95, 45, 8, 255)

    def center(d, c, s):
        d.ellipse((s * 0.2, s * 0.2, s * 0.8, s * 0.8), fill=(20, 30, 70, 255))
        draw_emblem(d, c, c + s * 0.03, s * 0.42)

    im = _coin(size, dark, gold, "PIRATE SHOP TOKEN  *  TREASURE HUNTERS", center)
    im.save(path)


def make_vbuck(path, size=512):
    blue = _rgb(C.COLORS["vbuck_blue"])

    def center(d, c, s):
        f = _font(int(s * 0.62))
        d.text((c + s * 0.015, c + s * 0.035), "V", font=f, fill=(10, 30, 90, 255), anchor="mm")
        d.text((c, c + s * 0.02), "V", font=f, fill=(235, 245, 255, 255), anchor="mm")

    im = _coin(size, (20, 60, 160, 255), blue, "", center)
    im.save(path)


def make_all():
    os.makedirs(C.TEXTURE_DIR, exist_ok=True)
    paths = {
        "jolly": os.path.join(C.TEXTURE_DIR, "jolly_roger.png"),
        "flag": os.path.join(C.TEXTURE_DIR, "flag.png"),
        "sail": os.path.join(C.TEXTURE_DIR, "sail.png"),
        "token": os.path.join(C.TEXTURE_DIR, "token_face.png"),
        "vbuck": os.path.join(C.TEXTURE_DIR, "vbuck.png"),
    }
    make_jolly_roger(paths["jolly"])
    make_flag(paths["flag"])
    make_sail(paths["sail"])
    make_token(paths["token"])
    make_vbuck(paths["vbuck"])
    return paths


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(make_all())
