"""
GTA 6 — EDIT « FLICKER » (réplique du modèle CapCut) · musique SUPER SLOWED
9:16 · 1080×1920 · 30 i/s · uniquement des passages VIDÉO (aucune image fixe)

STRUCTURE
  1. Intro SANS musique (2,7 s) : 2 clips vidéo en fondu enchaîné, son d'origine
       logo VI (reveal)  ──fondu 0,6 s──▶  Lucia en voiture, la nuit
  2. Edit sur la musique super slowed (19,4 s) : réplique du modèle CapCut

Le modèle CapCut (14,6 s, ~97 BPM) a été relevé image par image (luminance + saturation
de ses 437 images) : chaque plan arrive sur le beat en pleine lumière puis baisse, en
alternant couleur / noir & blanc, avec 4 effets signature :
  · balayage lumineux blanc + glitch en tranches     (modèle 4,87 → 5,30 s)
  · flicker négatif → explosion radiale arc-en-ciel  (modèle 7,27 → 7,63 s et 12,17 → 12,50 s)
  · strobe                                           (modèle 9,40 → 9,97 s et 13,53 → 14,10 s)
  · sortie en zoom flou                              (modèle 14,13 → fin)
Différence voulue avec le modèle : les plans ne tombent plus au noir complet (plancher 35 %)
pour qu'on voie clairement les clips.

Super slowed = vitesse ET hauteur × SLOW (0,75) + reverb. La timeline du modèle est étirée
du même facteur (chaque effet reste sur son temps) et les clips sont joués à 0,75× aussi.

USAGE
    python edit.py --source GTA6_VIDEO_FINALE_SANS_VOIX.mp4 --music modele_capcut.mp4
OUTPUT : WIZZCALL_GTA6_EDIT_SLOWED.mp4
"""

import argparse, os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter

W, H, FPS = 1080, 1920, 30
SLOW = 0.75                     # super slowed : 0,75× vitesse + hauteur (musique ET clips)
TPL_FRAMES = 437                # durée du modèle : 437 images à 30 i/s
OUT = "WIZZCALL_GTA6_EDIT_SLOWED.mp4"

# Zone de la « carte » vidéo dans la vidéo longue (clips personnages) : x 512→1406, y 92→986
CARD = (530, 110, 860, 860)     # x, y, largeur, hauteur (marge pour éviter le bord de la carte)

# ── Clips VIDÉO de la vidéo longue : début (s), cadrage, centre horizontal, vitesse ──
#    "full" = recadrage 9:16 de l'image 16:9 · "card" = zoom dans la carte vidéo centrale
CLIPS = {
    "vi":      (4.60,   "full", 0.50, 1.0),   # intro : reveal du logo VI
    "lucia":   (225.00, "full", 0.62, 1.0),   # intro : Lucia en voiture, la nuit, arme
    "jason":   (306.40, "full", 0.56, SLOW),  # Jason au bandana, braquage de la supérette
    "raul":    (311.35, "card", 0.50, SLOW),  # Raul Bautista, fusil d'assaut dans la rue
    "cover":   (525.90, "full", 0.50, SLOW),  # reveal de la jaquette GTA VI
    "dimez":   (327.95, "card", 0.55, SLOW),  # Real Dimez, boîte de nuit
    "drequan": (407.80, "card", 0.50, SLOW),  # Dre'Quan Priest
    "vi_end":  (6.15,   "full", 0.50, SLOW),  # logo VI néon (sortie)
}
INTRO = [("vi", 48), ("lucia", 51)]  # (clip, images) — fondu de FADE images entre les deux
FADE = 18

