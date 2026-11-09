"""Combine still JPGs into one labeled contact sheet (debug helper)."""
import sys
from PIL import Image, ImageDraw
paths, out = sys.argv[1:-1], sys.argv[-1]
ims = [Image.open(p) for p in paths]
w, h = 270, 480
sheet = Image.new("RGB", (w * len(ims), h + 20), (20, 20, 20))
for i, (p, im) in enumerate(zip(paths, ims)):
    sheet.paste(im.resize((w, h)), (i * w, 20))
    ImageDraw.Draw(sheet).text((i * w + 5, 3), p.split("_")[-1], fill=(255, 255, 0))
sheet.save(out)
