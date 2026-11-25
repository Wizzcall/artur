"""
GTA 6 — EDIT « DARK FLICKER » (réplique du modèle CapCut) · musique SUPER SLOWED
9:16 · 1080×1920 · 30 i/s

Le modèle CapCut (14,6 s, ~97 BPM) a été relevé image par image (luminance + saturation
de chacune de ses 437 images) : chaque plan tombe sur le beat en pleine lumière puis
s'éteint au noir, en alternant couleur / noir & blanc, avec 4 effets signature :
  · balayage lumineux blanc + glitch en tranches     (modèle 4,87 → 5,30 s)
  · flicker négatif → explosion radiale arc-en-ciel  (modèle 7,27 → 7,63 s et 12,17 → 12,50 s)
  · strobe                                           (modèle 9,40 → 9,97 s et 13,53 → 14,10 s)
  · sortie en zoom flou                              (modèle 14,13 → fin)

Super slowed = vitesse ET hauteur × SLOW (0,75) + reverb. Toute la timeline du modèle est
étirée du même facteur → chaque effet reste exactement sur le même temps de la musique.

USAGE
    python edit.py --source GTA6_VIDEO_FINALE_SANS_VOIX.mp4 --music modele_capcut.mp4
    (--music : le fichier dont on prend la bande-son — ici l'aperçu du modèle CapCut)
OUTPUT : WIZZCALL_GTA6_EDIT_SLOWED.mp4
"""

import argparse, os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter

W, H, FPS = 1080, 1920, 30
SLOW = 0.75                     # super slowed : 0,75× vitesse + hauteur
TPL_FRAMES = 437                # durée du modèle : 437 images à 30 i/s
OUT = "WIZZCALL_GTA6_EDIT_SLOWED.mp4"

# ── Plans : (début dans la vidéo longue en s, centre horizontal du recadrage 0..1) ──
SHOTS = {
    "A": (5.2,   0.50),   # logo VI néon
    "B": (102.2, 0.50),   # Jason, lunettes rouges (gros plan)
    "C": (87.0,  0.45),   # Jason & Lucia, palmiers au couchant
    "D": (184.6, 0.50),   # Cheetah blanche à Vice City
    "E": (161.6, 0.66),   # Jason arme au poing
    "F": (186.2, 0.50),   # boîte de nuit néon
    "G": (204.6, 0.50),   # Lucia & Jason, gros plan
    "H": (286.2, 0.50),   # bikers
    "I": (279.4, 0.50),   # Lucia, cocktail
    "J": (182.2, 0.50),   # Vice City vue de la mer
    "K": (480.2, 0.50),   # panneau VICE CITY
    "L": (307.0, 0.58),   # braqueur au bandana
    "M": (363.0, 0.62),   # Jason & Lucia, voiture, palmiers
    "N": (226.2, 0.50),   # Lucia au couchant
    "O": (451.6, 0.50),   # duo au port
    "P": (283.0, 0.45),   # Lucia robe rouge
    "Q": (488.2, 0.50),   # Jason & Lucia, plage
    "R": (62.0,  0.50),   # jaquette GTA VI
    "S": (231.0, 0.55),   # Bonnie & Clyde, station-service
    "T": (485.2, 0.50),   # Lucia en voiture (strobe + sortie)
}

