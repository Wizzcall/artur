"""
SHORT AUTONOME « GTA 6 DE MINUIT » — 1080×1920, 30 i/s, ~12 s.
Source : page GTA VI sur PS5 filmée au téléphone (1280×720), compte à rebours 00:00:10 → « Jouer au jeu ».
La vidéo d'origine est conservée à vitesse réelle (compte à rebours authentique), stabilisée, mise en
vertical avec fond agrandi/flouté ; habillage bande-annonce + bande-son originale calée sur le décompte.

    python minuit.py --src <dossier : stab.mp4 (vidstab), orig.wav>   [--preview t1 t2 ...]
    → ../WIZZCALL_GTA6_MINUIT_SHORT.mp4
"""
import argparse, math, subprocess, sys
from pathlib import Path
import numpy as np
import cv2
import soundfile as sf

ROOT = Path(__file__).resolve().parent
PROJ = ROOT.parent / "GTA6_PROJET_MONTAGE"
sys.path.insert(0, str(PROJ))
import fx  # noqa: E402

W, H = 1080, 1920
fx.W, fx.H = W, H
from fx import (PINK, ORANGE, YELLOW, PURPLE, NAVY, clamp, lerp, ease_out, ease_in, ease_io, ease_back,  # noqa: E402
                text3d, plain_text, blit, fast_blur, rgb_split, light_leak, zoom_blur)

FPS = 30
SRC_N = 331
SRC_END = SRC_N / FPS                       # 11,03 s
CHANGES = [0.37 + i for i in range(9)]      # 09, 08, … 01 apparaissent (relevé image par image)
ZERO = 9.13                                 # le bouton passe à « Jouer au jeu »
SWAP = 10.55                                # « GTA 6 EST ENFIN DISPONIBLE ! » → « RENDEZ-VOUS À VICE CITY »
HOLD_AT = 314 / FPS                         # la source s'assombrit ensuite (passage d'écran console) → image figée
TOTAL = SRC_END + 1.3                       # ~12,3 s : le temps de lire le texte final
CYS = 1060                                  # centre vertical de l'image à l'écran (laisse de la place aux textes)
SW, SH = 1280, 720


def ex(t, tau): return math.exp(-t / tau) if t >= 0 else 0.0


def digit(t): return 10 - sum(c <= t for c in CHANGES)


class Src:
    def __init__(self, p):
        cap = cv2.VideoCapture(str(p)); self.f = []
        while True:
            ok, f = cap.read()
            if not ok: break
            self.f.append(f)
    def at(self, t):
        return self.f[int(clamp(t * FPS, 0, len(self.f) - 1))].astype(np.float32) / 255


# ─────────────────────────────── caméra : (échelle, centre source x, centre source y)
def camera(t):
    if t < 2.0:                                         # gros plan Jason & Lucia, zoom lent
        u = ease_io(t / 2.0); return lerp(1.70, 1.90, u), lerp(770, 785, u), lerp(300, 280, u)
    a = (1.90, 785, 280)
    b = (0.92, 540 / 0.92, 360)                         # plan large : tout le compte à rebours visible
    if t < 2.6:
        u = ease_io((t - 2.0) / 0.6); return tuple(lerp(x, y, u) for x, y in zip(a, b))
    if t < 7.0:
        s = lerp(0.92, 0.98, (t - 2.6) / 4.4); return s, 540 / s, 360
    if t < ZERO:                                        # tension : on se rapproche du bouton
        u = ease_in((t - 7.0) / (ZERO - 7.0), 2); s = lerp(0.98, 1.16, u); return s, 540 / s, lerp(360, 420, u)
    c = (1.16, 540 / 1.16, 420); d = (1.25, 700, 330)
    if t < ZERO + 0.6:
        u = ease_io((t - ZERO) / 0.6); s, x, y = (lerp(p, q, u) for p, q in zip(c, d))
    else:
        u = (t - ZERO - 0.6) / (TOTAL - ZERO - 0.6); s, x, y = lerp(1.25, 1.42, u), lerp(700, 720, u), 330
    return s * (1 + 0.12 * ex(t - ZERO, 0.22)), x, y   # coup de zoom sur le zéro


