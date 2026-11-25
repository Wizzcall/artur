"""
GTA 6 — EDIT « FLICKER BOOMERANG » (réplique du modèle CapCut) · musique SLOWED
9:16 · 1080×1920 · 30 i/s · ~20 s

STRUCTURE
  1. Intro SANS musique (3,0 s) : logo VI (boomerang) ──fondu──▶ Lucia en voiture (boomerang),
     son d'origine des clips
  2. Edit sur la musique slowed (17,1 s) : réplique exacte des transitions du modèle CapCut

BOOMERANG (« reverse fondu en arrière ») : sur CHAQUE clip, l'image part en avant pendant la
lumière, puis se rembobine en arrière (×1,5) pendant le fondu au noir. Le clip suivant sur
le même plan reprend un peu plus loin, pour que l'action progresse.

TRANSITIONS DU MODÈLE (relevées sur ses 437 images : luminance + saturation)
  · flicker : chaque plan arrive sur le beat en pleine lumière puis tombe au noir,
    alternance couleur / noir & blanc
  · balayage lumineux blanc + glitch en tranches     (modèle 4,87 → 5,30 s)
  · flicker négatif → explosion radiale arc-en-ciel  (modèle 7,27 → 7,63 s et 12,17 → 12,50 s)
  · strobe                                           (modèle 9,40 → 9,97 s et 13,53 → 14,10 s)
  · sortie en zoom flou                              (modèle 14,13 → fin)

Slowed = vitesse ET hauteur × SLOW (0,85) + reverb ; la timeline du modèle est étirée du
même facteur → chaque effet reste sur son temps.

USAGE
    python edit.py --source GTA6_VIDEO_FINALE_SANS_VOIX.mp4 --music modele_capcut.mp4
OUTPUT : WIZZCALL_GTA6_EDIT_SLOWED.mp4
"""

import argparse, os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter

W, H, FPS = 1080, 1920, 30
SLOW = 0.85                     # slowed : 0,85× vitesse + hauteur
TPL_FRAMES = 437                # durée du modèle : 437 images à 30 i/s
OUT = "WIZZCALL_GTA6_EDIT_SLOWED.mp4"
FWD = 0.6                       # boomerang : 60 % du plan en avant, 40 % en arrière (×1,5)

# Zone de la « carte » vidéo des clips personnages dans la vidéo longue (x 512→1406, y 92→986)
CARD = (530, 110, 860, 860)

# ── Plans de la vidéo longue : début (s), cadrage, centre horizontal ──
#    "full" = recadrage 9:16 de l'image 16:9 · "card" = zoom dans la carte vidéo centrale
CLIPS = {
    # vrais clips vidéo
    "vi":      (4.60,   "full", 0.50),   # reveal du logo VI
    "lucia_v": (225.00, "full", 0.62),   # Lucia en voiture, la nuit, arme
    "jason_v": (306.40, "full", 0.56),   # Jason au bandana, braquage
    "raul":    (311.35, "card", 0.50),   # Raul Bautista, fusil d'assaut
    "cover":   (525.90, "full", 0.50),   # reveal de la jaquette
    "dimez":   (327.95, "card", 0.55),   # Real Dimez, boîte de nuit
    "drequan": (407.80, "card", 0.50),   # Dre'Quan Priest
    "vi_end":  (6.15,   "full", 0.50),   # logo VI néon
    # plus beaux plans animés
    "glasses": (102.2,  "full", 0.50),   # Jason, lunettes rouges
    "palms":   (87.0,   "full", 0.45),   # Jason & Lucia, palmiers au couchant
    "club":    (186.2,  "full", 0.50),   # boîte de nuit néon
    "duo":     (205.8,  "full", 0.50),   # Lucia & Jason, gros plan
    "cocktail":(279.4,  "full", 0.50),   # Lucia, cocktail
    "vcboat":  (182.2,  "full", 0.50),   # Vice City vue de la mer
    "car":     (363.0,  "full", 0.62),   # duo, voiture, palmiers
    "gun":     (161.6,  "full", 0.66),   # Jason arme au poing
    "port":    (451.6,  "full", 0.50),   # duo au port
    "dress":   (283.0,  "full", 0.45),   # Lucia robe rouge
    "beach":   (488.2,  "full", 0.50),   # duo, plage
    "bonnie":  (231.0,  "full", 0.55),   # Bonnie & Clyde, station-service
    "night":   (485.2,  "full", 0.50),   # Lucia en voiture, néons (strobe + sortie)
}

# Intro : (clip, images en avant, images en arrière) ; fondu enchaîné de FADE images
INTRO = [("vi", 36, 14), ("lucia_v", 38, 16)]
FADE = 14