# ── Timeline du modèle, en images du modèle (30 i/s) : (début, fin, type, clip, param) ──
D = 0.35  # plancher de lumière (le modèle descend à ~0,05 ; relevé pour voir les clips)
TIMELINE = [
    (0,   3,   "bw",     "jason", None),
    (3,   20,  "hit",    "jason", 8),
    (20,  33,  "hit",    "jason", 4),
    (33,  43,  "hit",    "jason", 0),
    (43,  51,  "hit",    "jason", 0),
    (51,  61,  "hit",    "jason", 1),
    (61,  79,  "hit",    "jason", 9),
    (79,  88,  "bw",     "raul", None),
    (88,  98,  "hit",    "raul", 0),
    (98,  107, "bw",     "raul", None),
    (107, 115, "hit",    "raul", 0),
    (115, 124, "bw",     "raul", None),
    (124, 133, "hit",    "raul", 0),
    (133, 146, "hit",    "raul", 0),
    (146, 153, "swipe",  "raul", None),
    (153, 159, "slice",  "cover", None),
    (159, 171, "swipein","cover", 2),
    (171, 180, "hit",    "cover", 0),
    (180, 190, "bwfade", "cover", None),
    (190, 209, "hit",    "dimez", 0),
    (209, 218, "hold",   "dimez", None),
    (218, 226, "flick",  "dimez", {218: "i", 221: "i", 222: "d", 223: "di", 224: "db", 225: "di"}),
    (226, 227, "rainbow","cover", None),
    (227, 244, "chroma", "cover", 4),
    (244, 254, "hold",   "cover", None),
    (254, 263, "bwfade", "cover", None),
    (263, 273, "hit",    "drequan", 0),
    (273, 282, "bwfade", "drequan", None),
    (282, 300, "strobe", "drequan", [1, 1, 1, 1, 1, D, 1, D, D, .9, D, .8, .8, D, .6, .6, D, .6]),
    (300, 318, "hit",    "jason", 7),
    (318, 328, "hit",    "raul", 0),
    (328, 337, "bwfade", "raul", None),
    (337, 346, "hit",    "raul", 0),
    (346, 356, "bwfade", "raul", None),
    (356, 365, "hold",   "dimez", None),
    (365, 373, "flick",  "dimez", {365: "w", 367: "d", 368: "i", 369: "d", 370: "i", 371: "d", 372: "di"}),
    (373, 374, "rainbow","dimez", None),
    (374, 391, "chroma", "dimez", 3),
    (391, 400, "hold",   "drequan", None),
    (400, 406, "bwfade", "drequan", None),
    (406, 424, "strobe", "vi_end", [.7, .6, .5, .45, 1, 1, D, 1, 1, D, 1, D, D, 1, D, D, 1, D]),
    (424, 437, "outro",  "vi_end", None),
]


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCES — chaque clip est extrait une fois, à sa cadence d'origine (jamais déformé)
# ══════════════════════════════════════════════════════════════════════════════

