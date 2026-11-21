"""Miniature 9:16 (1080x1920) pour le short : image HD de Mandy + titre accrocheur.
python make_short_thumbnail.py thumbnails/mandy_source.png thumbnails/miniature_short.jpg
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

W, H = 1080, 1920
BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
YELLOW, RED = (255, 214, 0), (230, 20, 35)

src = Image.open(sys.argv[1]).convert("RGB")
# recadrage tête -> taille (évite le sous-titre incrusté), puis upscale Lanczos
crop = src.crop((140, 70, 940, 70 + 1422))
img = crop.resize((W, H), Image.Resampling.LANCZOS)
img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=90, threshold=2))
img = ImageEnhance.Contrast(img).enhance(1.22)
img = ImageEnhance.Color(img).enhance(1.35)
img = ImageEnhance.Brightness(img).enhance(1.12)

a = np.asarray(img).astype(np.float32)
a[..., 0] *= 1.05; a[..., 2] *= 0.93                       # teinte chaude
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
d = np.sqrt(((xx - W * .48) / (W * .75)) ** 2 + ((yy - H * .35) / (H * .7)) ** 2)
a *= np.clip(1.15 - 0.55 * d, 0.35, 1.08)[..., None]       # vignette + éclairage visage
grad = np.clip((yy - H * 0.58) / (H * 0.32), 0, 1)[..., None]  # dégradé sombre bas
a *= 1 - 0.8 * grad
img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")

ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(ov)

def text(xy, s, size, fill, stroke=12, anchor="mm"):
    f = ImageFont.truetype(BLACK, size)
    x, y = xy
    if stroke: d.text((x + 8, y + 10), s, font=f, fill=(0, 0, 0, 170), anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    d.text((x, y), s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill="black")

# badge GTA VI
d.rounded_rectangle((44, 60, 330, 160), 22, fill=RED + (255,), outline="white", width=5)
text((187, 110), "GTA VI", 62, "white", stroke=0)

# titre
text((W // 2, 1440), "QUI EST", 120, "white")
text((W // 2, 1600), "MANDY ?!", 190, YELLOW, stroke=14)
text((W // 2, 1760), "C'EST FOU CE QU'ELLE M'A APPRIS…", 50, "white", stroke=7)

img.alpha_composite(ov)
img.convert("RGB").save(sys.argv[2], quality=95)
print("OK", sys.argv[2])