def shake(t, fi):
    g = np.random.default_rng(fi)
    amp = 0.0
    if 7.0 <= t < ZERO: amp = 1.5 + 7 * ((t - 7.0) / (ZERO - 7.0)) ** 2
    amp += 26 * ex(t - ZERO, 0.28) + 10 * ex(t - SWAP, 0.15)
    amp += sum(4 * ex(t - c, 0.08) for c in CHANGES if c > 2)
    return g.uniform(-amp, amp), g.uniform(-amp, amp)


@__import__("functools").lru_cache(maxsize=1)
def tint():
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    return (PURPLE * (1 - y) + ORANGE * y * 0.8 + PINK * (1 - abs(y - 0.5) * 2) * 0.6).astype(np.float32)


@__import__("functools").lru_cache(maxsize=1)
def scrim():
    y = np.linspace(0, 1, H, dtype=np.float32)
    return np.clip(1 - y / 0.42, 0, 1)[:, None, None] ** 1.4


def compose(frame, t, fi):
    # fond : la même image agrandie et floutée (cadrée sur le couple) + teinte rose/violet/orange
    bs = H / SH
    M = np.array([[bs, 0, W / 2 - bs * 720], [0, bs, 0]], np.float32)
    bg = cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = fast_blur(bg, 30) * 0.40 + tint() * 0.22
    # image d'origine : étalonnée, jamais déformée (échelle uniforme)
    img = fx.grade(frame, sat=1.15)
    img = np.clip(img * np.array([0.97, 0.98, 1.05], np.float32) + 0.012, 0, 1)   # légère chaleur rose/orange
    s, cx, cy = camera(t); dx, dy = shake(t, fi)
    M = np.array([[s, 0, W / 2 - s * cx + dx], [0, s, CYS - s * cy + dy]], np.float32)
    lay = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    al = cv2.warpAffine(np.ones((SH, SW), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)
    sh = cv2.GaussianBlur(np.roll(al, 26, 0), (0, 0), 24)[..., None]
    out = out * (1 - 0.55 * sh)
    out = out * (1 - al[..., None]) + lay * al[..., None]
    edge = np.clip(al - cv2.erode(al, np.ones((5, 5), np.uint8)), 0, 1)[..., None]
    out = np.clip(out + edge * (PINK * 0.7 + ORANGE * 0.3), 0, 1)
    # voile sombre en haut pour la lisibilité des textes
    return out * (1 - 0.55 * scrim())


FIRE = None


def fire_sprite(size):
    global FIRE
    if FIRE is None:
        im = cv2.imread(str(ROOT / "fire.png"), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
        FIRE = np.dstack([im[..., :3], im[..., 3]])
    return cv2.resize(FIRE, (size, size), interpolation=cv2.INTER_AREA)


def texts(out, t, fi):
    # 0–2 s : « 13 ANS D'ATTENTE… »
    if t < 2.35:
        a = ease_out((t - 0.05) / 0.35, 4); o = clamp((2.35 - t) / 0.3)
        t1 = text3d("13 ANS", "anton", 330, (255, 236, 140), (255, 70, 150), 26, (80, 16, 110), (255, 64, 160), 30, 0.7)
        out = blit(out, t1, W / 2, 330, (1.6 - 0.6 * a) * (1 + 0.025 * t), clamp(a * 2) * o)
        b = ease_out((t - 0.45) / 0.35, 4)
        t2 = text3d("D'ATTENTE…", "anton", 165, (255, 255, 255), (255, 170, 110), 14, (80, 16, 110), (255, 120, 60), 20, 0.7)
        out = blit(out, t2, W / 2, 545 + (1 - b) * 40, 1.0 + 0.02 * t, b * o)
    # 2,2 s → zéro : secondes restantes en géant, qui « frappent » à chaque changement
    if 2.2 <= t < ZERO + 0.05:
        d = digit(t)
        last = max([c for c in CHANGES if c <= t] or [0])
        p = ease_out((t - last) / 0.22, 3) if last > 2 else 1.0
        heat = clamp((10 - d) / 9)
        top = (255, int(lerp(236, 200, heat)), int(lerp(140, 60, heat)))
        bot = (255, int(lerp(60, 70, heat)), int(lerp(160, 40, heat)))
        e = clamp((t - 2.2) / 0.3)
        spr = text3d(str(d), "anton", 380, top, bot, 30, (80, 16, 110), (255, int(lerp(64, 110, heat)), 60), 34, 0.7)
        out = blit(out, spr, W / 2, 400, (1.35 - 0.35 * p) * (1 + 0.05 * heat), e * (0.4 + 0.6 * p))
        lab = plain_text("SECONDES AVANT GTA 6", "bebas", 58, (255, 255, 255), spacing=8, glow=(255, 64, 160), glow_r=10)
        out = blit(out, lab, W / 2, 640, 1.0, e)
        low = plain_text("MINUIT  ·  PS5", "bebas", 64, (255, 214, 102), spacing=14, glow=(255, 110, 60), glow_r=10)
        out = blit(out, low, W / 2, 1490, 1.0, e * clamp((ZERO - t) / 0.2))
    # zéro → : « GTA 6 EST ENFIN DISPONIBLE ! »
    if ZERO <= t < SWAP + 0.25:
        o = clamp((SWAP + 0.25 - t) / 0.25)
        for i, (txt, size, top, bot, y) in enumerate([
                ("GTA 6", 300, (255, 236, 140), (255, 60, 160), 300),
                ("EST ENFIN", 140, (255, 255, 255), (255, 200, 230), 500),
                ("DISPONIBLE !", 170, (255, 200, 90), (255, 90, 40), 670)]):
            a = ease_out((t - ZERO - i * 0.09) / 0.22, 4)
            spr = text3d(txt, "anton", size, top, bot, 22 if i == 0 else 14, (80, 16, 110), (255, 64, 160) if i != 2 else (255, 110, 40), 26, 0.7)
            out = blit(out, spr, W / 2, y, (1.7 - 0.7 * a) * (1 + 0.02 * (t - ZERO)), clamp(a * 3) * o)
    # fin : « RENDEZ-VOUS À VICE CITY 🔥 »
    if t >= SWAP:
        a = ease_back((t - SWAP) / 0.35, 1.8); b = ease_back((t - SWAP - 0.12) / 0.4, 1.8)
        r1 = text3d("RENDEZ-VOUS À", "anton", 130, (255, 255, 255), (255, 200, 230), 12, (80, 16, 110), None, 0, 0.7)
        out = blit(out, r1, W / 2, 330, 0.6 + 0.4 * a, clamp(a))
        r2 = text3d("VICE CITY", "anton", 250, (255, 214, 110), (255, 60, 160), 24, (80, 16, 110), (255, 64, 160), 32, 0.7)
        out = blit(out, r2, W / 2 - 85, 545, (0.6 + 0.4 * b) * (1 + 0.02 * (t - SWAP)), clamp(b))
        c = ease_back((t - SWAP - 0.3) / 0.35, 2.2)
        if c > 0:
            out = blit(out, fire_sprite(190), W / 2 + 425, 530 - 6 * math.sin(t * 7), c, clamp(c), -8 * math.sin(t * 5))
    return out


def render(src, fi):
    t = fi / FPS
    out = compose(src.at(min(t, HOLD_AT)), t, fi)
    # effets de la séquence d'ouverture et du zéro
    if t < 0.25: out = out * ease_out(t / 0.25)                           # ouverture depuis le noir
    if 1.85 <= t < 2.35:                                                   # transition gros plan → plan large
        q = math.sin(math.pi * (t - 1.85) / 0.5); out = zoom_blur(out, 0.10 * q)
    if 7.0 <= t < ZERO:                                                    # tension : pulsation rouge
        k = ((t - 7.0) / (ZERO - 7.0)) ** 2
        out = np.clip(out + (ORANGE * 0.5 + PINK * 0.5) * 0.10 * k * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 4)), 0, 1)
    if ZERO - 0.12 <= t < ZERO:                                            # « suck-out » visuel avant l'impact
        out = out * 0.35
    fl = ex(t - ZERO, 0.13)
    if fl > 0.01:
        out = np.clip(rgb_split(out, 30 * fl) + 0.85 * fl, 0, 1)
    if ZERO <= t <= ZERO + 1.1: out = light_leak(out, (t - ZERO) / 1.1, True, 1.0)
    if SWAP - 0.05 <= t <= SWAP + 0.9: out = light_leak(out, (t - SWAP) / 0.9, False, 0.8)
    out = texts(out, t, fi)
    out = out * clamp((TOTAL - t) / 0.3)                                # fondu final (comme la source)
    return fx.finish(out, fi)


