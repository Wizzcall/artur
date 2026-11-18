"""
Photo de profil de chaîne « Wizzcall » — ambiance Vice City / GTA 6 (design original, sans logo ni visuel Rockstar).

    python avatar.py  → ../WIZZCALL_PROFIL.png (2048²) , ../WIZZCALL_PROFIL_800.png (800², format YouTube)
                        + aperçu rond ../WIZZCALL_PROFIL_apercu.png
"""
from pathlib import Path
import math
import numpy as np
import cv2
import fx
from fx import PINK, CYAN, ORANGE, YELLOW, PURPLE, NAVY, text3d, plain_text, blit

ROOT = Path(__file__).resolve().parent
S = 1080  # rendu carré (les sprites de fx sont bornés à 1920×1080)


def col(c): return tuple(float(x) for x in c)


def palm(lay, base, height, lean, color, s=1.0):
    """palmier en silhouette : tronc courbe effilé + palmes en arcs"""
    bx, by = base
    pts = []
    for i in range(41):
        u = i / 40
        x = bx + lean * height * u ** 1.8
        y = by - height * u
        pts.append((x, y, (26 - 16 * u) * s))
    for (x0, y0, w0), (x1, y1, w1) in zip(pts, pts[1:]):
        cv2.line(lay, (int(x0), int(y0)), (int(x1), int(y1)), col(color), max(2, int(w0)), cv2.LINE_AA)
    tx, ty, _ = pts[-1]
    for ang, ln, droop in [(-170, 230, 0.9), (-140, 250, 0.7), (-105, 200, 0.4), (-70, 210, 0.45),
                           (-35, 250, 0.7), (-5, 235, 0.9), (-200, 190, 1.1), (25, 190, 1.1)]:
        a = math.radians(ang); L = ln * s
        leaf_top, leaf_bot = [], []
        for i in range(25):
            u = i / 24
            x = tx + math.cos(a) * L * u
            y = ty + math.sin(a) * L * u + droop * L * 0.55 * u ** 2
            w = 22 * s * math.sin(math.pi * u) ** 0.8
            nx, ny = -math.sin(a), math.cos(a)
            leaf_top.append((x + nx * w, y + ny * w)); leaf_bot.append((x - nx * w * 0.4, y - ny * w * 0.4))
        poly = np.array(leaf_top + leaf_bot[::-1], np.int32)
        cv2.fillPoly(lay, [poly], col(color), cv2.LINE_AA)


def main():
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    u = yy / S
    top, mid, bot = fx.C(24, 8, 60), fx.C(170, 30, 150), fx.C(255, 120, 80)
    bg = np.where(u[..., None] < 0.62, top + (mid - top) * (u[..., None] / 0.62), mid + (bot - mid) * ((u[..., None] - 0.62) / 0.38))
    out = bg.astype(np.float32)
    # soleil rayé
    cx, cy, r = S / 2, S * 0.60, S * 0.30
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    rel = yy - cy
    stripes = (rel > -r * 0.15) & (((rel + r * 0.15) % 34) < (3 + np.clip(rel + r * 0.15, 0, None) / r * 16))
    disk = np.clip((r - d) / 2, 0, 1) * (~stripes)
    g = np.clip((yy - (cy - r)) / (2 * r), 0, 1)[..., None]
    out = out + PINK * (np.clip(1 - d / (r * 2.2), 0, 1) ** 2)[..., None] * 0.5
    out = out * (1 - disk[..., None]) + (YELLOW * (1 - g) + PINK * g) * disk[..., None]
    # sol en grille néon
    hy = int(S * 0.74)
    out[hy:] = fx.C(26, 6, 50)
    grid = np.zeros((S, S), np.float32)
    for k in range(-14, 15):
        cv2.line(grid, (int(S / 2 + k * 30), hy), (int(S / 2 + k * 260), S + 60), 1.0, 2, cv2.LINE_AA)
    for j in range(1, 30):
        y = hy + (S - hy) / (j * 0.55)
        if hy < y < S: cv2.line(grid, (0, int(y)), (S, int(y)), 1.0, 2, cv2.LINE_AA)
    cv2.line(grid, (0, hy), (S, hy), 1.0, 3, cv2.LINE_AA)
    out = out + (grid + cv2.GaussianBlur(grid, (0, 0), 8) * 1.4)[..., None] * PINK
    # palmiers
    lay = np.zeros((S, S, 3), np.float32); dark = fx.C(30, 6, 46)
    palm(lay, (150, hy + 40), 620, 0.30, dark, 1.15)
    palm(lay, (960, hy + 40), 560, -0.28, dark, 1.05)
    palm(lay, (60, hy + 60), 420, 0.12, dark, 0.8)
    m = (lay.max(2) > 0).astype(np.float32)[..., None]
    m = cv2.GaussianBlur(m, (0, 0), 0.8)[..., None] if m.ndim == 2 else m
    out = out * (1 - m) + dark * m
    out = np.clip(out, 0, 1)

    canvas = np.zeros((1080, 1920, 3), np.float32)   # zone de travail aux dimensions de fx
    canvas[:, :S] = out
    w = text3d("W", "anton", 700, (255, 236, 140), (255, 60, 160), 40, (70, 18, 120), (255, 64, 160), 46, 0.75)
    canvas = blit(canvas, w, S / 2, S * 0.45, 1.0, 1.0)
    name = text3d("WIZZCALL", "anton", 150, (140, 240, 255), (90, 120, 255), 12, (30, 20, 90), (60, 200, 255), 22, 0.7, spacing=4)
    canvas = blit(canvas, name, S / 2, S * 0.83, 1.0, 1.0)
    out = canvas[:, :S]
    # vignette ronde douce (le profil YouTube est affiché en cercle)
    rr = np.sqrt((xx - S / 2) ** 2 + (yy - S / 2) ** 2) / (S / 2)
    out = out * (1 - 0.35 * np.clip(rr - 0.75, 0, 1) / 0.25)[..., None]
    u8 = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
    big = cv2.resize(u8, (2048, 2048), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(ROOT.parent / "WIZZCALL_PROFIL.png"), big)
    cv2.imwrite(str(ROOT.parent / "WIZZCALL_PROFIL_800.png"), cv2.resize(u8, (800, 800), interpolation=cv2.INTER_AREA))
    # aperçu : cercle à 3 tailles (comme sur YouTube)
    prev = np.full((420, 760, 3), 245, np.uint8); x = 20
    for sz in (300, 120, 48):
        im = cv2.resize(u8, (sz, sz), interpolation=cv2.INTER_AREA)
        mk = np.zeros((sz, sz), np.uint8); cv2.circle(mk, (sz // 2, sz // 2), sz // 2, 255, -1, cv2.LINE_AA)
        a = (mk / 255.0)[..., None]
        roi = prev[60:60 + sz, x:x + sz]
        prev[60:60 + sz, x:x + sz] = (roi * (1 - a) + im * a).astype(np.uint8); x += sz + 40
    cv2.imwrite(str(ROOT.parent / "WIZZCALL_PROFIL_apercu.png"), prev)
    print("ok")


if __name__ == "__main__":
    main()
