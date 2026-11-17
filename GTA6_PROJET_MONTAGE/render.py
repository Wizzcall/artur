"""
RENDU VIDÉO — lit build/edl.json et calcule chaque image (1920×1080, 30 i/s).

    python render.py --start 0 --end 900 --out build/chunks/c000.mp4
    python render.py --preview 12.5 40 95      (images PNG de contrôle)
"""
import argparse, json, math, subprocess, sys
from functools import lru_cache
from pathlib import Path
import numpy as np
import cv2

import fx
from fx import (W, H, PINK, MAGENTA, ORANGE, YELLOW, CYAN, BLUE, PURPLE, NAVY, WHITE, BLACK, clamp, lerp,
                ease_io, ease_out, ease_in, ease_back, env, img, bgimg, mask, has_mask, Video, fit_rect,
                move_rect, view, kb_frame, fast_blur, motion_blur, zoom_blur, scale_frame, text3d, plain_text,
                blit, card, synth_grid, sunset_bg, grade, finish, letterbox, light_leak, rgb_split, glitch_blocks)

ROOT = Path(__file__).resolve().parent
EDL = json.loads((ROOT / "build" / "edl.json").read_text())
FPS = EDL["fps"]
PAD = 0.6  # marge de mouvement (le plan continue de bouger pendant les transitions)
PS5_DIR = ROOT / "ps5_captures"   # déposez ici vos vraies captures : boot.mp4 page.mp4 dl.mp4 done.mp4 locked.mp4

PINK_T, YEL_T, CYAN_T, PURP_T, WHITE_T = (255, 64, 160), (255, 214, 102), (60, 220, 255), (120, 50, 210), (255, 255, 255)


def U(lt, dur):
    return clamp((lt + PAD) / (dur + 2 * PAD))


def src_aspect(key):
    s = img(key, 1920).shape; return s[1] / s[0]


# ═══════════════════════════════════════════════════════════ PLANS PHOTO
def shot_kb(p, lt, dur, fi):
    k = p["img"]; base = fit_rect(src_aspect(k), tuple(p.get("crop", (0, 0, 1, 1))))
    r = move_rect(base, p.get("move", "in"), ease_io(U(lt, dur)) * 0.85 + U(lt, dur) * 0.15, p.get("amt", 0.12))
    return kb_frame(k, r)


def shot_para(p, lt, dur, fi):
    """Parallaxe 2.5D : sujet détouré (premier plan) et décor (arrière-plan) à des vitesses différentes."""
    k = p["img"]; mv = p.get("move", "in")
    u = ease_io(U(lt, dur)) * 0.8 + U(lt, dur) * 0.2
    base = fit_rect(src_aspect(k))
    if has_mask(k):
        lv = 1920
        bgv = view(bgimg(k, lv), move_rect(base, mv, u, 0.05))
        bgv = cv2.GaussianBlur(bgv, (0, 0), 2.2)                # profondeur de champ
        rf = move_rect(base, mv, u, 0.15)
        fgv = view(img(k, lv), rf)
        a = view(mask(k, lv), rf)[..., None]
        sh = cv2.GaussianBlur(np.roll(np.roll(a[..., 0], 26, 0), 18, 1), (0, 0), 14)[..., None]
        bgv = bgv * (1 - 0.42 * sh)                             # ombre portée du sujet sur le décor
        out = bgv * (1 - a) + fgv * a
        edge = np.clip(a[..., 0] - cv2.erode(a[..., 0], np.ones((5, 5), np.uint8)), 0, 1)[..., None]
        return np.clip(out + edge * (PINK * 0.5 + ORANGE * 0.3) * 0.35, 0, 1)
    # sans détourage : déformation par profondeur (sol proche, ciel lointain)
    src = img(k, 2880); sh_, sw_ = src.shape[:2]
    cx, cy, w = base
    s0 = W / (w * sw_)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = (yy / H) ** 1.6
    if mv == "in": S = s0 * (1 + 0.04 * u + 0.10 * u * d); dx = 0
    elif mv == "out": S = s0 * (1 + 0.04 * (1 - u) + 0.10 * (1 - u) * d); dx = 0
    else:
        S = s0 * 1.1 * np.ones_like(d); dx = (u - 0.5) * (1 if mv == "right" else -1) * 120 * (0.3 + d)
    mx = cx * sw_ + (xx - W / 2 + dx) / S
    my = cy * sh_ + (yy - H / 2) / S
    return cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


@lru_cache(maxsize=48)
def card_sprite(key, w, h, crop=None, border=4):
    base = fit_rect(src_aspect(key), crop or (0, 0, 1, 1))
    v = view(img(key, 1920 if w < 1200 else 2880), base, out=(w, h), interp=cv2.INTER_AREA)
    return card(v, r=18, border=border)


def bg_blur(key, lt, dur, dark=0.42, sigma=22):
    base = fit_rect(src_aspect(key))
    v = view(img(key, 1920), move_rect(base, "in", U(lt, dur), 0.08))
    b = fast_blur(v, sigma) * dark
    return b * 0.8 + (NAVY * 0.6 + PURPLE * 0.4) * 0.2


def shot_stack(p, lt, dur, fi):
    keys = p["imgs"]
    out = bg_blur(keys[0], lt, dur, 0.38)
    u = U(lt, dur)
    lay = [((540, 400), -4.0, 0.62, 40), ((1380, 470), 3.0, 0.58, -55), ((960, 760), -1.5, 0.55, 25)]
    for i, kk in enumerate(keys[:3]):
        (x, y), rot, sc, drift = lay[i]
        cw, ch = 920, 518
        spr = card_sprite(kk, cw, ch)
        e = ease_out((lt - 0.18 * i) / 0.55)
        out = blit(out, spr, x + drift * (u - 0.5) * 2, y + (1 - e) * 80 - 30 * u * (i - 1),
                   sc * (0.9 + 0.1 * e) * (1 + 0.04 * u), clamp(e * 1.2), rot + (1 - e) * 4)
    return out


def shot_loc(p, lt, dur, fi):
    out = shot_kb(dict(img=p["img"], move="in", amt=0.1), lt, dur, fi)
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    out = out * (1 - 0.6 * np.clip((g - 0.55) / 0.45, 0, 1))
    e = ease_out(lt / 0.5)
    name = text3d(p["name"], "anton", 120, (255, 255, 255), (120, 230, 255), 9, (60, 20, 110), (255, 64, 160), 14, 0.6)
    out = blit(out, name, 150 + (1 - e) * -80, 900, 1.0, e, 0, anchor="l")
    tag = plain_text("LEONIDA  ·  LIEU", "bebas", 46, YEL_T, spacing=6)
    out = blit(out, tag, 160 + (1 - e) * -40, 805, 1.0, e, anchor="l")
    cv2.circle(out, (118, 902), int(16 * e), tuple(float(c) for c in PINK), -1, cv2.LINE_AA)
    return out