# ── Timeline du modèle, en images du modèle (30 i/s) : (début, fin, type, plan, param) ──
D = 0.05  # niveau « éteint »
TIMELINE = [
    (0,   3,   "bw",     "A", None),
    (3,   20,  "hit",    "A", 8),
    (20,  33,  "hit",    "A", 4),
    (33,  43,  "hit",    "B", 0),
    (43,  51,  "hit",    "B", 0),
    (51,  61,  "hit",    "C", 1),
    (61,  79,  "hit",    "C", 9),
    (79,  88,  "bw",     "D", None),
    (88,  98,  "hit",    "D", 0),
    (98,  107, "bw",     "E", None),
    (107, 115, "hit",    "E", 0),
    (115, 124, "bw",     "F", None),
    (124, 133, "hit",    "F", 0),
    (133, 146, "hit",    "F", 0),
    (146, 153, "swipe",  "F", None),
    (153, 159, "slice",  "G", None),
    (159, 171, "swipein","G", 2),
    (171, 180, "hit",    "G", 0),
    (180, 190, "bwfade", "G", None),
    (190, 209, "hit",    "H", 0),
    (209, 218, "hold",   "I", None),
    (218, 226, "flick",  "I", {218: "i", 221: "i", 222: "d", 223: "di", 224: "db", 225: "di"}),
    (226, 227, "rainbow","J", None),
    (227, 244, "chroma", "J", 4),
    (244, 254, "hold",   "K", None),
    (254, 263, "bwfade", "K", None),
    (263, 273, "hit",    "L", 0),
    (273, 282, "bwfade", "L", None),
    (282, 300, "strobe", "M", [1, 1, 1, 1, 1, D, 1, D, D, .85, D, .7, .7, D, .45, .45, D, .45]),
    (300, 318, "hit",    "N", 7),
    (318, 328, "hit",    "O", 0),
    (328, 337, "bwfade", "O", None),
    (337, 346, "hit",    "P", 0),
    (346, 356, "bwfade", "P", None),
    (356, 365, "hold",   "Q", None),
    (365, 373, "flick",  "Q", {365: "w", 367: "d", 368: "i", 369: "d", 370: "i", 371: "d", 372: "di"}),
    (373, 374, "rainbow","R", None),
    (374, 391, "chroma", "R", 3),
    (391, 400, "hold",   "S", None),
    (400, 406, "bwfade", "S", None),
    (406, 424, "strobe", "T", [.5, .35, .2, .1, 1, 1, D, 1, 1, D, 1, D, D, 1, D, D, 1, D]),
    (424, 437, "outro",  "T", None),
]


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCES — chaque plan est extrait une fois (recadrage 9:16, jamais déformé)
# ══════════════════════════════════════════════════════════════════════════════

