"""
GTA 6 — réplique du modèle CapCut « Malemo slowed » (FlipClip · #reverse)
9:16 · 1080×1920 · 30 i/s · 22,1 s · musique du modèle (Malemo slowed) telle quelle

Le modèle a été relevé image par image (luminance, couleur, écart entre images, sur ses
664 images) :
  0,00 → 10,63 s  emplacement « INTRO » : ouverture depuis le noir, poussée lente, vignette
                  (ici : 2 clips vidéo en fondu enchaîné, logo VI ralenti → Jason au bandana)
  10,33 → 11,00   le premier média monte par le bas + zoom radial qui blanchit (le drop)
  11,00 → 21,63   emplacements « YOUR MEDIA » : 2 cycles identiques de 159 images, 8 médias
                  par cycle. Chaque média arrive sur un flash d'exposition qui retombe ;
                  certains se retournent en NÉGATIF MIROIR (« AIDEM RUOY ») puis repartent
                  EN ARRIÈRE (reverse) ; flashs blancs entre les médias ; vitres brisées ;
                  2 zooms radiaux jusqu'au blanc par cycle.
  21,63 → 22,13   flash blanc → fondu au noir

USAGE
    python edit_malemo.py --source GTA6_VIDEO_FINALE_SANS_VOIX.mp4 --template malemo.mp4
    (--template : l'aperçu du modèle CapCut, dont on reprend la musique)
OUTPUT : WIZZCALL_GTA6_MALEMO.mp4
"""

import argparse, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from edit import Clip, grade, radial_blur, zoom, W, H, FPS

OUT = "WIZZCALL_GTA6_MALEMO.mp4"
N_TOTAL = 664                        # 22,13 s, comme le modèle

# ── Plans de la vidéo longue : début (s), cadrage, centre horizontal, vitesse ──
CLIPS = {
    # INTRO (2 clips vidéo en fondu)
    "vi":      (4.60,   "full", 0.50, 0.4),    # logo VI qui se construit, ralenti
    "jason_i": (306.40, "full", 0.64, 0.7),    # Jason au bandana, braquage
    # YOUR MEDIA — cycle 1
    "lucia_v": (225.00, "full", 0.62, 1.0),    # Lucia en voiture, la nuit
    "raul":    (311.40, "card", 0.50, 1.0),    # Raul Bautista, fusil d'assaut
    "glasses": (102.20, "full", 0.50, 1.0),    # Jason, lunettes rouges
    "club":    (186.20, "full", 0.50, 1.0),    # boîte de nuit néon
    "cocktail":(279.40, "full", 0.50, 1.0),    # Lucia, cocktail
    "palms":   (87.00,  "full", 0.45, 1.0),    # Jason & Lucia, palmiers
    "dress":   (283.00, "full", 0.45, 1.0),    # Lucia robe rouge
    "bonnie":  (231.00, "full", 0.55, 1.0),    # Bonnie & Clyde
    # YOUR MEDIA — cycle 2
    "dimez":   (327.95, "card", 0.55, 1.0),    # Real Dimez, boîte de nuit
    "gun":     (161.60, "full", 0.66, 1.0),    # Jason arme au poing
    "vcboat":  (182.20, "full", 0.50, 1.0),    # Vice City vue de la mer
    "port":    (451.60, "full", 0.50, 1.0),    # duo au port
    "night":   (485.20, "full", 0.50, 1.0),    # Lucia en voiture, néons
    "beach":   (488.20, "full", 0.50, 1.0),    # duo, plage
    "drequan": (407.80, "card", 0.50, 1.0),    # Dre'Quan Priest
    "cover":   (525.90, "full", 0.50, 1.0),    # reveal de la jaquette
}
CYCLES = [
    ["lucia_v", "raul", "glasses", "club", "cocktail", "palms", "dress", "bonnie"],
    ["dimez", "gun", "vcboat", "port", "night", "beach", "drequan", "cover"],
]

# ── INTRO ──
INTRO_END = 319              # fin de l'emplacement INTRO (début du zoom radial)
XFADE = (150, 180)           # fondu enchaîné entre les 2 clips de l'intro
SLIDE = (310, 330)           # le premier média monte par le bas