def shot_hero(p, lt, dur, fi):
    """Personnage détouré, nom géant en 3D placé ENTRE le décor et le sujet."""
    k = p["img"]; u = U(lt, dur)
    base = fit_rect(src_aspect(k))
    bgv = view(bgimg(k, 1920), move_rect(base, "in", u, 0.05))
    bgv = fast_blur(bgv, 6) * 0.55
    tint = fx.sunset_bg(0)
    bgv = bgv * 0.7 + tint * 0.3
    first, last = p["name"].split(" ", 1)
    t1 = text3d(first, "anton", 330, (255, 230, 120), (255, 70, 160), 20, (70, 20, 120), (255, 64, 160), 24, 0.5)
    t2 = text3d(last, "anton", 170, (130, 235, 255), (90, 120, 255), 12, (40, 20, 100), (60, 200, 255), 16, 0.4, spacing=6)
    e = ease_out(lt / 0.7)
    left = p.get("side") == "right"   # sujet à droite → texte calé à gauche
    tx = (660 if left else 1260) + (-1 if left else 1) * 60 * (u - 0.5) * 2
    ty = p.get('ty', 0)
    bgv = blit(bgv, t1, tx + (1 - e) * (-200 if left else 200), 430 + ty, 1.0, e)
    bgv = blit(bgv, t2, tx + (1 - e) * (-120 if left else 120), 690 + ty * 1.3, 1.0, ease_out((lt - 0.2) / 0.6))
    rf = move_rect(base, "in", u, 0.14)
    rf = (rf[0] + (0.012 if left else -0.012) * (1 - e), rf[1], rf[2])
    fgv = view(img(k, 1920), rf); a = view(mask(k, 1920), rf)[..., None]
    sh = cv2.GaussianBlur(np.roll(np.roll(a[..., 0], 30, 0), -24 if left else 24, 1), (0, 0), 16)[..., None]
    bgv = bgv * (1 - 0.5 * sh)
    out = bgv * (1 - a) + fgv * a
    edge = np.clip(a[..., 0] - cv2.erode(a[..., 0], np.ones((5, 5), np.uint8)), 0, 1)[..., None]
    return np.clip(out + edge * (PINK * 0.6 + ORANGE * 0.3) * 0.5, 0, 1)


def shot_split(p, lt, dur, fi):
    u = U(lt, dur)
    a = shot_kb(dict(img=p["a"], move="right", amt=0.14), lt, dur, fi)
    b = shot_kb(dict(img=p["b"], move="left", amt=0.14), lt, dur, fi)
    e = ease_out(lt / 0.6)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    split = W * (0.5 + 0.03 * (u - 0.5)) + (yy - H / 2) * -0.25
    off = (1 - e) * W * 0.5
    m = np.clip((xx - split - off) / 3 + 0.5, 0, 1)[..., None]
    out = a * (1 - m) + b * m
    line = np.exp(-((xx - split - off) ** 2) / 30)[..., None]
    glow = np.exp(-((xx - split - off) ** 2) / 900)[..., None]
    return np.clip(out + line * WHITE * 0.9 + glow * PINK * 0.5, 0, 1)


# ═══════════════════════════════════════════════════════════ VIDÉO
def shot_reveal(p, lt, dur, fi):
    v = Video.get("reveal")
    t = clamp(p["a"] + lt * p.get("speed", 1.0), p["a"], p["b"] - 1 / 30)
    f = v.at(t * 30)
    return scale_frame(f, 1.0 + 0.03 * U(lt, dur))


def clip_frame(key, lt, dur):
    v = Video.get(key)
    rate = min(1.0, (v.n - 1) / max(1, (dur + PAD) * 30))
    return v.at(clamp(lt + PAD * 0.5, 0, dur + PAD) * 30 * rate)