# ── Timeline du modèle, en images du modèle (30 i/s) : (début, fin, type, clip, param) ──
D = 0.05  # niveau « éteint » relevé sur le modèle
TIMELINE = [
    (0,   3,   "bw",     "jason_v", None),
    (3,   20,  "hit",    "jason_v", 8),
    (20,  33,  "hit",    "jason_v", 4),
    (33,  43,  "hit",    "glasses", 0),
    (43,  51,  "hit",    "glasses", 0),
    (51,  61,  "hit",    "palms", 1),
    (61,  79,  "hit",    "palms", 9),
    (79,  88,  "bw",     "raul", None),
    (88,  98,  "hit",    "raul", 0),
    (98,  107, "bw",     "raul", None),
    (107, 115, "hit",    "raul", 0),
    (115, 124, "bw",     "club", None),
    (124, 133, "hit",    "club", 0),
    (133, 146, "hit",    "club", 0),
    (146, 153, "swipe",  "club", None),
    (153, 159, "slice",  "cover", None),
    (159, 171, "swipein","cover", 2),
    (171, 180, "hit",    "cover", 0),
    (180, 190, "bwfade", "cover", None),
    (190, 209, "hit",    "duo", 0),
    (209, 218, "hold",   "cocktail", None),
    (218, 226, "flick",  "cocktail", {218: "i", 221: "i", 222: "d", 223: "di", 224: "db", 225: "di"}),
    (226, 227, "rainbow","vcboat", None),
    (227, 244, "chroma", "vcboat", 4),
    (244, 254, "hold",   "dimez", None),
    (254, 263, "bwfade", "dimez", None),
    (263, 273, "hit",    "drequan", 0),
    (273, 282, "bwfade", "drequan", None),
    (282, 300, "strobe", "car", [1, 1, 1, 1, 1, D, 1, D, D, .85, D, .7, .7, D, .45, .45, D, .45]),
    (300, 318, "hit",    "gun", 7),
    (318, 328, "hit",    "port", 0),
    (328, 337, "bwfade", "port", None),
    (337, 346, "hit",    "dress", 0),
    (346, 356, "bwfade", "dress", None),
    (356, 365, "hold",   "beach", None),
    (365, 373, "flick",  "beach", {365: "w", 367: "d", 368: "i", 369: "d", 370: "i", 371: "d", 372: "di"}),
    (373, 374, "rainbow","vi_end", None),
    (374, 391, "chroma", "vi_end", 3),
    (391, 400, "hold",   "bonnie", None),
    (400, 406, "bwfade", "bonnie", None),
    (406, 424, "strobe", "night", [.5, .35, .2, .1, 1, 1, D, 1, 1, D, 1, D, D, 1, D, D, 1, D]),
    (424, 437, "outro",  "night", None),
]
BOOMERANG = {"bw", "hit", "bwfade", "hold", "swipein", "chroma"}


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCES — chaque plan est extrait une fois (recadrage 9:16, jamais déformé)
# ══════════════════════════════════════════════════════════════════════════════