# ── Un cycle « YOUR MEDIA », en images relatives au début du cycle (cycle 1 = image 330) ──
#   (début, fin, type, n° du média 0-7, param)
#   fd = flash d'exposition qui retombe (param = intensité de départ)
#   flip = négatif miroir + vitre brisée · rev = lecture en arrière
#   white = flash blanc (param = niveaux) · zin/zout = zoom radial vers le blanc / depuis le blanc
CYCLE = [
    (0,   13,  "fd",    0, 0.75),
    (13,  16,  "white", 0, [0.5, 0.8, 1.0]),
    (16,  20,  "fd",    0, 0.15),
    (20,  27,  "fd",    1, 0.5),
    (27,  32,  "flip",  1, None),
    (32,  39,  "rev",   1, None),
    (39,  49,  "fd",    2, 0.7),
    (49,  51,  "white", 2, [0.85, 1.0]),
    (51,  59,  "fd",    3, 0.5),
    (59,  64,  "white", 3, [0.8, 1.0, 1.0, 1.0, 0.95]),
    (64,  79,  "zin",   2, None),
    (79,  87,  "zout",  4, None),
    (87,  96,  "fd",    4, 0.0),
    (96,  99,  "white", 4, [0.45, 0.75, 1.0]),
    (99,  100, "fd",    4, 0.0),
    (100, 108, "fd",    5, 0.45),
    (108, 113, "flip",  5, None),
    (113, 119, "rev",   5, None),
    (119, 129, "fd",    6, 0.6),
    (129, 131, "white", 6, [0.85, 1.0]),
    (131, 140, "fd",    7, 0.45),
    (140, 142, "white", 7, [1.0, 0.95]),
    (142, 150, "rev",   6, 0.4),
    (150, 152, "white", 6, [0.85, 0.8]),
    (152, 159, "zin",   7, None),
]
CYCLE_STARTS = [330, 489]
CRACKED = {3, 7}             # médias « gris » du modèle : vitre brisée par-dessus
END_FADE = 648               # flash blanc puis fondu au noir


# ══════════════════════════════════════════════════════════════════════════════
#  EFFETS
# ══════════════════════════════════════════════════════════════════════════════

_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_RAD = np.hypot(_yy - H / 2, _xx - W / 2) / np.hypot(W / 2, H / 2)

def exposure(f, a):
    """Flash d'exposition : mélange vers le blanc avec des hautes lumières qui brûlent."""
    if a <= 0:
        return f
    return f + (255 - f) * a

def white(f, a):
    return f * (1 - a) + 255 * a

def negative_mirror(f):
    return (255 - f)[:, ::-1]

def vignette(f, k):
    return f * (1 - k * np.clip(_RAD - 0.35, 0, 1)[..., None] ** 1.3)

def make_crack(seed=3):
    """Calque « vitre brisée » : fissures blanches rayonnantes + éclats, alpha doux."""
    rng = np.random.default_rng(seed)
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    cx, cy = W * 0.58, H * 0.42
    for k in range(18):
        ang = k / 18 * 2 * np.pi + rng.uniform(-0.15, 0.15)
        x, y = cx, cy
        for s in range(int(rng.integers(6, 14))):
            ang += rng.uniform(-0.35, 0.35)
            step = rng.uniform(60, 160)
            nx, ny = x + np.cos(ang) * step, y + np.sin(ang) * step
            d.line([(x, y), (nx, ny)], fill=int(rng.integers(150, 255)), width=int(rng.integers(2, 5)))
            if rng.random() < 0.25:
                a2 = ang + rng.choice([-1, 1]) * rng.uniform(0.6, 1.2)
                d.line([(nx, ny), (nx + np.cos(a2) * step * 0.6, ny + np.sin(a2) * step * 0.6)],
                       fill=180, width=2)
            x, y = nx, ny
    for r in (90, 190, 320):  # anneaux concentriques
        pts = [(cx + np.cos(t) * r * rng.uniform(0.85, 1.15), cy + np.sin(t) * r * rng.uniform(0.85, 1.15))
               for t in np.linspace(0, 2 * np.pi, 22)]
        d.line(pts + [pts[0]], fill=140, width=2)
    m = np.asarray(img.filter(ImageFilter.GaussianBlur(0.8)), np.float32)[..., None] / 255
    return m

CRACK = make_crack()

def crack(f, a=0.85):
    return f * (1 - CRACK * a * 0.6) + 255 * CRACK * a * 0.6

def shake(f, k, amp=18):
    if amp <= 0:
        return f
    rng = np.random.default_rng(k)
    dx, dy = rng.integers(-amp, amp + 1, 2)
    return np.roll(np.roll(f, int(dy), axis=0), int(dx), axis=1)

def finish(f, rng):
    f = f + rng.normal(0, 4.0, (H, W, 1)).astype(np.float32)
    return np.clip(f, 0, 255).astype(np.uint8)


# ══════════════════════════════════════════════════════════════════════════════
#  PLAN : quelle image de quel clip, avec quel effet, pour chaque image de sortie
# ══════════════════════════════════════════════════════════════════════════════

def build_plan():
    plan = [None] * N_TOTAL
    for k in range(min(INTRO_END + 11, N_TOTAL)):
        plan[k] = ("intro", k)
    for ci, base in enumerate(CYCLE_STARTS):
        for s, e, kind, m, prm in CYCLE:
            for k in range(base + s, min(base + e, N_TOTAL)):
                if k >= END_FADE:
                    break
                plan[k] = ("media", CYCLES[ci][m], m, kind, prm, k - (base + s), e - s)
    for k in range(END_FADE, N_TOTAL):
        plan[k] = ("end", k - END_FADE)
    return plan