def shot_clip(p, lt, dur, fi):
    f = clip_frame(p["clip"], lt, dur); u = U(lt, dur)
    if abs(f.shape[1] / f.shape[0] - 16 / 9) < 0.05:
        return scale_frame(cv2.resize(f, (W, H)), 1.02 + 0.06 * u)
    bgf = cv2.resize(f, (W, W))[(W - H) // 2:(W - H) // 2 + H]
    out = fast_blur(bgf, 28) * 0.45
    side = cv2.resize(f, (880, 880), interpolation=cv2.INTER_AREA)
    out = blit(out, card(side, r=20, border=3), W / 2, H / 2, 1.0 + 0.05 * u, 1.0)
    return out


def shot_char(p, lt, dur, fi):
    u = U(lt, dur); e = ease_out(lt / 0.45)
    if p.get("img"):
        out = shot_kb(dict(img=p["img"], move="right", amt=0.1), lt, dur, fi)
        out = out * np.clip(1.05 - np.linspace(0, 0.55, W, dtype=np.float32)[None, :, None] * 0, 0, 1)
        f = clip_frame(p["clip"], lt, dur)
        sq = cv2.resize(f, (560, 560), interpolation=cv2.INTER_AREA) if f.shape[0] == f.shape[1] else \
            cv2.resize(f[:, (f.shape[1] - f.shape[0]) // 2:(f.shape[1] + f.shape[0]) // 2], (560, 560), interpolation=cv2.INTER_AREA)
        out = blit(out, card(sq, r=18, border=4), 1530 + (1 - e) * 500, 430, 1.0, 1.0, 3.0)
    else:
        f = clip_frame(p["clip"], lt, dur)
        out = fast_blur(cv2.resize(f, (W, W))[(W - H) // 2:(W - H) // 2 + H], 30) * 0.45
        sq = cv2.resize(f, (860, 860), interpolation=cv2.INTER_AREA)
        out = blit(out, card(sq, r=20, border=3), 700 + (1 - e) * -300, H / 2, 1.0 + 0.04 * u, 1.0, -2)
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    out = out * (1 - 0.55 * np.clip((g - 0.6) / 0.4, 0, 1))
    name = text3d(p["name"], "anton", 112, (255, 240, 200), (255, 80, 170), 10, (70, 20, 120), (255, 64, 160), 14, 0.6)
    out = blit(out, name, 130 + (1 - e) * -100, 935, 1.0, e, 0, anchor="l")
    bar_w = int(380 * e)
    cv2.rectangle(out, (140, 858), (140 + bar_w, 866), tuple(float(c) for c in YELLOW), -1)
    return out


# ═══════════════════════════════════════════════════════════ HABILLAGES / MOTION DESIGN
def shot_title(p, lt, dur, fi):
    u = U(lt, dur)
    k = p.get("bg", "cover")
    base = fit_rect(src_aspect(k))
    bgv = view(img(k, 1920), move_rect(base, "in", u, 0.1))
    out = fast_blur(bgv, 10) * 0.42 + fx.sunset_bg(0) * 0.22
    out = light_leak(out, clamp(lt / max(1, dur)), True, 0.8)
    e = ease_back(lt / 0.65, 1.4)
    t1 = text3d(p["t1"], "anton", 300, (255, 236, 140), (255, 60, 160), 26, (70, 18, 120), (255, 64, 160), 30, 0.6)
    out = blit(out, t1, W / 2, 470 - (30 if p.get("t2") else 0), (0.55 + 0.45 * e) * (1 + 0.05 * u), clamp(lt / 0.25))
    if p.get("t2"):
        t2 = plain_text(p["t2"], "bebas", 74, (255, 255, 255), spacing=10, glow=CYAN_T, glow_r=10)
        e2 = ease_out((lt - 0.5) / 0.6)
        out = blit(out, t2, W / 2, 730 + (1 - e2) * 40, 1.0, e2)
        lw = int(520 * e2)
        cv2.line(out, (W // 2 - lw, 790), (W // 2 + lw, 790), tuple(float(c) for c in PINK), 3, cv2.LINE_AA)
    return out


def shot_chapter(p, lt, dur, fi):
    out = synth_grid(lt, 0.64)
    out = out * 0.85
    e = ease_back(lt / 0.6, 1.3)
    num = text3d(p["num"], "monoton", 230, (130, 235, 255), (255, 80, 200), 0, (0, 0, 0), (60, 200, 255), 22, 0.0)
    out = blit(out, num, W / 2, 300 - (1 - e) * 200, 1.0, clamp(lt / 0.3))
    e2 = ease_out((lt - 0.25) / 0.6)
    name = text3d(p["name"], "anton", 150, (255, 236, 140), (255, 60, 160), 16, (70, 18, 120), (255, 64, 160), 20, 0.6)
    out = blit(out, name, W / 2 + (1 - e2) * 300, 540, 1.0 + 0.03 * lt / dur, e2)
    tag = plain_text("CHAPITRE", "bebas", 44, (255, 255, 255), spacing=14)
    out = blit(out, tag, W / 2, 180 - 10, 1.0, ease_out((lt - 0.1) / 0.5))
    return out


def shot_year(p, lt, dur, fi):
    out = bg_blur(p["img"], lt, dur, 0.5, 6)
    e = ease_out(lt / 0.5, 4)
    yr = text3d(p["year"], "anton", 340, (255, 255, 255), (255, 120, 200), 24, (80, 20, 120), (255, 64, 160), 28, 0.6)
    out = blit(out, yr, W / 2, 470, 1.35 - 0.35 * e + 0.04 * U(lt, dur), clamp(lt / 0.2))
    lab = plain_text(p["label"], "bebas", 78, YEL_T, spacing=10, glow=PINK_T, glow_r=8)
    e2 = ease_out((lt - 0.35) / 0.5)
    out = blit(out, lab, W / 2, 740 + (1 - e2) * 30, 1.0, e2)
    return out


def shot_counter(p, lt, dur, fi):
    out = bg_blur(p["img"], lt, dur, 0.45, 8)
    v = int(round(p["value"] * ease_out(lt / 1.5, 3)))
    txt = f"{p.get('pre', '')}{v}{p.get('suffix', '')}"
    t = text3d(txt, "anton", 300, (130, 240, 255), (90, 110, 255), 20, (30, 20, 90), (60, 200, 255), 26, 0.6)
    out = blit(out, t, W / 2, 460, 1.0 + 0.04 * U(lt, dur), clamp(lt / 0.2))
    lab = plain_text(p["label"], "bebas", 66, WHITE_T, spacing=8, glow=PINK_T, glow_r=8)
    out = blit(out, lab, W / 2, 720, 1.0, ease_out((lt - 0.3) / 0.5))
    return out


def shot_glitchwall(p, lt, dur, fi):
    keys = p["imgs"]; seg = int(max(0, lt) / 0.42)
    out = np.zeros((H, W, 3), np.float32)
    tw, th = W // 3, H // 2
    for i in range(6):
        k = keys[(i + seg) % len(keys)]
        cell = view(img(k, 1920), fit_rect(src_aspect(k), (0.1, 0, 0.9, 1)), out=(tw, th), interp=cv2.INTER_AREA)
        y0 = (i // 3) * th; x0 = (i % 3) * tw
        out[y0:y0 + th, x0:x0 + tw] = cell
        out[y0:y0 + 3, x0:x0 + tw] = 0; out[y0:y0 + th, x0:x0 + 3] = 0
    out = out * 0.8
    phase = (max(0, lt) % 0.42) / 0.42
    amt = 1.0 if phase < 0.25 else 0.25
    out = glitch_blocks(out, fi // 2, amt)
    return out


def shot_dates(p, lt, dur, fi):
    out = synth_grid(lt * 0.5, 0.78, CYAN, alpha=0.5, sun=False) * 0.6
    y = 520; x0, x1 = 300, 1620
    e = ease_out(lt / 0.6)
    cv2.line(out, (x0, y), (int(x0 + (x1 - x0) * e), y), tuple(float(c) for c in WHITE * 0.8), 4, cv2.LINE_AA)
    nodes = [(450, "AUTOMNE 2025", True), (960, "26 MAI 2026", True), (1470, "19 NOV. 2026", False)]
    step = dur / 3.3
    for i, (x, lab, struck) in enumerate(nodes):
        t0 = 0.3 + i * step
        ei = ease_back((lt - t0) / 0.45, 1.5)
        if lt < t0: continue
        col = PINK if not struck else WHITE * 0.85
        cv2.circle(out, (x, y), int(18 * ei), tuple(float(c) for c in col), -1, cv2.LINE_AA)
        big = not struck
        t = text3d(lab, "anton", 110 if big else 80, (255, 236, 140) if big else (230, 230, 240),
                   (255, 60, 160) if big else (170, 170, 200), 12 if big else 6, (70, 18, 120), (255, 64, 160) if big else None,
                   22 if big else 0, 0.5)
        out = blit(out, t, x, y - 110, ei, clamp((lt - t0) / 0.25))
        if struck:
            es = ease_out((lt - t0 - step * 0.55) / 0.3)
            if es > 0:
                w = int(170 * es)
                cv2.line(out, (x - 170, y - 105), (x - 170 + 2 * w, y - 115), (0.25, 0.2, 1.0), 9, cv2.LINE_AA)
                st = plain_text("REPORTÉ", "bebas", 52, (255, 90, 90), spacing=6)
                out = blit(out, st, x, y + 80, 1.0, es, -6)
    return out


def shot_num(p, lt, dur, fi):
    u = U(lt, dur); e = ease_out(lt / 0.55)
    right = shot_kb(dict(img=p["img"], move="in", amt=0.12), lt, dur, fi)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = 820 + (yy - H) * -0.22 + (1 - e) * 900
    m = np.clip((xx - edge) / 2, 0, 1)[..., None]
    panel = fx.sunset_bg(1) * 0.9
    out = panel * (1 - m) + right * m
    out = out + np.exp(-((xx - edge) ** 2) / 40)[..., None] * PINK * 0.9
    n = text3d(p["n"], "anton", 520, (130, 240, 255), (255, 70, 200), 30, (50, 15, 110), (255, 64, 160), 30, 0.6)
    out = blit(out, n, 400, 470, (0.6 + 0.4 * ease_back(lt / 0.5, 1.5)) * (1 + 0.04 * u), clamp(lt / 0.2))
    lab = text3d(p["label"], "anton", 92, (255, 255, 255), (255, 214, 102), 8, (70, 18, 120), None, 0, 0.7)
    out = blit(out, lab, 120, 900, 1.0, ease_out((lt - 0.25) / 0.5), anchor="l")
    return out


def shot_list(p, lt, dur, fi):
    out = bg_blur(p["img"], lt, dur, 0.4, 10)
    items = p["items"]; n = len(items)
    for i, it in enumerate(items):
        t0 = 0.25 + i * (dur - 0.8) / n
        e = ease_out((lt - t0) / 0.45)
        if e <= 0: continue
        y = 300 + i * 150
        cx = 330 + (1 - e) * -120
        cv2.circle(out, (int(cx), y), 34, tuple(float(c) for c in PINK), -1, cv2.LINE_AA)
        cv2.polylines(out, [np.array([[cx - 15, y + 2], [cx - 4, y + 14], [cx + 17, y - 12]], np.int32)], False,
                      (1.0, 1.0, 1.0), 6, cv2.LINE_AA)
        t = text3d(it, "anton", 92, (255, 255, 255), (130, 235, 255), 7, (50, 15, 110), None, 0, 0.7)
        out = blit(out, t, cx + 70, y, 1.0, e, anchor="l")
    return out


def shot_platform(p, lt, dur, fi):
    out = synth_grid(lt, 0.7, CYAN, alpha=0.6, sun=False) * 0.75
    badges = [("PS5", 560, False), ("XBOX SERIES", 1160, False), ("PC", 1660, True)]
    for i, (lab, x, crossed) in enumerate(badges):
        e = ease_back((lt - 0.2 - i * 0.35) / 0.45, 1.4)
        if e <= 0: continue
        t = text3d(lab, "anton", 150, (255, 255, 255) if not crossed else (150, 150, 170),
                   (130, 235, 255) if not crossed else (110, 110, 130), 14, (40, 20, 100), (60, 200, 255) if not crossed else None,
                   20, 0.6)
        out = blit(out, t, x, 470, e, clamp(e))
        if crossed and lt > 1.0:
            es = ease_out((lt - 1.0) / 0.3)
            cv2.line(out, (x - 120, 540), (x - 120 + int(240 * es), 400), (0.25, 0.25, 1.0), 12, cv2.LINE_AA)
            nt = plain_text("PAS AU LANCEMENT", "bebas", 46, (255, 120, 120), spacing=4)
            out = blit(out, nt, x, 640, 1.0, es)
    return out


def shot_meme(p, lt, dur, fi):
    out = bg_blur(p["img"], lt, dur, 0.35, 8)
    top = text3d("« GTA 6 SORTIRA AVANT…", "anton", 110, (255, 255, 255), (255, 214, 102), 8, (70, 18, 120), (255, 64, 160), 14, 0.6)
    out = blit(out, top, W / 2, 360, 1.0, ease_out(lt / 0.4))
    opts = ["…LA FIN DE MES ÉTUDES »", "…MON PERMIS DE CONDUIRE »", "…LE PROCHAIN ÉTÉ »", "…MA RETRAITE »"]
    end_t = dur * 0.72
    if lt < end_t:
        i = int(max(0, lt - 0.5) / max(0.4, (end_t - 0.5) / len(opts))) % len(opts)
        t = plain_text(opts[i], "bebas", 92, CYAN_T, spacing=4, glow=PURP_T, glow_r=8)
        out = blit(out, t, W / 2, 560, 1.0, clamp((lt - 0.4) / 0.2))
        ph = (lt * 30) % 12
        if ph < 2: out = glitch_blocks(out, fi, 0.6)
    else:
        e = ease_back((lt - end_t) / 0.4, 2.0)
        st = text3d("SORTIE : 19.11.2026", "anton", 130, (255, 236, 140), (255, 60, 160), 12, (70, 18, 120), (255, 64, 160), 18, 0.6)
        out = blit(out, st, W / 2, 600, 1.3 - 0.3 * e, clamp(e), -4)
    return out


def shot_mapgrid(p, lt, dur, fi):
    keys = p["imgs"]; u = U(lt, dur)
    BW, BH = 2600, 1300
    board = _map_board(tuple(keys))
    cx = lerp(0.36, 0.64, ease_io(u)) * BW; cy = lerp(0.45, 0.55, u) * BH
    out = view(board, (cx / BW, cy / BH, 0.78 * (1 - 0.08 * u)))
    # ligne de balayage
    sy = int((lt * 380) % (H + 200)) - 100
    yy = np.arange(H, dtype=np.float32)[:, None, None]
    out = out + np.exp(-((yy - sy) ** 2) / 300) * CYAN * 0.5
    return np.clip(out, 0, 1)


@lru_cache(maxsize=2)
def _map_board(keys):
    BW, BH = 2600, 1300
    b = np.zeros((BH, BW, 3), np.float32); b[:] = NAVY
    tw, th = BW // 3, BH // 2
    for i, k in enumerate(keys[:6]):
        cell = cv2.resize(img(k, 1920), (tw - 16, th - 16), interpolation=cv2.INTER_AREA)
        y0 = (i // 3) * th + 8; x0 = (i % 3) * tw + 8
        b[y0:y0 + th - 16, x0:x0 + tw - 16] = cell * 0.8
    for x in range(0, BW, 100): cv2.line(b, (x, 0), (x, BH), tuple(float(c) for c in CYAN * 0.35), 1)
    for y in range(0, BH, 100): cv2.line(b, (0, y), (BW, y), tuple(float(c) for c in CYAN * 0.35), 1)
    for (x, y) in [(500, 420), (1300, 300), (2100, 500), (700, 1000), (1600, 950), (2300, 1100)]:
        cv2.circle(b, (x, y), 16, tuple(float(c) for c in PINK), -1, cv2.LINE_AA)
        cv2.circle(b, (x, y), 30, tuple(float(c) for c in PINK), 2, cv2.LINE_AA)
    return b


def shot_countdown(p, lt, dur, fi):
    out = synth_grid(lt, 0.66)
    seq = ["J-3", "J-2", "J-1", "J-0"]
    step = min(0.42, (dur - 1.0) / 4)
    i = min(3, int(max(0, lt) / step))
    lt_i = lt - i * step
    e = ease_back(lt_i / 0.25, 2.0)
    t = text3d(seq[i], "anton", 360, (255, 236, 140), (255, 60, 160), 26, (70, 18, 120), (255, 64, 160), 30, 0.6)
    out = blit(out, t, W / 2, 450, 1.3 - 0.3 * e, 1.0)
    if i == 3:
        e2 = ease_out((lt_i - 0.15) / 0.4)
        d = plain_text("19 NOVEMBRE 2026", "bebas", 90, WHITE_T, spacing=10, glow=CYAN_T, glow_r=10)
        out = blit(out, d, W / 2, 760, 1.0, e2)
    return out


def _bokeh(lt):
    out = fx.sunset_bg(1) * 0.55
    g = np.random.default_rng(5)
    lay = np.zeros((H // 4, W // 4, 3), np.float32)
    for k in range(26):
        x = (g.random() * W / 4 + lt * (3 + g.random() * 6)) % (W / 4); y = g.random() * H / 4
        r = int(6 + g.random() * 22); col = [PINK, CYAN, PURPLE, ORANGE][k % 4]
        cv2.circle(lay, (int(x), int(y)), r, tuple(float(c) for c in col * 0.35), -1, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 3)
    return out + cv2.resize(lay, (W, H))


@lru_cache(maxsize=1)
def _tile():
    c = img("cover", 1920)
    h, w = c.shape[:2]
    t = c[int(h * 0.05):int(h * 0.95), int(w * 0.5 - h * 0.36):int(w * 0.5 + h * 0.36)]
    t = cv2.resize(t, (520, 650), interpolation=cv2.INTER_AREA)
    return card(t, r=26, border=0)


def _bar(out, x, y, w, prog, h=18):
    cv2.rectangle(out, (x, y), (x + w, y + h), (0.25, 0.18, 0.22), -1, cv2.LINE_AA)
    pw = int(w * clamp(prog))
    if pw > 2:
        grad = np.linspace(0, 1, pw, dtype=np.float32)[None, :, None]
        out[y:y + h, x:x + pw] = CYAN * (1 - grad) + PINK * grad
        glow = np.zeros((h + 60, pw + 60, 3), np.float32)
        glow[30:30 + h, 30:30 + pw] = PINK * 0.8
        glow = cv2.GaussianBlur(glow, (0, 0), 12)
        y0, x0 = y - 30, x - 30
        sl = out[max(0, y0):y0 + h + 60, max(0, x0):x0 + pw + 60]
        sl += glow[:sl.shape[0], :sl.shape[1]] * 0.8
    return out


def shot_ps5(p, lt, dur, fi):
    """Habillage graphique du préchargement (illustration, pas une capture d'interface).
    Si de vraies captures existent dans ps5_captures/<phase>.mp4, elles sont utilisées à la place."""
    ph = p.get("phase", "dl")
    cap = PS5_DIR / f"{ph}.mp4"
    if cap.exists():
        cv = cv2.VideoCapture(str(cap)); n = int(cv.get(cv2.CAP_PROP_FRAME_COUNT))
        cv.set(cv2.CAP_PROP_POS_FRAMES, int(clamp(lt, 0, dur) / dur * (n - 1))); ok, f = cv.read()
        if ok: return cv2.resize(f, (W, H)).astype(np.float32) / 255
    out = _bokeh(lt)
    u = U(lt, dur)
    if ph == "boot":
        e = ease_out(lt / 1.2)
        r = int(120 + 10 * math.sin(lt * 4))
        c = (W // 2, H // 2 - 40)
        lay = np.zeros((H, W, 3), np.float32)
        cv2.ellipse(lay, c, (r, r), -90, 40, 320, tuple(float(x) for x in CYAN), 12, cv2.LINE_AA)
        cv2.line(lay, (c[0], c[1] - r - 20), (c[0], c[1] - 30), tuple(float(x) for x in CYAN), 12, cv2.LINE_AA)
        out = out + (lay + fast_blur(lay, 14) * 1.5) * e
        burst = clamp((lt - dur * 0.55) / 0.6)
        if burst > 0:
            rr = int(140 + burst * 900)
            cv2.circle(out, c, rr, tuple(float(x) for x in PINK * (1 - burst)), 8, cv2.LINE_AA)
        t = plain_text("MISE SOUS TENSION", "bebas", 54, WHITE_T, spacing=12)
        out = blit(out, t, W / 2, 820, 1.0, e)
        return np.clip(out, 0, 1)
    tile_x = 470 + (1 - ease_out(lt / 0.6)) * -200 if ph in ("page", "teaser") else 470
    out = blit(out, _tile(), tile_x, H / 2, 1.0 + 0.03 * u, clamp(lt / 0.3) if ph in ("page", "teaser") else 1.0)
    title = text3d("GRAND THEFT AUTO VI", "anton", 96, (255, 255, 255), (255, 214, 102), 6, (70, 18, 120), None, 0, 0.6)
    out = blit(out, title, 850, 330, 1.0, 1.0, anchor="l")
    if ph == "page":
        press = dur * 0.8
        pulse = 1 + 0.03 * math.sin(lt * 6)
        pressed = lt > press
        sc = (0.94 if pressed and lt < press + 0.15 else 1.0) * (pulse if not pressed else 1)
        bw, bh = 560, 120
        btn = np.zeros((bh, bw, 3), np.float32)
        grad = np.linspace(0, 1, bw, dtype=np.float32)[None, :, None]
        btn[:] = PINK * (1 - grad) + ORANGE * grad if not pressed else CYAN * 0.8
        lab = plain_text("TÉLÉCHARGER" if not pressed else "TÉLÉCHARGEMENT…", "bebas", 64, WHITE_T, spacing=6, shadow=0.3)
        b = card(btn, r=60, border=0)
        out = blit(out, b, 850 + bw / 2, 560, sc, 1.0)
        out = blit(out, lab, 850 + bw / 2, 560, sc, 1.0)
        sub = plain_text("PRÉCHARGEMENT DISPONIBLE", "bebas", 46, (200, 200, 230), spacing=6)
        out = blit(out, sub, 850, 430, 1.0, 1.0, anchor="l")
        if pressed:
            out = light_leak(out, clamp((lt - press) / 0.8), False, 0.6)
        return np.clip(out, 0, 1)
    if ph in ("dl", "teaser"):
        prog = lerp(p.get("p0", 0.0), p.get("p1", 0.12), ease_io(clamp(lt / max(0.1, dur))))
        st = plain_text("PRÉCHARGEMENT EN COURS" + "." * (1 + int(lt * 2) % 3), "bebas", 50, (200, 200, 230), spacing=6)
        out = blit(out, st, 850, 440, 1.0, 1.0, anchor="l")
        out = _bar(out, 850, 560, 900, prog)
        pc = plain_text(f"{int(prog * 100)} %", "bebas", 140, WHITE_T, spacing=4, glow=PINK_T, glow_r=12)
        out = blit(out, pc, 850, 700, 1.0, 1.0, anchor="l")
        return np.clip(out, 0, 1)
    if ph == "done":
        prog = lerp(0.97, 1.0, ease_out(lt / 0.8))
        out = _bar(out, 850, 560, 900, prog)
        done = lt > 0.9
        st = plain_text("INSTALLATION TERMINÉE" if done else "FINALISATION…", "bebas", 50, YEL_T if done else (200, 200, 230), spacing=6)
        out = blit(out, st, 850, 440, 1.0, 1.0, anchor="l")
        pc = plain_text(f"{int(prog * 100)} %", "bebas", 140, WHITE_T, spacing=4, glow=PINK_T, glow_r=12)
        out = blit(out, pc, 850, 700, 1.0, 1.0, anchor="l")
        if done:
            e = ease_back((lt - 0.9) / 0.4, 2)
            c = (1600, 700)
            cv2.circle(out, c, int(70 * e), tuple(float(x) for x in PINK), -1, cv2.LINE_AA)
            if e > 0.5:
                cv2.polylines(out, [np.array([[c[0] - 30, c[1] + 2], [c[0] - 8, c[1] + 26], [c[0] + 34, c[1] - 24]], np.int32)],
                              False, (1.0, 1.0, 1.0), 10, cv2.LINE_AA)
            un = plain_text("DÉVERROUILLAGE : 19.11.2026", "bebas", 52, CYAN_T, spacing=6)
            out = blit(out, un, 850, 850, 1.0, ease_out((lt - 1.3) / 0.5), anchor="l")
            out = light_leak(out, clamp((lt - 0.9) / 1.2), True, 0.5)
        return np.clip(out, 0, 1)
    if ph == "locked":
        out = _bar(out, 850, 560, 900, 1.0)
        st = plain_text("PRÉCHARGÉ  ·  EN ATTENTE DE DÉVERROUILLAGE", "bebas", 50, YEL_T, spacing=5)
        out = blit(out, st, 850, 440, 1.0, 1.0, anchor="l")
        # cadenas
        c = (470, H // 2); s = 1 + 0.02 * math.sin(lt * 3)
        cv2.ellipse(out, (c[0], c[1] - 40), (int(55 * s), int(65 * s)), 0, 180, 360, (1, 1, 1), 16, cv2.LINE_AA)
        cv2.rectangle(out, (c[0] - 85, c[1] - 40), (c[0] + 85, c[1] + 90), tuple(float(x) for x in PINK), -1, cv2.LINE_AA)
        cv2.circle(out, (c[0], c[1] + 25), 16, (0.1, 0.05, 0.1), -1, cv2.LINE_AA)
        j = plain_text("J-2", "anton", 170, WHITE_T, glow=PINK_T, glow_r=14)
        out = blit(out, j, 850, 720, 1.0, ease_out(lt / 0.5), anchor="l")
        d = plain_text("19.11.2026", "bebas", 80, CYAN_T, spacing=8)
        out = blit(out, d, 1150, 735, 1.0, ease_out((lt - 0.3) / 0.5), anchor="l")
        return np.clip(out, 0, 1)
    return out


def shot_dl_teaser(p, lt, dur, fi):
    return shot_ps5(dict(phase="teaser", p0=0.0, p1=0.08), lt, dur, fi)


def shot_next(p, lt, dur, fi):
    out = synth_grid(lt, 0.72, PURPLE * 0.5 + PINK * 0.5, alpha=0.5) * 0.7
    e = ease_out(lt / 0.5)
    thumb = card_sprite(p["img"], 900, 506)
    out = blit(out, thumb, 620 + (1 - e) * -500, 520, 1.0 + 0.03 * U(lt, dur), 1.0, -2)
    rib = plain_text("BIENTÔT SUR LA CHAÎNE", "bebas", 46, (20, 10, 40), spacing=6, shadow=0)
    box = np.zeros((70, 480, 3), np.float32); box[:] = YELLOW
    out = blit(out, card(box, r=10, border=0), 420 + (1 - e) * -500, 250, 1.0, 1.0, -2)
    out = blit(out, rib, 420 + (1 - e) * -500, 250, 1.0, 1.0, -2)
    n = text3d(f"#{p['n']}", "anton", 200, (130, 240, 255), (255, 70, 200), 16, (50, 15, 110), (60, 200, 255), 22, 0.6)
    out = blit(out, n, 1180, 360, 1.0, ease_out((lt - 0.15) / 0.4), anchor="l")
    words = p["label"].split(" ")
    l1 = " ".join(words[:2]); l2 = " ".join(words[2:])
    for i, l in enumerate([l1, l2]):
        if not l: continue
        t = text3d(l, "anton", 96, (255, 255, 255), (255, 214, 102), 8, (70, 18, 120), None, 0, 0.7)
        out = blit(out, t, 1180 + (1 - ease_out((lt - 0.25 - i * 0.1) / 0.45)) * 200, 560 + i * 115, 1.0,
                   ease_out((lt - 0.25 - i * 0.1) / 0.45), anchor="l")
    return out


def _bell(out, c, s, ang, col):
    lay = np.zeros((H, W, 3), np.float32)
    M = cv2.getRotationMatrix2D(c, ang, 1)
    pts = np.array([[-60, 40], [-50, -20], [-30, -55], [0, -65], [30, -55], [50, -20], [60, 40], [75, 55], [-75, 55]], np.float32) * s
    pts = (np.hstack([pts + np.array(c, np.float32), np.ones((len(pts), 1), np.float32)]) @ M.T).astype(np.int32)
    cv2.fillPoly(lay, [pts], tuple(float(x) for x in col), cv2.LINE_AA)
    cl = (M @ np.array([c[0], c[1] + 72 * s, 1])).astype(int)
    cv2.circle(lay, tuple(cl), int(16 * s), tuple(float(x) for x in col), -1, cv2.LINE_AA)
    m = (lay.max(2) > 0)[..., None]
    return out * (1 - m) + lay * m


def shot_subscribe(p, lt, dur, fi):
    out = bg_blur(p["img"], lt, dur, 0.4, 10)
    click = dur * 0.22; ring = dur * 0.36
    subbed = lt > click
    bw, bh = 640, 150
    btn = np.zeros((bh, bw, 3), np.float32)
    grad = np.linspace(0, 1, bw, dtype=np.float32)[None, :, None]
    btn[:] = (PINK * (1 - grad) + ORANGE * grad) if not subbed else np.array([0.35, 0.3, 0.33], np.float32)
    sc = (0.92 if click < lt < click + 0.15 else 1.0) * ease_back(lt / 0.5, 1.6)
    out = blit(out, card(btn, r=75, border=0), 860, 540, sc, 1.0)
    lab = plain_text("S'ABONNER" if not subbed else "ABONNÉ !", "anton", 84, WHITE_T, spacing=4, shadow=0.3)
    out = blit(out, lab, 860, 536, sc, 1.0)
    ang = 22 * math.sin((lt - ring) * 18) * math.exp(-(lt - ring) * 2.5) if lt > ring else 0
    out = _bell(out, (1340, 540), 1.15 * ease_back((lt - 0.2) / 0.5, 1.6), ang, YELLOW if lt > ring else WHITE)
    # curseur
    cx = lerp(1300, 880, ease_io(lt / click)) if lt < click else lerp(880, 1360, ease_io((lt - click - 0.3) / (ring - click - 0.3)))
    cy = lerp(800, 560, ease_io(lt / click)) if lt < click else lerp(560, 580, ease_io((lt - click - 0.3) / (ring - click - 0.3)))
    if lt < ring + 0.6:
        pts = np.array([[0, 0], [0, 46], [12, 35], [22, 58], [30, 54], [20, 32], [36, 32]], np.int32) + np.array([int(cx), int(cy)])
        cv2.fillPoly(out, [pts], (1, 1, 1), cv2.LINE_AA); cv2.polylines(out, [pts], True, (0, 0, 0), 2, cv2.LINE_AA)
    return np.clip(out, 0, 1)


def shot_endcard(p, lt, dur, fi):
    out = synth_grid(lt, 0.8, PINK, alpha=0.6) * 0.8
    t = text3d("MERCI D'AVOIR REGARDÉ", "anton", 96, (255, 236, 140), (255, 60, 160), 10, (70, 18, 120), (255, 64, 160), 16, 0.6)
    out = blit(out, t, W / 2, 140, 1.0, ease_out(lt / 0.5))
    for i, (x, k, lab) in enumerate([(530, "vs2", "VIDÉO SUIVANTE"), (1390, "ue_squalo", "PLAYLIST GTA 6")]):
        e = ease_out((lt - 0.2 - i * 0.15) / 0.5)
        th = card_sprite(k, 760, 428, border=5)
        out = blit(out, th, x, 520 + (1 - e) * 60, 1.0, e * 0.85)
        l = plain_text(lab, "bebas", 50, WHITE_T, spacing=8, glow=PINK_T, glow_r=8)
        out = blit(out, l, x, 780, 1.0, e)
    e = ease_back((lt - 0.6) / 0.5, 1.5)
    cv2.circle(out, (W // 2, 930), int(80 * clamp(e, 0, 1.2)), tuple(float(c) for c in PINK), 6, cv2.LINE_AA)
    s = plain_text("ABONNE-TOI", "bebas", 40, WHITE_T, spacing=4)
    out = blit(out, s, W / 2, 930, 1.0, clamp(e))
    return np.clip(out, 0, 1)


SHOTS = dict(kb=shot_kb, para=shot_para, stack=shot_stack, loc=shot_loc, hero=shot_hero, split=shot_split,
             reveal=shot_reveal, clip=shot_clip, char=shot_char, title=shot_title, chapter=shot_chapter,
             year=shot_year, counter=shot_counter, glitchwall=shot_glitchwall, dates=shot_dates, num=shot_num,
             list=shot_list, platform=shot_platform, meme=shot_meme, mapgrid=shot_mapgrid,
             countdown=shot_countdown, ps5=shot_ps5, dl_teaser=shot_dl_teaser, next=shot_next,
             subscribe=shot_subscribe, endcard=shot_endcard)


# ═══════════════════════════════════════════════════════════ TRANSITIONS
def transition(kind, a_fn, b_fn, p, fi):
    """p ∈ [0,1] : progression de la transition. a_fn/b_fn : fonctions qui rendent le plan A/B."""
    if kind == "xfade":
        return cv2.addWeighted(a_fn(), 1 - ease_io(p), b_fn(), ease_io(p), 0)
    if kind == "fade_soft":
        k = 1 - 0.65 * math.sin(math.pi * p)
        return (a_fn() if p < 0.5 else b_fn()) * k if abs(p - 0.5) > 0.12 else \
            cv2.addWeighted(a_fn(), 1 - (p - 0.38) / 0.24, b_fn(), (p - 0.38) / 0.24, 0) * k
    if kind == "fade":
        k = abs(1 - 2 * p) ** 1.2
        return (a_fn() if p < 0.5 else b_fn()) * k
    if kind == "dezoom_soft":
        e = ease_io(p)
        return cv2.addWeighted(scale_frame(a_fn(), 1 - 0.04 * e), 1 - e, scale_frame(b_fn(), 1.06 - 0.06 * e), e, 0)
    if kind == "whip":
        e = ease_in(p, 2) if p < 0.5 else 1 - ease_in(1 - p, 2)
        sp = math.sin(math.pi * p)
        if p < 0.5:
            f = scale_frame(a_fn(), 1.0, -e * W * 0.9); return motion_blur(f, 260 * sp)
        f = scale_frame(b_fn(), 1.0, (1 - e) * W * 0.9); return motion_blur(f, 260 * sp)
    if kind == "zoom":
        if p < 0.5:
            q = ease_in(p * 2, 2); f = zoom_blur(scale_frame(a_fn(), 1 + 0.6 * q), 0.25 * q)
        else:
            q = ease_out((p - 0.5) * 2, 2); f = zoom_blur(scale_frame(b_fn(), 1.4 - 0.4 * q), 0.25 * (1 - q))
        fl = max(0.0, 1 - abs(p - 0.5) * 6)
        return np.clip(f + fl * 0.6, 0, 1)
    if kind == "dirblur":
        e = ease_io(p); sp = math.sin(math.pi * p)
        f = cv2.addWeighted(a_fn(), 1 - e, b_fn(), e, 0)
        return motion_blur(scale_frame(f, 1.0, 0, (0.5 - p) * 80), 200 * sp, horizontal=False)
    if kind == "light":
        e = ease_io(p)
        f = cv2.addWeighted(a_fn(), 1 - e, b_fn(), e, 0)
        f = light_leak(f, p, warm=(fi // 300) % 2 == 0, strength=1.4)
        return np.clip(f + max(0, 1 - abs(p - 0.5) * 3) * 0.35, 0, 1)
    if kind == "dezoom":
        if p < 0.5:
            q = ease_in(p * 2, 2); f = zoom_blur(scale_frame(a_fn(), 1 - 0.35 * q, border=cv2.BORDER_REFLECT), 0.12 * q)
        else:
            q = ease_out((p - 0.5) * 2, 2); f = zoom_blur(scale_frame(b_fn(), 1.25 - 0.25 * q), 0.15 * (1 - q))
        return f
    if kind == "glitch":
        f = a_fn() if p < 0.5 else b_fn()
        return glitch_blocks(f, fi, 1.0 - abs(p - 0.5))
    if kind == "flash":
        f = a_fn() if p < 0.45 else b_fn()
        fl = max(0.0, 1 - abs(p - 0.45) * 3.2)
        return np.clip(f + fl * 0.95, 0, 1)
    return a_fn() if p < 0.5 else b_fn()


# ═══════════════════════════════════════════════════════════ SOUS-TITRES DYNAMIQUES
def caption_sprite(text, style):
    if style == "big":
        return text3d(text, "anton", 128, (255, 236, 140), (255, 60, 160), 12, (70, 18, 120), (255, 64, 160), 18, 0.7)
    if style == "stat":
        return text3d(text, "anton", 170, (255, 255, 255), (130, 235, 255), 16, (50, 15, 110), (60, 200, 255), 22, 0.7)
    if style == "logo":
        return text3d(text.title() if text.isupper() and "&" not in text else text, "script", 150, (255, 140, 210),
                      (255, 60, 160), 8, (90, 20, 120), (255, 64, 160), 26, 0.6)
    if style == "warn":
        return text3d(text, "anton", 96, (255, 236, 140), (255, 190, 60), 8, (60, 30, 10), None, 0, 0.8)
    if style == "glitch":
        return text3d(text, "anton", 104, (255, 255, 255), (130, 235, 255), 8, (50, 15, 110), (255, 64, 160), 12, 0.7)
    if style == "place":
        return text3d(text, "anton", 110, (255, 255, 255), (130, 235, 255), 9, (50, 15, 110), (255, 64, 160), 14, 0.7)
    return plain_text(text, "mont", 52, WHITE_T, shadow=0.85, spacing=1, var="ExtraBold")


CAP_POS = dict(big=(W / 2, 830), stat=(W / 2, 540), logo=(W / 2, 520), warn=(W / 2, 880), glitch=(W / 2, 540),
               place=(W / 2, 860), sub=(W / 2, 935))


def draw_caption(frame, c, t, fi):
    lt = t - c["t0"]; dur = c["t1"] - c["t0"]
    if lt < 0 or lt > dur: return frame
    st = c["style"]
    spr = caption_sprite(c["text"], st)
    e_in = ease_back(lt / 0.32, 1.7); e_out = clamp((dur - lt) / 0.3)
    a = clamp(lt / 0.15) * e_out
    x, y = CAP_POS.get(st, CAP_POS["sub"])
    sc = (0.75 + 0.25 * e_in) * (1 + 0.025 * lt) if st != "sub" else 1.0
    if st == "sub":
        y = y + (1 - ease_out(lt / 0.3)) * 30
        pw = spr.shape[1] - 60; ph = 96
        pill = np.zeros((ph, pw, 3), np.float32); pill[:] = NAVY * 0.9
        pill[:, :10] = PINK
        frame = blit(frame, card(pill, r=14, border=0, shadow=False), x, y, 1.0, a * 0.82)
    if st == "warn":
        bw = spr.shape[1] - 40; box = np.zeros((130, bw, 3), np.float32); box[:] = (0.05, 0.05, 0.08)
        box[:8] = YELLOW; box[-8:] = YELLOW
        frame = blit(frame, card(box, r=8, border=0, shadow=True), x, y, sc, a * 0.9)
    if st == "glitch" and (fi % 9) < 2:
        frame = blit(frame, spr, x + 14, y, sc, a * 0.5)
    return blit(frame, spr, x, y, sc, a)


# ═══════════════════════════════════════════════════════════ RENDU D'UNE IMAGE
SHOT_LIST = EDL["shots"]
TRL = EDL["tr_len"]


def render_shot(i, t, fi):
    s = SHOT_LIST[i]
    return SHOTS[s["kind"]](s["p"], t - s["t0"], s["t1"] - s["t0"], fi).astype(np.float32)


def letterbox_amt(t):
    amt = 0.0
    intro = [s for s in SHOT_LIST if s["sec"] == "intro"]
    tz = next((s["t0"] for s in intro if s["kind"] == "dl_teaser"), 20)
    if t < tz: amt = min(ease_out(t / 1.2), clamp((tz - t) / 0.5))
    rv = [s for s in SHOT_LIST if s["kind"] == "reveal" and s["sec"] == "outro"]
    if rv and rv[0]["t0"] - 0.5 < t < rv[0]["t1"]: amt = min(ease_out((t - rv[0]["t0"] + 0.5) / 1.0), clamp((rv[0]["t1"] - t) / 0.6))
    return amt


GRAPHIC = {"chapter", "dates", "platform", "countdown", "ps5", "dl_teaser", "next", "endcard", "subscribe"}


def render_frame(fi):
    t = fi / FPS
    # plan courant
    i = 0
    while i + 1 < len(SHOT_LIST) and SHOT_LIST[i + 1]["t0"] <= t: i += 1
    frame = None
    # transition entrante (centrée sur le début du plan i) ou sortante (vers i+1)
    for j in (i, i + 1):
        if 0 < j < len(SHOT_LIST):
            tr = SHOT_LIST[j]["tr"]; L = TRL.get(tr, 0.0)
            t0 = SHOT_LIST[j]["t0"]
            if L > 0 and t0 - L / 2 <= t < t0 + L / 2:
                p = (t - (t0 - L / 2)) / L
                frame = transition(tr, lambda: render_shot(j - 1, t, fi), lambda: render_shot(j, t, fi), p, fi)
                break
    if frame is None:
        frame = render_shot(i, t, fi)
    if SHOT_LIST[i]["kind"] not in GRAPHIC:
        frame = grade(frame)
    frame = letterbox(frame, letterbox_amt(t))
    for c in EDL["caps"]:
        if c["t0"] <= t <= c["t1"]:
            frame = draw_caption(frame, c, t, fi)
    return finish(frame, fi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--pdir", default=str(ROOT / "build" / "preview"))
    a = ap.parse_args()
    if a.preview is not None:
        Path(a.pdir).mkdir(parents=True, exist_ok=True)
        for t in a.preview:
            f = render_frame(int(round(t * FPS)))
            cv2.imwrite(f"{a.pdir}/f_{t:07.2f}.jpg", (f * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
        return
    end = a.end if a.end is not None else int(math.ceil(EDL["total"] * FPS))
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p",
           "-x264-params", "keyint=60:min-keyint=30", a.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time; t0 = time.time()
    for fi in range(a.start, end):
        f = render_frame(fi)
        proc.stdin.write((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        if (fi - a.start) % 300 == 0:
            el = time.time() - t0; done = fi - a.start + 1
            print(f"[{a.out}] {done}/{end - a.start}  {el / done:.3f}s/img", flush=True)
    proc.stdin.close(); proc.wait()


if __name__ == "__main__":
    main()
