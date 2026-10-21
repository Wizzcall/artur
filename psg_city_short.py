"""
PSG SHORT — MAN CITY 2-4 PSG (UCL · Etihad · 14 oct. 2026) + blessure de Kvaratskhelia
9:16 · ~30s · scoreboard · speed-ramp · color grade

Les 7 buts/moments de City-PSG, puis la séquence « 6 jours plus tard » :
Kvaratskhelia se blesse contre le Barça (PSG 4-2 Barça, 20 oct. 2026,
rupture du ligament croisé du genou droit).

USAGE
-----
1. pip install moviepy pillow numpy scipy
2. Mets tes extraits dans ./clips/ — le nom du fichier doit contenir la clé :
       doue  dembele  vitinha  haaland1  akliouche  haaland2  penalty  kvara
   ex. clips/01_doue.mp4, clips/kvara_blessure.mov …
   Un extrait manquant est remplacé par une carte animée (minute + score).
3. Mets la musique du modèle (mp3/m4a/wav) et lance :
       python psg_city_short.py --music musique.mp3 --music-start 0
   Sans --music, une instru phonk est générée.

OUTPUT : psg_city_short.mp4  (1080×1920 · 30fps)
"""

import argparse, subprocess, sys, tempfile, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from moviepy import VideoFileClip

from psg_storm_edit import (
    W, H, FPS, BEAT, PSG_BLUE, PSG_RED, WHITE, GOLD,
    to_9x16_frame, storm_color_grade, vignette, grain, glitch_rgb,
    zoom_frame, flash, speed_ramp, load_font, draw_text_storm,
    draw_beat_flash_bar, gen_phonk,
)

OUT       = "psg_city_short.mp4"
CITY_BLUE = (108, 171, 221)
CLIP_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".m4v")