class Shot:
    def __init__(self, src, start, cx, n, tmp, key):
        self.n, self.path = n, f"{tmp}/{key}.rgb"
        cw = int(1080 * W / H) // 2 * 2                      # 606 px de large dans du 1080p
        x = int(np.clip(cx * 1920 - cw / 2, 0, 1920 - cw))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start}", "-i", src,
                        "-frames:v", str(n), "-vf",
                        f"fps={FPS},crop={cw}:1080:{x}:0,scale={W}:{H}:flags=lanczos",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", self.path], check=True)
        got = os.path.getsize(self.path) // (W * H * 3)
        self.mm = np.memmap(self.path, np.uint8, "r", shape=(got, H, W, 3))

    def frame(self, i):
        return np.array(self.mm[min(i, len(self.mm) - 1)], dtype=np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  EFFETS (formes relevées sur le modèle)
# ══════════════════════════════════════════════════════════════════════════════

def grade(f):
    """Étalonnage sombre et contrasté du modèle (ombres denses, saturation retenue)."""
    lum = f.mean(axis=2, keepdims=True)
    f = lum + (f - lum) * 0.85
    f = (f / 255.0) ** 1.15 * 255.0
    return f * np.array([1.03, 1.0, 0.96], np.float32)

def bw(f):
    return np.repeat((f @ np.array([0.299, 0.587, 0.114], np.float32))[..., None], 3, axis=2)

def fade_gain(p, hold_frac):
    """Pleine lumière pendant le maintien, puis extinction linéaire jusqu'au noir (relevé : 1 → 0,05)."""
    if p <= hold_frac:
        return 1.0
    return 1.0 - (1.0 - D) * min(1.0, (p - hold_frac) / max(1e-6, 1 - hold_frac))

def chroma(f, px):
    if px < 1:
        return f
    px = int(px)
    out = f.copy()
    out[:, px:, 0] = f[:, :-px, 0]
    out[:, :-px, 2] = f[:, px:, 2]
    return out

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
    out = base * 0.45 + rb * streak * 0.75 * np.clip(_RAD * 1.6, 0, 1)[..., None]
    return out + 120 * np.clip(1 - _RAD * 3, 0, 1)[..., None]

def light_bar(f, cx, width, strength=0.95):
    """Barre de lumière blanche verticale aux bords doux (balayage du modèle)."""
    x = np.arange(W, dtype=np.float32)
    m = np.exp(-((x - cx * W) / (width * W)) ** 6)[None, :, None]
    return f * (1 - m * strength) + 250 * m * strength

def slice_glitch(base, reveal, rng, p):
    """Tranches horizontales : blocs blancs/noirs + image décalée, l'image suivante apparaît."""
    out = np.empty_like(base)
    y = 0
    while y < H:
        h = int(rng.integers(30, 220))
        r = rng.random()
        src = reveal if rng.random() < p else base
        if r < 0.35:
            out[y:y + h] = 245
            x0 = int(rng.integers(0, W // 2))
            out[y:y + h, x0:x0 + int(rng.integers(80, W // 2))] = 8
        elif r < 0.55:
            out[y:y + h] = 8
        else:
            out[y:y + h] = np.roll(src[y:y + h], int(rng.integers(-250, 250)), axis=1)
        y += h
    return out

def grain(f, rng, a=7.0):
    return f + rng.normal(0, a, (H, W, 1)).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  RENDU
# ══════════════════════════════════════════════════════════════════════════════

def render_frame(tf, tpos, entry, shots, local, rng):
    """tf = image du modèle (entier), tpos = position fractionnaire dans le segment."""
    f0, f1, kind, key, prm = entry
    shot = shots[key]
    f = grade(shot.frame(local))
    p = tpos

    if kind == "bw":
        f = bw(f) * 0.64
    elif kind == "hit":
        f = f * fade_gain(p, prm / (f1 - f0))
    elif kind == "bwfade":
        f = bw(f) * fade_gain(p, 0.0)
    elif kind == "hold":
        pass
    elif kind == "swipe":
        f = light_bar(f * 0.3, -0.05 + 1.0 * p, 0.10 + 0.08 * p)
    elif kind == "slice":
        prev = grade(shots["F"].frame(local + 60)) * 0.3
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
            f = radial_blur(f, 0.05 + 0.35 * q) * (1.0 + 0.55 * q)
        else:
            q = (p - 0.65) / 0.35
            img = Image.fromarray(np.clip(radial_blur(f, 0.4) * 1.55, 0, 255).astype(np.uint8))
            f = np.asarray(img.filter(ImageFilter.GaussianBlur(12 + 40 * q)), np.float32)
            f = f * (1.0 - 0.55 * q)

    # vignette légère + grain (texture du modèle)
    f = f * (1 - 0.35 * np.clip(_RAD - 0.45, 0, 1)[..., None] ** 1.2)
    return np.clip(grain(f, rng), 0, 255).astype(np.uint8)


def build(source, music, out):
    n_out = int(round(TPL_FRAMES / SLOW))
    dur = n_out / FPS
    tmp = tempfile.mkdtemp(prefix="gta6_edit_")
    print(f"🎬  {n_out} images · {dur:.2f} s (modèle {TPL_FRAMES / FPS:.2f} s × 1/{SLOW})")

    # durée nécessaire par plan (temps réel de sortie)
    need = {}
    for f0, f1, kind, key, _ in TIMELINE:
        need[key] = need.get(key, 0) + int((f1 - f0) / SLOW) + 2
    need["F"] += 70                                       # images reprises sous le glitch
    shots = {}
    for key, (start, cx) in SHOTS.items():
        print(f"   plan {key} ← {int(start // 60)}:{start % 60:04.1f}")
        shots[key] = Shot(source, start, cx, need[key], tmp, key)

    silent = f"{tmp}/video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "slow", "-crf", "18", "-maxrate", "20M", "-bufsize", "40M", "-pix_fmt", "yuv420p", silent],
                          stdin=subprocess.PIPE)
    rng = np.random.default_rng(7)
    used = {k: 0 for k in SHOTS}
    seg_i = -1
    for k in range(n_out):
        tt = k / FPS * SLOW                    # temps dans le modèle
        tf = min(int(tt * FPS + 1e-6), TPL_FRAMES - 1)
        idx = next(i for i, e in enumerate(TIMELINE) if e[0] <= tf < e[1])
        e = TIMELINE[idx]
        if idx != seg_i:
            seg_i, seg_k0 = idx, k
        p = (tt * FPS - e[0]) / (e[1] - e[0])
        local = used[e[3]]
        used[e[3]] += 1
        ff.stdin.write(render_frame(tf, p, e, shots, local, rng).tobytes())
    ff.stdin.close(); ff.wait()

    # ── musique super slowed : vitesse+hauteur × SLOW, reverb longue, aigus adoucis ──
    sr = 44100
    af = (f"asetrate={int(sr * SLOW)},aresample={sr},"
          "aecho=0.8:0.82:70|140|260|400:0.32|0.24|0.16|0.10,"
          "lowpass=f=11000,bass=g=3:f=90,"
          "loudnorm=I=-14:TP=-1.0:LRA=11,"
          f"afade=t=out:st={dur - 0.9:.2f}:d=0.9")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", music,
                    "-map", "0:v", "-map", "1:a", "-af", af, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-ar", str(sr), "-t", f"{dur:.3f}",
                    "-movflags", "+faststart", out], check=True)
    print(f"✅  {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Edit GTA 6 réplique du modèle CapCut + musique super slowed")
    ap.add_argument("--source", required=True, help="vidéo longue GTA 6")
    ap.add_argument("--music", required=True, help="fichier audio/vidéo de la musique (aperçu du modèle)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    build(a.source, a.music, a.out)
