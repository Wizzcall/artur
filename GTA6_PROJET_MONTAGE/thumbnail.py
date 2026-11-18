"""
Miniature YouTube dans l'identité visuelle du montage (synthwave Vice City, textes 3D, détourage).

    python thumbnail.py   → ../GTA6_MINIATURE.jpg (1280×720, < 2 Mo) + ../GTA6_MINIATURE_1920.png
"""
from pathlib import Path
import numpy as np
import cv2
import fx
from fx import W, H, PINK, CYAN, ORANGE, YELLOW, img, mask, fit_rect, view, text3d, plain_text, blit, synth_grid, fast_blur

ROOT = Path(__file__).resolve().parent


def main():
    # fond : ciel de Vice City (skyline Squalo) teinté coucher de soleil + sol en grille néon
    sky = view(img("ue_squalo", 1920), fit_rect(16 / 9, (0, 0.0, 1, 0.8)))
    sky = fast_blur(sky, 3) * 0.55 + fx.sunset_bg(0) * 0.45
    out = synth_grid(0.3, 0.70, PINK, alpha=0.9, sun=True)
    hy = int(H * 0.70)
    g = np.clip(np.linspace(0, 1, hy, dtype=np.float32) * 1.4, 0, 1)[:, None, None]
    out[:hy] = sky[:hy] * (1 - g * 0.35) + out[:hy] * g * 0.35
    out = fx.light_leak(out, 0.62, True, 0.9)

    # Jason & Lucia détourés à droite, avec ombre portée et liseré néon
    k = "jl_beach"; src = img(k, 2880); m = mask(k, 2880)
    sh, sw = src.shape[:2]
    x0, x1 = int(sw * 0.40), int(sw * 0.98)
    crop, mc = src[:, x0:x1], m[:, x0:x1]
    s = 1180 / sh
    crop = cv2.resize(crop, (int(crop.shape[1] * s), 1180), interpolation=cv2.INTER_AREA)
    mc = cv2.resize(mc, (crop.shape[1], 1180), interpolation=cv2.INTER_AREA)
    ox, oy = W - crop.shape[1] + 230, H - 1180 + 140
    lay = np.zeros((H, W, 3), np.float32); al = np.zeros((H, W), np.float32)
    xa, xb = max(0, ox), min(W, ox + crop.shape[1]); ya, yb = max(0, oy), min(H, oy + 1180)
    lay[ya:yb, xa:xb] = crop[ya - oy:yb - oy, xa - ox:xb - ox]
    al[ya:yb, xa:xb] = mc[ya - oy:yb - oy, xa - ox:xb - ox]
    shadow = cv2.GaussianBlur(np.roll(al, -40, 1), (0, 0), 25)[..., None]
    out = out * (1 - 0.55 * shadow)
    glow = cv2.GaussianBlur(cv2.dilate(al, np.ones((9, 9), np.uint8)), (0, 0), 18)[..., None]
    out = np.clip(out + glow * (PINK * 0.6 + ORANGE * 0.3) * 0.9, 0, 1)
    out = out * (1 - al[..., None]) + fx.grade(lay) * al[..., None]
    edge = np.clip(al - cv2.erode(al, np.ones((5, 5), np.uint8)), 0, 1)[..., None]
    out = np.clip(out + edge * PINK * 0.6, 0, 1)

    # textes 3D à gauche
    t1 = text3d("GTA VI", "anton", 300, (255, 236, 140), (255, 60, 160), 30, (70, 18, 120), (255, 64, 160), 34, 0.7)
    out = blit(out, t1, 500, 290, 1.0, 1.0, -4)
    t2 = text3d("PRÉCHARGÉ !", "anton", 136, (130, 240, 255), (90, 110, 255), 16, (30, 20, 90), (60, 200, 255), 24, 0.7)
    out = blit(out, t2, 500, 560, 1.0, 1.0, -4)
    # barre de progression néon
    bx, by, bw, bh = 110, 720, 560, 46
    cv2.rectangle(out, (bx - 6, by - 6), (bx + bw + 6, by + bh + 6), (1, 1, 1), 4, cv2.LINE_AA)
    pw = int(bw * 0.99)
    grad = np.linspace(0, 1, pw, dtype=np.float32)[None, :, None]
    out[by:by + bh, bx:bx + pw] = CYAN * (1 - grad) + PINK * grad
    gl = np.zeros_like(out); gl[by:by + bh, bx:bx + pw] = PINK
    out = np.clip(out + cv2.GaussianBlur(gl, (0, 0), 16) * 0.9, 0, 1)
    pc = text3d("99 %", "anton", 130, (255, 255, 255), (255, 214, 102), 10, (70, 18, 120), (255, 64, 160), 16, 0.7)
    out = blit(out, pc, bx + bw + 135, by + bh / 2, 1.0, 1.0)
    d = plain_text("19.11.2026", "bebas", 84, (255, 255, 255), spacing=10, glow=(255, 64, 160), glow_r=12)
    out = blit(out, d, 480, 880, 1.0, 1.0)

    out = np.clip(out * fx.vignette_map() * 1.04, 0, 1)
    u8 = (out * 255 + 0.5).astype(np.uint8)
    cv2.imwrite(str(ROOT.parent / "GTA6_MINIATURE_1920.png"), u8)
    small = cv2.resize(u8, (1280, 720), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(ROOT.parent / "GTA6_MINIATURE.jpg"), small, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("ok")


if __name__ == "__main__":
    main()