# key, minute, line1, line2, score (MCI, PSG), beats, mood
SEGMENTS = [
    ("doue",      "13'", "DOUÉ",           "CONTRE ÉCLAIR",         (0, 1), 5, "goal"),
    ("dembele",   "15'", "DEMBÉLÉ",        "LE BALLON D'OR FRAPPE", (0, 2), 5, "goal"),
    ("vitinha",   "32'", "VITINHA",        "LE MAESTRO",            (0, 3), 5, "goal"),
    ("haaland1",  "53'", "HAALAND",        "CITY Y CROIT",          (1, 3), 4, "city"),
    ("akliouche", "62'", "AKLIOUCHE",      "LE COUP DE GRÂCE",      (1, 4), 5, "goal"),
    ("haaland2",  "75'", "HAALAND",        "DOUBLÉ",                (2, 4), 4, "city"),
    ("penalty",   "",    "PENALTY MANQUÉ", "FERRAN TORRES",         (2, 4), 5, "goal"),
    ("kvara",     "",    "KVARATSKHELIA",  "LIGAMENT CROISÉ ROMPU", None,   9, "injury"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  OVERLAYS
# ══════════════════════════════════════════════════════════════════════════════

def fit(text: str, size: int, max_w: int = W - 120) -> int:
    """Largest font size <= size so the text fits within max_w."""
    while size > 30 and load_font(size).getlength(text) > max_w:
        size -= 4
    return size


def title(img, line1, line2, y_frac, alpha, size):
    return draw_text_storm(img, line1, line2, y_frac=y_frac, alpha=alpha, size=fit(line1, size))


def draw_scoreboard(img: np.ndarray, score, minute: str = "") -> np.ndarray:
    """TV-style score bug at the top: MCI 1-3 PSG · 53'."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)
    f    = load_font(46)
    y0, y1 = 150, 230
    x0, x1 = 170, W - 170
    draw.rounded_rectangle([x0, y0, x1, y1], radius=18, fill=(10, 10, 20, 225))
    draw.rectangle([x0 + 18, y0 + 12, x0 + 28, y1 - 12], fill=(*CITY_BLUE, 255))
    draw.rectangle([x1 - 28, y0 + 12, x1 - 18, y1 - 12], fill=(*PSG_RED, 255))
    cy = (y0 + y1) // 2
    draw.text((x0 + 120, cy), "MCI", font=f, fill=(*WHITE, 255), anchor="mm")
    draw.text((x1 - 120, cy), "PSG", font=f, fill=(*WHITE, 255), anchor="mm")
    draw.rectangle([W//2 - 90, y0 + 8, W//2 + 90, y1 - 8], fill=(*PSG_BLUE, 255))
    draw.text((W//2, cy), f"{score[0]} - {score[1]}", font=f, fill=(*GOLD, 255), anchor="mm")
    if minute:
        draw.rounded_rectangle([W//2 - 60, y1 + 6, W//2 + 60, y1 + 56], radius=10,
                               fill=(*PSG_RED, 235))
        draw.text((W//2, y1 + 31), minute, font=load_font(34), fill=(*WHITE, 255), anchor="mm")
    return np.array(Image.alpha_composite(pil, ovl).convert("RGB"))


def gradient_bg(top, bottom) -> np.ndarray:
    r = np.linspace(0, 1, H)[:, None, None]
    img = np.array(top, np.float32) * (1 - r) + np.array(bottom, np.float32) * r
    return np.repeat(img, W, axis=1).astype(np.uint8)


def card_frame(p: float, big: str, mood: str) -> np.ndarray:
    """Animated stand-in when no clip is provided: huge minute/word + rings."""
    if mood == "injury":
        img = gradient_bg((25, 0, 5), (0, 0, 0))
    elif mood == "city":
        img = gradient_bg((10, 40, 70), (0, 5, 20))
    else:
        img = gradient_bg((0, 15, 70), (60, 0, 15))
    pil  = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    for ring in range(4):
        rr = int(((ring * 0.25 + p * 0.6) % 1.0) * W * 0.9)
        c  = PSG_RED if ring % 2 == 0 else GOLD
        draw.ellipse([W//2 - rr, H//2 - rr, W//2 + rr, H//2 + rr], outline=c, width=6)
    if big:
        draw.text((W//2, int(H * 0.47)), big, font=load_font(330),
                  fill=(255, 255, 255), anchor="mm", stroke_width=10, stroke_fill=(0, 0, 0))
    return zoom_frame(np.array(pil), 1.0 + 0.08 * p)


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCES
# ══════════════════════════════════════════════════════════════════════════════

def find_clip(clips_dir: Path, key: str):
    if not clips_dir.exists():
        return None
    hits = sorted(p for p in clips_dir.iterdir()
                  if p.suffix.lower() in CLIP_EXTS and key in p.stem.lower())
    return str(hits[0]) if hits else None


def clip_frames(path: str, n: int) -> list[np.ndarray]:
    """n frames from the clip, centred on its middle (where the action usually is)."""
    cap = VideoFileClip(path)
    dur = n / FPS
    start = max(0.0, (cap.duration - dur) / 2)
    out = []
    for i in range(n):
        t = min(start + i / FPS, cap.duration - 1e-3)
        out.append(to_9x16_frame(cap.get_frame(t).astype(np.uint8)))
    cap.close()
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  SEQUENCES (generators → streamed to ffmpeg, never all in RAM)
# ══════════════════════════════════════════════════════════════════════════════

def intro(n: int):
    for i in range(n):
        p = i / n
        img = card_frame(p, "", "goal")
        img = title(img, "MAN CITY 2-4 PSG", "ETIHAD STADIUM · 14.10.2026",
                              0.44, min(1.0, p * 3), 105)
        img = draw_text_storm(img, "LIGUE DES CHAMPIONS", "", y_frac=0.30,
                              alpha=min(1.0, p * 3), size=60)
        if i < 3:
            img = flash(img, 1 - i / 3)
        yield grain(img, 0.02)


def segment(seg, clips_dir: Path):
    key, minute, line1, line2, score, beats, mood = seg
    n   = int(beats * BEAT * FPS)
    src = find_clip(clips_dir, key)
    if src:
        print(f"   {line1:<16} ← {Path(src).name}")
        raw    = clip_frames(src, n)
        slow   = 0.35 if mood == "injury" else 0.25
        frames = speed_ramp(raw, FPS, FPS, slow_factor=slow, slow_start=0.35, slow_end=0.65)[:n]
        frames += [frames[-1]] * (n - len(frames))
    else:
        print(f"   {line1:<16} ← (carte animée, pas de clip '{key}')")
        big = "" if mood == "injury" else (minute or "!")
        frames = [card_frame(i / n, big, mood) for i in range(n)]

    for i, f in enumerate(frames):
        p      = i / n
        t      = i / FPS
        beat_p = (t % BEAT) / BEAT
        f = storm_color_grade(f)
        if mood == "injury":
            # Desaturate + red tint + slow push-in
            lum = f.mean(axis=2, keepdims=True)
            f   = np.clip(lum * 0.8 + f * 0.2 + np.array([40, -10, -10]), 0, 255).astype(np.uint8)
            f   = zoom_frame(f, 1.0 + 0.15 * p)
            f   = vignette(f, 0.8)
        else:
            if p < 0.15:
                f = zoom_frame(f, 1.0 + 0.2 * (1 - p / 0.15))
            if beat_p < 0.05 and mood == "goal":
                f = glitch_rgb(f, 1.0)
            f = vignette(f, 0.5)
            if beat_p < 0.035:
                f = flash(f, 0.3 * (1 - beat_p / 0.035))
        f = grain(f, 0.02)

        alpha = min(1.0, p * 5) * (1.0 if p < 0.85 else (1 - p) / 0.15)
        if mood == "injury":
            f = draw_text_storm(f, "6 JOURS PLUS TARD…", "PSG 4-2 BARÇA · 20.10.2026",
                                y_frac=0.20, alpha=min(1.0, p * 4), size=70)
            if p > 0.35:
                a = min(1.0, (p - 0.35) * 5)
                f = title(f, line1, line2, y_frac=0.74, alpha=a, size=100)
        else:
            f = draw_scoreboard(f, score, minute)
            f = title(f, line1, line2, y_frac=0.76, alpha=alpha, size=110)
        if i == 0:
            f = flash(f, 0.9)
        yield draw_beat_flash_bar(f, p)


def outro(n: int):
    for i in range(n):
        p = i / n
        img = card_frame(p, "", "injury")
        img = title(img, "FORCE KVARA", "REVIENS PLUS FORT · #7",
                              y_frac=0.45, alpha=min(1.0, p * 3), size=120)
        img = np.clip(img.astype(np.float32) * (1 - max(0, p - 0.8) * 5), 0, 255).astype(np.uint8)
        yield img


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════════════════════════════════════════

def write_wav(path: str, data: np.ndarray, sr: int):
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1] if pcm.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def build(clips_dir: Path, music, music_start: float):
    n_intro, n_outro = int(4 * BEAT * FPS), int(5 * BEAT * FPS)
    n_total = n_intro + n_outro + sum(int(s[5] * BEAT * FPS) for s in SEGMENTS)
    dur     = n_total / FPS
    print(f"\n🎬  Man City 2-4 PSG + Kvara — {dur:.1f}s")

    tmp       = tempfile.mkdtemp(prefix="psg_city_")
    silent_mp4 = f"{tmp}/video.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", silent_mp4],
        stdin=subprocess.PIPE)

    def frames():
        yield from intro(n_intro)
        for seg in SEGMENTS:
            yield from segment(seg, clips_dir)
        yield from outro(n_outro)

    for f in frames():
        ff.stdin.write(np.ascontiguousarray(f, dtype=np.uint8).tobytes())
    ff.stdin.close()
    ff.wait()

    if music:
        print(f"🎵  Musique : {music} (à partir de {music_start}s)")
        audio_in = ["-ss", str(music_start), "-i", music]
    else:
        print("🎵  Pas de --music → instru phonk générée")
        data, sr = gen_phonk(dur + 0.5)
        write_wav(f"{tmp}/phonk.wav", data, sr)
        audio_in = ["-i", f"{tmp}/phonk.wav"]

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", silent_mp4, *audio_in,
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-af", f"afade=t=out:st={dur - 1.2:.2f}:d=1.2", "-t", f"{dur:.2f}", OUT],
        check=True)
    print(f"✅  {OUT}")


def main():
    ap = argparse.ArgumentParser(description="Short Man City 2-4 PSG + blessure Kvaratskhelia")
    ap.add_argument("--clips-dir",   default="./clips", help="dossier des extraits du match")
    ap.add_argument("--music",       default=None,      help="fichier audio du modèle (mp3/m4a/wav)")
    ap.add_argument("--music-start", type=float, default=0.0,
                    help="seconde de la musique où commencer (ex. le drop)")
    args = ap.parse_args()
    if args.music and not Path(args.music).exists():
        sys.exit(f"❌  Musique introuvable : {args.music}")
    build(Path(args.clips_dir), args.music, args.music_start)


if __name__ == "__main__":
    main()