# ═════════════════════════════════════════ BANDE-SON (originale, calée sur le décompte)
def build_audio(src, out_wav):
    import audio as A
    SR = A.SR; N = int((TOTAL + 0.6) * SR)
    mus = np.zeros((N, 2)); fxb = np.zeros((N, 2))

    def add(buf, x, t, g=1.0): A.place(buf, x if x.ndim == 2 else A.stereo(x), t, g)
    # 0 s : « braam » de bande-annonce + boom
    n = int(2.4 * SR)
    br = sum(A.osc(A.mtof(m + det), n, "saw") for m in (26, 33, 38) for det in (-0.08, 0.0, 0.07))
    br = A.lp_sweep(br, 250 + 900 * np.exp(-np.arange(n) / (0.5 * SR))) * A.adsr(n, 0.04, 0.6, 0.55, 1.2)
    add(mus, A.reverb(A.norm(A.sat(br, 1.6), 0.9), 0.35, 3.0, 3000), 0.0, 0.75)
    add(fxb, A.sfx_boom(2.5, 60, 30, 0.6), 0.02, 0.9)
    # nappe qui monte de 0 au zéro (filtre qui s'ouvre, volume qui grimpe)
    d = ZERO; n = int(d * SR); u = np.arange(n) / n
    pad = A.pad_chord([50, 53, 57, 62], d + 0.2, cutoff=6000, att=1.5, rel=0.1)[:n]
    pad = np.stack([A.lp_sweep(pad[:, c], 350 + 3200 * u ** 2) for c in range(2)], 1) * (0.25 + 0.75 * u ** 1.5)[:, None]
    add(mus, pad, 0.0, 0.55)
    dr = A.drone(d, 38, 300)[:n] * (0.4 + 0.6 * u)[:, None]; add(mus, dr, 0.0, 0.6)
    # tic-tac calé sur le compte à rebours, de plus en plus présent
    def tick(f, dur=0.05):
        m = int(dur * SR); tt = np.arange(m) / SR
        x = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.012) + A.bp(np.random.default_rng(int(f)).standard_normal(m), 2000, 9000) * np.exp(-tt / 0.004) * 0.6
        return A.reverb(x * 0.6, 0.15, 0.5, 9000)
    TIC, TAC = tick(1900), tick(1250)
    for c in CHANGES:
        if c < 1.0: continue
        g = 0.35 + 0.65 * clamp((c - 1.37) / 5.6)
        add(fxb, TIC, c, g)
        if c + 0.5 < 7.0: add(fxb, TAC, c + 0.5, g * 0.85)
        add(mus, A.stereo(A.kick(1.4)), c, 0.25 + 0.45 * clamp((c - 2) / 5))          # pulsation grave
    # 7 s → zéro : accélération (tic-tac en doubles puis quadruples croches) + roulement + riser
    t = 7.37
    while t < ZERO - 0.15:
        step = 0.25 if t < 8.37 else 0.125
        add(fxb, TIC if round((t - 7.37) / step) % 2 == 0 else TAC, t, 0.9)
        add(mus, A.snare(False), t, 0.12 + 0.35 * clamp((t - 7.37) / 1.6))
        t += step
    for k, tb in enumerate(np.arange(7.37, ZERO - 0.2, 0.5)):
        add(mus, A.stereo(A.kick(1.6)), tb, 0.7); add(mus, A.stereo(A.kick(1.2)), tb + 0.18, 0.4)   # battement de cœur
    add(fxb, A.sfx_riser(2.2), ZERO - 0.12 - 2.2, 0.9)
    # « suck-out » : silence de 0,12 s juste avant l'impact
    i0, i1 = int((ZERO - 0.12) * SR), int(ZERO * SR)
    mus[i0:i1] *= np.linspace(1, 0, i1 - i0)[:, None] ** 3; fxb[i0:i1] *= np.linspace(1, 0, i1 - i0)[:, None] ** 3
    # ZÉRO : gros impact + crash + drop synthwave triomphant
    add(fxb, A.sfx_impact(), ZERO, 1.0); add(fxb, A.sfx_boom(3.0, 70, 28, 0.9), ZERO, 0.9)
    m = int(2.5 * SR); tt = np.arange(m) / SR
    crash = A.hp(np.random.default_rng(3).standard_normal(m), 5000) * np.exp(-tt / 0.8) * 0.35
    add(fxb, A.reverb(crash, 0.4, 2.0), ZERO, 0.8)
    tr = A.Track(TOTAL - ZERO + 1, 120)
    ch = ["Bb", "C", "Dm", "Dm"]
    A.chord_loop(tr, ch, 0, TOTAL - ZERO + 0.5, beats_per=2, cutoff=3800, gain=0.9, voices=7, att=0.02)
    A.bass_line(tr, ch, 0, TOTAL - ZERO + 0.3, [(p * 0.5, 0.45, p % 2) for p in range(4)], beats_per=2, cutoff=1200, gain=0.7)
    A.drum_pattern(tr, 0, TOTAL - ZERO + 0.3, kick_at=(0, 1, 2, 3), snare_at=(1, 3), hats=0.25, gain=0.9, clapz=True, open_hat=True)
    A.arp_line(tr, ch, 0, TOTAL - ZERO + 0.3, step=0.25, beats_per=2, cutoff=4200, gain=0.3, oct=1)
    drop = A.finish(tr, dict(drums=0.9, bass=0.8, pad=0.75, arp=0.8, lead=0, fx=1), pump=0.4)
    add(mus, A.norm(drop, 0.9), ZERO, 0.85)
    add(fxb, A.sfx_whoosh(0.6, 300, 6000), SWAP - 0.3, 0.7); add(fxb, A.sfx_shimmer(), SWAP, 0.6)
    add(fxb, A.sfx_impact_s(), SWAP, 0.6)
    # son d'origine conservé (ambiance + bips de la console), synchronisé
    o, sr = sf.read(src / "orig.wav", always_2d=True)
    o = o / (np.sqrt((o ** 2).mean()) + 1e-9) * 10 ** (-30 / 20)
    L = min(len(o), int(SRC_END * SR)); org = np.zeros((N, 2)); org[:L] = o[:L]
    mix = A.norm(mus, 0.6) * 1.0 + fxb * 0.55 + org
    end = int(TOTAL * SR); f = int(0.5 * SR)
    mix[end - f:end] *= np.linspace(1, 0.2, f)[:, None]; mix[end:] *= 0
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    sf.write(out_wav, mix[:end + int(0.05 * SR)].astype(np.float32), SR)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args(); src = Path(a.src); S = Src(src / "stab.mp4")
    if a.preview is not None:
        for t in a.preview:
            cv2.imwrite(str(src / f"pv_{t:05.2f}.jpg"), (render(S, int(round(t * FPS))) * 255).astype(np.uint8),
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
        return
    build_audio(src, src / "mix.wav")
    vid = src / "video.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", str(vid)], stdin=subprocess.PIPE)
    for fi in range(int(math.ceil(TOTAL * FPS))):
        p.stdin.write((np.clip(render(S, fi), 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vid), "-i", str(src / "mix.wav"), "-map", "0:v", "-map", "1:a",
                    "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", str(ROOT.parent / "WIZZCALL_GTA6_MINUIT_SHORT.mp4")], check=True)
    print("ok", round(TOTAL, 2), "s")


if __name__ == "__main__":
    main()
