"""Render a style board of every overlay element (1920x1080)."""
import math, random
from PIL import Image, ImageDraw, ImageFilter
import overlays as O

W, H = 1920, 1080
bg = O._gradient((W, H), (40, 120, 230), (120, 40, 200))
rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(rays)
random.seed(3)
for _ in range(10):  # Fortnite-ish light rays
    x = random.randint(-200, W)
    d.polygon([(x, 0), (x + 140, 0), (x + 600, H), (x + 380, H)], fill=(255, 255, 255, 28))
bg.alpha_composite(rays.filter(ImageFilter.GaussianBlur(6)))

title = O.text_3d("WIZZCALL", 120, O.WHITE, (190, 220, 255), tilt=3)
bg.alpha_composite(title, (60, 10))
main = O.text_3d("5 SPOTS JETON PIRATE", 110, O.YELLOW, O.GOLD, tilt=-2)
bg.alpha_composite(main, ((W - main.width) // 2, 230))
sub = O.box_3d("SPOT 1 : RUBBER RESORT", "CHRONO 3:30", rarity="epic", size=60)
bg.alpha_composite(sub, ((W - sub.width) // 2, 410))
bg.alpha_composite(O.chest_counter(7, pop=0.5), (40, 830))
bg.alpha_composite(O.circular_timer(124), (W - 300, 40))
bg.alpha_composite(O.ring_3d(140, O.CYAN, 0.4), (1180, 640))
bg.alpha_composite(O.arrow_3d(250, O.YELLOW, angle=-25), (870, 690))
bg.alpha_composite(O.progress_bar(0.62, 700, "TEMPS RESTANT"), (560, 940))
bg.convert("RGB").save("style_preview.png")
print("ok")