class Clip:
    def __init__(self, src, key, start, mode, cx, n_src, tmp):
        self.path = f"{tmp}/{key}.rgb"
        if mode == "card":
            x0, y0, cw0, ch = CARD
            cw = int(ch * W / H) // 2 * 2
            x = int(np.clip(x0 + cx * cw0 - cw / 2, x0, x0 + cw0 - cw))
            vf = f"crop={cw}:{ch}:{x}:{y0},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.7"
        else:
            cw = int(1080 * W / H) // 2 * 2
            x = int(np.clip(cx * 1920 - cw / 2, 0, 1920 - cw))
            vf = f"crop={cw}:1080:{x}:0,scale={W}:{H}:flags=lanczos,unsharp=5:5:0.4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-i", src,
                        "-frames:v", str(n_src), "-vf", f"fps={FPS},{vf}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", self.path], check=True)
        got = os.path.getsize(self.path) // (W * H * 3)
        self.mm = np.memmap(self.path, np.uint8, "r", shape=(got, H, W, 3))
        mean = float(np.mean(self.mm[::max(1, got // 6)]))
        self.gain = float(np.clip(105.0 / max(mean, 1.0), 1.0, 2.2))  # clips sombres éclaircis

    def at(self, pos):
        """Image à la position source `pos` (en images, fractionnaire → mélange des voisines)."""
        a = int(np.clip(int(pos), 0, len(self.mm) - 1))
        b = min(a + 1, len(self.mm) - 1)
        w = float(np.clip(pos - int(pos), 0, 1))
        f = self.mm[a].astype(np.float32) * (1 - w) + self.mm[b].astype(np.float32) * w
        if self.gain > 1.01:
            f = 255.0 * (1 - (1 - f / 255.0) ** self.gain)
        return f


def boomerang(cur, n):
    """Positions source d'un plan de n images : en avant, puis rembobinage jusqu'au départ."""
    nf = max(2, int(round(n * FWD)))
    nr = n - nf
    pos = [cur + i for i in range(nf)]
    peak = cur + nf - 1
    pos += [peak - (j + 1) * (peak - cur) / max(nr, 1) for j in range(nr)]
    return pos, cur + nf * 0.5          # le plan suivant reprend un peu plus loin


def plan_edit():
    """Pour chaque image de l'edit : (image du modèle, position dans le segment, segment, pos source)."""
    n_edit = int(round(TPL_FRAMES / SLOW))
    frames_of = {}
    for k in range(n_edit):
        tt = k / FPS * SLOW
        tf = min(int(tt * FPS + 1e-6), TPL_FRAMES - 1)
        idx = next(i for i, e in enumerate(TIMELINE) if e[0] <= tf < e[1])
        frames_of.setdefault(idx, []).append((k, tf, (tt * FPS - TIMELINE[idx][0]) /
                                              (TIMELINE[idx][1] - TIMELINE[idx][0])))
    cur = {k: 0.0 for k in CLIPS}
    plan = [None] * n_edit
    for idx in sorted(frames_of):
        e = TIMELINE[idx]
        fr = frames_of[idx]
        key = e[3]
        if e[2] in BOOMERANG and len(fr) >= 4:
            pos, cur[key] = boomerang(cur[key], len(fr))
        else:
            pos = [cur[key] + i for i in range(len(fr))]
            cur[key] += len(fr)
        for (k, tf, p), ps in zip(fr, pos):
            plan[k] = (tf, p, e, ps)
    return plan


def plan_intro():
    """Intro : chaque clip en boomerang, fondu enchaîné pendant le rembobinage du premier."""
    seqs = []
    for key, nf, nr in INTRO:
        peak = nf - 1
        back_to = peak * 0.4
        pos = list(range(nf)) + [peak - (j + 1) * (peak - back_to) / nr for j in range(nr)]
        seqs.append((key, pos))
    (ka, pa), (kb, pb) = seqs
    n = len(pa) + len(pb) - FADE
    out = []
    for k in range(n):
        ia, ib = k, k - (len(pa) - FADE)
        if ib < 0:
            out.append(((ka, pa[ia]), None, 0.0))
        elif ia < len(pa):
            a = (ib + 1) / (FADE + 1)
            out.append(((ka, pa[ia]), (kb, pb[ib]), a * a * (3 - 2 * a)))
        else:
            out.append(((kb, pb[ib]), None, 0.0))
    return out
# ══════════════════════════════════════════════════════════════════════════════
#  EFFETS (formes relevées sur le modèle)
# ══════════════════════════════════════════════════════════════════════════════

def grade(f):
    """Étalonnage : léger contraste en S, saturation un peu relevée, tons chauds."""
    lum = f.mean(axis=2, keepdims=True)
    f = lum + (f - lum) * 1.08
    x = np.clip(f / 255.0, 0, 1)
    f = 255.0 * (x + 0.12 * x * (1 - x) * (2 * x - 1) * 2)
    return f * np.array([1.02, 1.0, 0.97], np.float32)

def bw(f):
    return np.repeat((f @ np.array([0.299, 0.587, 0.114], np.float32))[..., None], 3, axis=2)

def chroma(f, px):
    if px < 1:
        return f
    px = int(px)
    out = f.copy()
    out[:, px:, 0] = f[:, :-px, 0]
    out[:, :-px, 2] = f[:, px:, 2]
    return out

def zoom(f, s):
    if s <= 1.001:
        return f
    img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8))
    w, h = int(W * s), int(H * s)
    z = img.resize((w, h), Image.BICUBIC)
    return np.asarray(z.crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H)),
                      np.float32)