class Clip:
    def __init__(self, src, key, start, mode, cx, speed, n_out, tmp):
        self.speed, self.path = speed, f"{tmp}/{key}.rgb"
        n_src = int(np.ceil(n_out * speed)) + 2
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
        # clips sombres éclaircis automatiquement (luminance moyenne visée ≈ 105)
        mean = float(np.mean(self.mm[::max(1, got // 6)]))
        self.gain = float(np.clip(105.0 / max(mean, 1.0), 1.0, 2.2))
        self.used = 0

    def frame(self, i):
        """Image i de sortie ; à vitesse < 1, mélange des 2 images source voisines (ralenti fluide)."""
        pos = i * self.speed
        a = min(int(pos), len(self.mm) - 1)
        b = min(a + 1, len(self.mm) - 1)
        w = pos - int(pos)
        f = self.mm[a].astype(np.float32) * (1 - w) + self.mm[b].astype(np.float32) * w
        if self.gain > 1.01:  # éclaircit en protégeant les hautes lumières
            f = 255.0 * (1 - (1 - f / 255.0) ** self.gain)
        return f

    def next(self):
        f = self.frame(self.used)
        self.used += 1
        return f


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

def fade_gain(p, hold_frac):
    """Pleine lumière pendant le maintien, puis baisse linéaire jusqu'au plancher D."""
    hold = max(hold_frac, 0.4)
    if p <= hold:
        return 1.0
    return 1.0 - (1.0 - D) * min(1.0, (p - hold) / (1 - hold))

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

def intro_frames(clips, rng):
    """2 clips vidéo en fondu enchaîné, légère poussée caméra, ouverture depuis le noir."""
    (ka, na), (kb, nb) = INTRO
    n = na + nb - FADE
    for k in range(n):
        if k < na - FADE:
            f = clips[ka].next()
        elif k < na:
            a = (k - (na - FADE) + 1) / (FADE + 1)
            a = a * a * (3 - 2 * a)                       # fondu doux (smoothstep)
            f = clips[ka].next() * (1 - a) + clips[kb].next() * a
        else:
            f = clips[kb].next()
        f = zoom(grade(f), 1.0 + 0.05 * k / n)
        if k < 9:
            f = f * (k / 9)
        yield finish(f, rng)


def edit_frame(tf, p, entry, clips, rng):
    """tf = image du modèle (entier), p = position fractionnaire dans le segment."""
    f0, f1, kind, key, prm = entry
    f = grade(clips[key].next())

    if kind == "bw":
        f = bw(f) * 0.9
    elif kind == "hit":
        f = f * fade_gain(p, prm / (f1 - f0))
    elif kind == "bwfade":
        f = bw(f) * (0.9 * fade_gain(p, 0.3))
    elif kind == "hold":
        pass
    elif kind == "swipe":
        f = light_bar(f * 0.6, -0.05 + 1.0 * p, 0.10 + 0.08 * p)
    elif kind == "slice":
        prev = grade(clips["raul"].frame(clips["raul"].used))
        f = slice_glitch(prev * 0.6, f, rng, p)
    elif kind == "swipein":
        f = f * fade_gain(p, prm / (f1 - f0))
        if p < 0.65:
            f = light_bar(f, 0.35 + 0.9 * p / 0.65, 0.14, 0.9 * (1 - p / 0.65 * 0.5))
    elif kind == "flick":
        s = prm.get(tf, "n")
        if s == "i":
            f = (255 - f) * np.array([0.8, 0.95, 1.1], np.float32)
        elif s == "w":
            f = np.minimum(255, f * 1.8 + 40)
        elif s == "d":
            f = f * 0.6
        elif s == "db":
            f = radial_blur(f, 0.12) * 0.6
        elif s == "di":
            f = chroma((255 - f) * np.array([0.45, 0.6, 0.75], np.float32), 14)
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
            f = radial_blur(f, 0.05 + 0.35 * q) * (1.0 + 0.45 * q)
        else:
            q = (p - 0.65) / 0.35
            img = Image.fromarray(np.clip(radial_blur(f, 0.4) * 1.45, 0, 255).astype(np.uint8))
            f = np.asarray(img.filter(ImageFilter.GaussianBlur(12 + 40 * q)), np.float32)
            f = f * (1.0 - 0.6 * q)
    return finish(f, rng)


def build(source, music, out):
    n_intro = sum(n for _, n in INTRO) - FADE
    n_edit = int(round(TPL_FRAMES / SLOW))
    d_intro, d_edit = n_intro / FPS, n_edit / FPS
    tmp = tempfile.mkdtemp(prefix="gta6_edit_")
    print(f"🎬  intro {d_intro:.2f} s (sans musique) + edit {d_edit:.2f} s = {d_intro + d_edit:.2f} s")

    # nombre d'images de sortie demandées à chaque clip
    need = {k: 0 for k in CLIPS}
    for k, n in INTRO:
        need[k] += n
    for f0, f1, kind, key, _ in TIMELINE:
        need[key] += int((f1 - f0) / SLOW) + 2
    clips = {}
    for key, (start, mode, cx, speed) in CLIPS.items():
        clips[key] = Clip(source, key, start, mode, cx, speed, need[key], tmp)
        c = clips[key]
        print(f"   {key:<8} {int(start // 60)}:{start % 60:05.2f} → {start + need[key] * speed / FPS:7.2f} s"
              f"  ({mode}, ×{speed}, éclairci ×{c.gain:.2f})")

    silent = f"{tmp}/video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "slow", "-crf", "18", "-maxrate", "20M", "-bufsize", "40M",
                           "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    rng = np.random.default_rng(7)
    for f in intro_frames(clips, rng):
        ff.stdin.write(f.tobytes())
    for k in range(n_edit):
        tt = k / FPS * SLOW                                    # temps dans le modèle
        tf = min(int(tt * FPS + 1e-6), TPL_FRAMES - 1)
        e = next(e for e in TIMELINE if e[0] <= tf < e[1])
        p = (tt * FPS - e[0]) / (e[1] - e[0])
        ff.stdin.write(edit_frame(tf, p, e, clips, rng).tobytes())
    ff.stdin.close(); ff.wait()

    # ── audio : intro = son d'origine des 2 clips en fondu ; puis musique super slowed ──
    sr = 44100
    (ka, na), (kb, nb) = INTRO
    sa, sb = CLIPS[ka][0], CLIPS[kb][0]
    fc = (f"[0:a]atrim={sa}:{sa + na / FPS:.3f},asetpts=PTS-STARTPTS,aresample={sr}[a1];"
          f"[0:a]atrim={sb}:{sb + nb / FPS:.3f},asetpts=PTS-STARTPTS,aresample={sr}[a2];"
          f"[a1][a2]acrossfade=d={FADE / FPS:.3f}:c1=tri:c2=tri,"
          f"afade=t=in:d=0.3,afade=t=out:st={d_intro - 0.25:.3f}:d=0.25,"
          f"loudnorm=I=-20:TP=-2,aresample={sr},atrim=0:{d_intro:.3f}[intro];"
          f"[1:a]asetrate={int(sr * SLOW)},aresample={sr},"
          "aecho=0.8:0.82:70|140|260|400:0.32|0.24|0.16|0.10,"
          "lowpass=f=11000,bass=g=3:f=90,"
          f"loudnorm=I=-14:TP=-1.0:LRA=11,aresample={sr},atrim=0:{d_edit:.3f},"
          f"afade=t=out:st={d_edit - 0.9:.2f}:d=0.9[mus];"
          "[intro][mus]concat=n=2:v=0:a=1[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source, "-i", music, "-i", silent,
                    "-filter_complex", fc, "-map", "2:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "320k", "-ar", str(sr),
                    "-t", f"{d_intro + d_edit:.3f}", "-movflags", "+faststart", out], check=True)
    print(f"✅  {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Edit GTA 6 réplique du modèle CapCut + musique super slowed")
    ap.add_argument("--source", required=True, help="vidéo longue GTA 6")
    ap.add_argument("--music", required=True, help="fichier audio/vidéo de la musique (aperçu du modèle)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    build(a.source, a.music, a.out)
