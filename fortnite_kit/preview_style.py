"""Render a style board of every overlay element (1920x1080)."""
import math
import random
from PIL import Image, ImageDraw, ImageFilter
import overlays as O

W, H = 1920, 1080


def background():
    bg = O._gradient((W, H), (30, 110, 235), (110, 35, 210))
    fx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fx)
    random.seed(3)
    for _ in range(9):  # diagonal light beams
        x = random.randint(-300, W)
        d.polygon([(x, 0), (x + 120, 0), (x + 620, H), (x + 420, H)], fill=(255, 255, 255, 22))
    bg.alpha_composite(fx.filter(ImageFilter.GaussianBlur(8)))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # perspective floor grid
    g = ImageDraw.Draw(grid)
    hy = int(H * .62)
    for k in range(-20, 21):
        g.line([(W / 2 + k * 40, hy), (W / 2 + k * 260, H)], fill=(120, 220, 255, 55), width=2)
    for k in range(12):
        y = hy + (H - hy) * (k / 11) ** 1.8
        g.line([(0, y), (W, y)], fill=(120, 220, 255, 45), width=2)
    bg.alpha_composite(grid)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * .25, -H * .35, W * 1.25, H * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGBA", (W, H), (10, 5, 40, 170))
    dark.putalpha(vig.point(lambda v: 170 - v * 170 // 255))
    bg.alpha_composite(dark)
    return bg


bg = background()
title = O.text_3d("WIZZCALL", 115, O.WHITE, (185, 215, 255), tilt=3, glow_color=O.CYAN)
bg.alpha_composite(title, (40, -10))
main = O.text_3d("5 SPOTS JETON PIRATE", 112, O.YELLOW, O.GOLD, tilt=-2, glow_color=O.GOLD)
bg.alpha_composite(main, ((W - main.width) // 2, 200))
card = O.box_3d("SPOT 1 : RUBBER RESORT", "CHRONO 3:30", rarity="epic", size=60)
bg.alpha_composite(card, ((W - card.width) // 2, 400))
bg.alpha_composite(O.chest_counter(7, pop=0.45), (10, 800))
bg.alpha_composite(O.circular_timer(124), (W - 320, 20))
bg.alpha_composite(O.ring_3d(140, O.CYAN, 0.4), (1170, 600))
bg.alpha_composite(O.arrow_3d(240, O.YELLOW, angle=-25), (860, 660))
bg.alpha_composite(O.progress_bar(0.62, 700, "TEMPS RESTANT"), (560, 920))
bg.convert("RGB").save("style_preview.png")
print("ok")