def radial_blur(f, strength, steps=8):
    img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8))
    acc = np.zeros_like(f)
    for k in range(steps):
        s = 1.0 + strength * k / (steps - 1)
        w, h = int(W * s), int(H * s)
        z = img.resize((w, h), Image.BILINEAR).crop(((w - W) // 2, (h - H) // 2,
                                                    (w - W) // 2 + W, (h - H) // 2 + H))
        acc += np.asarray(z, np.float32)
    return acc / steps

_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_ANG = np.arctan2(_yy - H / 2, _xx - W / 2)
_RAD = np.hypot(_yy - H / 2, _xx - W / 2) / np.hypot(W / 2, H / 2)

def rainbow(f):
    """Explosion radiale arc-en-ciel (rayons colorés + zoom radial + centre lumineux)."""
    hue = (_ANG / (2 * np.pi) * 6.0) % 1.0
    rb = np.stack([np.clip(np.abs(hue * 6 - 3) - 1, 0, 1),
                   np.clip(2 - np.abs(hue * 6 - 2), 0, 1),
                   np.clip(2 - np.abs(hue * 6 - 4), 0, 1)], axis=2) * 255
    streak = 0.55 + 0.45 * np.sin(_ANG * 40)[..., None]
    base = radial_blur(f, 0.9, 10)
    out = base * 0.55 + rb * streak * 0.7 * np.clip(_RAD * 1.6, 0, 1)[..., None]
    return out + 120 * np.clip(1 - _RAD * 3, 0, 1)[..., None]

def light_bar(f, cx, width, strength=0.95):
    """Barre de lumière blanche verticale aux bords doux (balayage du modèle)."""
    x = np.arange(W, dtype=np.float32)
    m = np.exp(-((x - cx * W) / (width * W)) ** 6)[None, :, None]
    return f * (1 - m * strength) + 250 * m * strength

def slice_glitch(base, reveal, rng, p):
    """Tranches horizontales : blocs blancs/noirs + image décalée, le clip suivant apparaît."""
    out = np.empty_like(base)
    y = 0
    while y < H:
        h = int(rng.integers(30, 220))
        r = rng.random()
        src = reveal if rng.random() < 0.3 + 0.7 * p else base
        if r < 0.28:
            out[y:y + h] = 245
            x0 = int(rng.integers(0, W // 2))
            out[y:y + h, x0:x0 + int(rng.integers(80, W // 2))] = 8
        elif r < 0.42:
            out[y:y + h] = 8
        else:
            out[y:y + h] = np.roll(src[y:y + h], int(rng.integers(-250, 250)), axis=1)
        y += h
    return out

def finish(f, rng):
    """Vignette légère + grain fin (texture du modèle)."""
    f = f * (1 - 0.22 * np.clip(_RAD - 0.5, 0, 1)[..., None])
    f = f + rng.normal(0, 5.0, (H, W, 1)).astype(np.float32)
    return np.clip(f, 0, 255).astype(np.uint8)


# ══════════════════════════════════════════════════════════════════════════════
#  RENDU
# ══════════════════════════════════════════════════════════════════════════════

def fade_gain(p, hold_frac):
    """Pleine lumière pendant le maintien puis chute au noir (modèle : 1 → 0,05).
    Maintien minimum 30 % pour que chaque clip se voie clairement."""
    hold = max(hold_frac, 0.3)
    if p <= hold:
        return 1.0
    return 1.0 - (1.0 - D) * min(1.0, (p - hold) / (1 - hold))


def edit_frame(tf, p, entry, f, clips, rng):
    f0, f1, kind, key, prm = entry
    f = grade(f)
    if kind == "bw":
        f = bw(f) * 0.75
    elif kind == "hit":
        f = f * fade_gain(p, prm / (f1 - f0))
    elif kind == "bwfade":
        f = bw(f) * (0.85 * fade_gain(p, 0.0))
    elif kind == "hold":
        pass
    elif kind == "swipe":
        f = light_bar(f * 0.35, -0.05 + 1.0 * p, 0.10 + 0.08 * p)
    elif kind == "slice":
        prev = grade(clips["club"].at(40)) * 0.35
        f = slice_glitch(prev, f, rng, p)
    elif kind == "swipein":
        f = f * fade_gain(p, prm / (f1 - f0))
        if p < 0.65:
            f = light_bar(f, 0.35 + 0.9 * p / 0.65, 0.14, 0.9 * (1 - p / 0.65 * 0.5))
    elif kind == "flick":
        s = prm.get(tf, "n")
        if s == "i":
            f = (255 - f) * np.array([0.75, 0.95, 1.1], np.float32)
        elif s == "w":
            f = np.minimum(255, f * 1.9 + 40)
        elif s == "d":
            f = f * 0.45
        elif s == "db":
            f = radial_blur(f, 0.12) * 0.45
        elif s == "di":
            f = chroma((255 - f) * np.array([0.3, 0.42, 0.55], np.float32), 14)
    elif kind == "rainbow":
        f = rainbow(f)
    elif kind == "chroma":
        k = tf - f0
        if k < prm:
            a = 1 - k / prm
            f = chroma(radial_blur(f, 0.35 * a), 26 * a)
    elif kind == "strobe":
        f = f * prm[min(tf - f0, len(prm) - 1)]
    elif kind == "outro":
        if p < 0.65:
            q = p / 0.65
            f = radial_blur(f, 0.05 + 0.35 * q) * (1.0 + 0.5 * q)
        else:
            q = (p - 0.65) / 0.35
            img = Image.fromarray(np.clip(radial_blur(f, 0.4) * 1.5, 0, 255).astype(np.uint8))
            f = np.asarray(img.filter(ImageFilter.GaussianBlur(12 + 40 * q)), np.float32)
            f = f * (1.0 - 0.6 * q)
    return finish(f, rng)


def build(source, music, out):
    intro, plan = plan_intro(), plan_edit()
    n_intro, n_edit = len(intro), len(plan)
    d_intro, d_edit = n_intro / FPS, n_edit / FPS
    print(f"🎬  intro {d_intro:.2f} s (sans musique) + edit {d_edit:.2f} s = {d_intro + d_edit:.2f} s")

    need = {k: 0.0 for k in CLIPS}
    for a, b, _ in intro:
        for kp in (a, b):
            if kp:
                need[kp[0]] = max(need[kp[0]], kp[1])
    for tf, p, e, ps in plan:
        need[e[3]] = max(need[e[3]], ps)
    tmp = tempfile.mkdtemp(prefix="gta6_edit_")
    clips = {}
    for key, (start, mode, cx) in CLIPS.items():
        n_src = int(need[key]) + 3
        clips[key] = Clip(source, key, start, mode, cx, n_src, tmp)
        print(f"   {key:<9} {int(start // 60)}:{start % 60:05.2f} → {start + n_src / FPS:7.2f} s"
              f"  ({mode}, éclairci ×{clips[key].gain:.2f})")

    silent = f"{tmp}/video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "slow", "-crf", "18", "-maxrate", "20M", "-bufsize", "40M",
                           "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    rng = np.random.default_rng(7)
    for k, (a, b, w) in enumerate(intro):
        f = clips[a[0]].at(a[1])
        if b:
            f = f * (1 - w) + clips[b[0]].at(b[1]) * w
        f = zoom(grade(f), 1.0 + 0.05 * k / n_intro)
        if k < 9:
            f = f * (k / 9)
        ff.stdin.write(finish(f, rng).tobytes())
    for tf, p, e, ps in plan:
        ff.stdin.write(edit_frame(tf, p, e, clips[e[3]].at(ps), clips, rng).tobytes())
    ff.stdin.close(); ff.wait()

    # ── audio : intro = son d'origine des 2 clips en fondu ; puis musique slowed ──
    sr = 44100
    (ka, nfa, nra), (kb, nfb, nrb) = INTRO
    sa, sb = CLIPS[ka][0], CLIPS[kb][0]
    la, lb = (nfa + nra) / FPS, (nfb + nrb) / FPS
    fc = (f"[0:a]atrim={sa}:{sa + la:.3f},asetpts=PTS-STARTPTS,aresample={sr}[a1];"
          f"[0:a]atrim={sb}:{sb + lb:.3f},asetpts=PTS-STARTPTS,aresample={sr}[a2];"
          f"[a1][a2]acrossfade=d={FADE / FPS:.3f}:c1=tri:c2=tri,"
          f"afade=t=in:d=0.3,afade=t=out:st={d_intro - 0.25:.3f}:d=0.25,"
          f"loudnorm=I=-20:TP=-2,aresample={sr},apad,atrim=0:{d_intro:.3f}[intro];"
          f"[1:a]asetrate={int(sr * SLOW)},aresample={sr},"
          "aecho=0.8:0.8:60|120|220:0.28|0.2|0.12,"
          "lowpass=f=13000,bass=g=2:f=90,"
          f"loudnorm=I=-14:TP=-1.0:LRA=11,aresample={sr},apad,atrim=0:{d_edit:.3f},"
          f"afade=t=out:st={d_edit - 0.8:.2f}:d=0.8[mus];"
          "[intro][mus]concat=n=2:v=0:a=1[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source, "-i", music, "-i", silent,
                    "-filter_complex", fc, "-map", "2:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-ar", str(sr),
                    "-t", f"{d_intro + d_edit:.3f}", "-movflags", "+faststart", out], check=True)
    print(f"✅  {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Edit GTA 6 réplique du modèle CapCut + musique slowed")
    ap.add_argument("--source", required=True, help="vidéo longue GTA 6")
    ap.add_argument("--music", required=True, help="fichier audio/vidéo de la musique (aperçu du modèle)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    build(a.source, a.music, a.out)