def build(source, template, out):
    plan = build_plan()
    # position source de chaque image : chaque média avance, « rev » repart en arrière
    cur = {k: 0.0 for k in CLIPS}
    pos = [None] * N_TOTAL
    for k, p in enumerate(plan):
        if p[0] != "media":
            continue
        _, key, m, kind, prm, i, n = p
        sp = CLIPS[key][3]
        if kind == "rev":
            cur[key] = max(0.0, cur[key] - sp * 1.5)
        elif kind == "flip":
            cur[key] += sp * 0.3          # quasi-arrêt sur image pendant le négatif
        else:
            cur[key] += sp
        pos[k] = cur[key]
    need = {k: 0.0 for k in CLIPS}
    for k, p in enumerate(plan):
        if p[0] == "media":
            need[p[1]] = max(need[p[1]], pos[k])
    need["vi"] = XFADE[1] * CLIPS["vi"][3]
    need["jason_i"] = (INTRO_END + 11 - XFADE[0]) * CLIPS["jason_i"][3]

    tmp = tempfile.mkdtemp(prefix="gta6_malemo_")
    clips = {}
    for key, (start, mode, cx, sp) in CLIPS.items():
        n_src = int(need[key]) + 3
        clips[key] = Clip(source, key, start, mode, cx, n_src, tmp)
        print(f"   {key:<9} {int(start // 60)}:{start % 60:05.2f} → {start + n_src / FPS:7.2f} s"
              f"  ({mode}, éclairci ×{clips[key].gain:.2f})")

    silent = f"{tmp}/video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "slow", "-crf", "18", "-maxrate", "20M", "-bufsize", "40M",
                           "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    rng = np.random.default_rng(11)
    first = CYCLES[0][0]
    for k, p in enumerate(plan):
        if p[0] == "intro":
            # 2 clips vidéo en fondu enchaîné, poussée lente, ouverture depuis le noir
            a = np.clip((k - XFADE[0]) / (XFADE[1] - XFADE[0]), 0, 1)
            a = a * a * (3 - 2 * a)
            f = None
            if a < 1:
                f = clips["vi"].at(min(k, XFADE[1]) * CLIPS["vi"][3])
            if a > 0:
                g = clips["jason_i"].at(max(0, k - XFADE[0]) * CLIPS["jason_i"][3])
                f = g if f is None else f * (1 - a) + g * a
            f = zoom(grade(f), 1.0 + 0.12 * min(k, INTRO_END) / INTRO_END)
            f = vignette(f, 0.55)
            if k < 60:
                f = f * (k / 60) ** 1.5
            if k >= SLIDE[0]:                         # le premier média monte par le bas
                q = (k - SLIDE[0]) / (SLIDE[1] - SLIDE[0])
                q = min(1.0, q) ** 2
                g = grade(clips[first].at(0))
                y0 = int(H * (1 - q))
                if y0 < H:
                    f = f.copy()
                    f[y0:] = g[:H - y0]
            if k >= INTRO_END:                        # zoom radial qui blanchit (le drop)
                q = (k - INTRO_END) / 11
                f = exposure(radial_blur(f, 0.08 + 0.5 * q), 0.7 * q)
        elif p[0] == "media":
            _, key, m, kind, prm, i, n = p
            f = grade(clips[key].at(pos[k]))
            if kind == "fd":
                a = prm * max(0.0, 1 - i / 7) ** 1.6
                f = exposure(shake(f, k, int(16 * a)), a)
            elif kind == "white":
                f = white(f, prm[min(i, len(prm) - 1)])
            elif kind == "flip":
                f = crack(shake(negative_mirror(f), k, 10), 0.9) * 0.95 + 12
            elif kind == "rev":
                a = (prm or 0.0) * max(0.0, 1 - i / 6)
                f = exposure(f, a + 0.12 * i / max(n - 1, 1))
            elif kind == "zin":
                q = i / max(n - 1, 1)
                f = exposure(radial_blur(f, 0.05 + 0.6 * q), 0.85 * q ** 1.5)
            elif kind == "zout":
                q = 1 - i / max(n - 1, 1)
                f = exposure(radial_blur(f, 0.05 + 0.6 * q), 0.95 * q)
            if m in CRACKED and kind == "fd":
                f = crack(f, 0.8)
        else:  # fin : flash blanc puis fondu au noir
            i = p[1]
            last = grade(clips[CYCLES[1][7]].at(need[CYCLES[1][7]]))
            if i < 7:
                f = white(last, 0.9) * (1 - i / 7)
            else:
                f = np.zeros((H, W, 3), np.float32)
        ff.stdin.write(finish(f, rng).tobytes())
    ff.stdin.close(); ff.wait()

    dur = N_TOTAL / FPS
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", template,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-af", "loudnorm=I=-14:TP=-1.0:LRA=11,aresample=44100",
                    "-t", f"{dur:.3f}", "-movflags", "+faststart", out], check=True)
    print(f"✅  {out}  ({dur:.2f} s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="GTA 6 × modèle CapCut « Malemo slowed »")
    ap.add_argument("--source", required=True, help="vidéo longue GTA 6")
    ap.add_argument("--template", required=True, help="aperçu du modèle (pour la musique)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    build(a.source, a.template, a.out)
