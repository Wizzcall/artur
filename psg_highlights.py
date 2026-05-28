"""
PSG All-Time Highlights Edit — 30 seconds
Generates a cinematic video montage with animated cards, transitions and an epic synthetic soundtrack.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import moviepy as mp
from moviepy import VideoClip, AudioClip, CompositeVideoClip, ImageClip, concatenate_videoclips
from moviepy.audio.AudioClip import AudioArrayClip
import scipy.signal as signal
import os, math

# ─── Constants ────────────────────────────────────────────────────────────────
FPS      = 30
W, H     = 1920, 1080
DURATION = 30.0
OUT_FILE = "psg_highlights_30s.mp4"

PSG_NAVY  = (0,   30,  99)
PSG_RED   = (218, 22,  40)
PSG_WHITE = (255, 255, 255)
PSG_GOLD  = (218, 165, 32)

# ─── Moment cards ─────────────────────────────────────────────────────────────
MOMENTS = [
    # (start, duration, player, moment_text, sub_text)
    (0.0,  4.0, "PARIS SAINT-GERMAIN",    "ALL-TIME HIGHLIGHTS",       "Est. 1970 · Parc des Princes"),
    (4.0,  3.5, "RONALDINHO",              "LA MAGIE DU DRIBBLE",       "2001–2003 · Le génie brésilien"),
    (7.5,  3.5, "ZLATAN IBRAHIMOVIĆ",      "38 BUTS EN LIGUE 1",        "2012–2016 · Le roi de Paris"),
    (11.0, 3.0, "EDINSON CAVANI",          "MEILLEUR BUTEUR ALL-TIME",  "200 buts · 2013–2020"),
    (14.0, 3.0, "6-1 CONTRE BARCELONE",   "REMONTADA PARISIENNE",      "6 Mars 2017 · Parc des Princes"),
    (17.0, 3.0, "NEYMAR JR",              "LE TRANSFERT DU SIÈCLE",    "222M€ · 2017 · Fantaisie pure"),
    (20.0, 3.0, "KYLIAN MBAPPÉ",          "PRODIGE DE BONDY",          "Hat-trick · UCL · Légende"),
    (23.0, 3.0, "FINALE UCL 2020",        "AU SOMMET DE L'EUROPE",     "Champions League · Lisbonne"),
    (26.0, 4.0, "PARIS SAINT-GERMAIN",    "ICI C'EST PARIS",           "Forever our club 🔵🔴"),
]

# ─── Audio synthesis ──────────────────────────────────────────────────────────

def synth_audio(total_dur: float, sr: int = 44100) -> np.ndarray:
    """Generate a cinematic/epic electronic soundtrack."""
    n      = int(total_dur * sr)
    t      = np.linspace(0, total_dur, n, endpoint=False)

    # ── Base kick ──────────────────────────────────────────────────────────────
    bpm    = 130
    beat   = 60.0 / bpm
    kick   = np.zeros(n)
    for i in range(int(total_dur / beat) + 1):
        ts = i * beat
        idx = int(ts * sr)
        if idx >= n:
            break
        env = np.exp(-20 * np.linspace(0, 0.1, min(int(0.1 * sr), n - idx)))
        freq_sweep = 60 * np.exp(-30 * np.linspace(0, 0.05, len(env)))
        seg = np.sin(2 * np.pi * freq_sweep * np.linspace(0, 0.1, len(env)))
        kick[idx:idx + len(env)] += seg * env * 0.7

    # ── Hi-hat pattern ─────────────────────────────────────────────────────────
    hat = np.zeros(n)
    for i in range(int(total_dur / (beat / 2)) + 1):
        ts  = i * beat / 2
        idx = int(ts * sr)
        if idx >= n:
            break
        l   = min(int(0.02 * sr), n - idx)
        env = np.exp(-80 * np.linspace(0, 0.02, l))
        noise = np.random.randn(l)
        seg = noise * env * 0.15
        hat[idx:idx + l] += seg

    # ── Sub-bass ───────────────────────────────────────────────────────────────
    bass_notes = [55, 55, 62, 65, 55, 55, 62, 69]  # A1,A1,D2,F2…
    bass       = np.zeros(n)
    note_dur   = beat * 2
    for i, note in enumerate(bass_notes * (int(total_dur / (note_dur * len(bass_notes))) + 1)):
        ts  = i * note_dur
        if ts >= total_dur:
            break
        freq = note * 2 ** ((note - 69) / 12) / (note * 2 ** ((note - 69) / 12)) * note
        freq_hz = 440 * 2 ** ((note - 69) / 12)
        l       = min(int(note_dur * sr), n - int(ts * sr))
        env     = np.ones(l)
        env[:int(0.01 * sr)] = np.linspace(0, 1, int(0.01 * sr))
        env[-int(0.05 * sr):] = np.linspace(1, 0, int(0.05 * sr))
        seg = np.sin(2 * np.pi * freq_hz * np.linspace(0, note_dur, l)) * env * 0.4
        bass[int(ts * sr):int(ts * sr) + l] += seg

    # ── Lead synth (epic melody) ───────────────────────────────────────────────
    melody_notes = [69, 72, 74, 76, 74, 72, 69, 71,
                    72, 74, 76, 79, 77, 76, 74, 72]
    mel         = np.zeros(n)
    note_dur    = beat
    for i, note in enumerate(melody_notes * (int(total_dur / (note_dur * len(melody_notes))) + 1)):
        ts = i * note_dur
        if ts >= total_dur:
            break
        freq_hz = 440 * 2 ** ((note - 69) / 12)
        l       = min(int(note_dur * 0.9 * sr), n - int(ts * sr))
        env     = np.ones(l)
        env[:int(0.005 * sr)] = np.linspace(0, 1, max(1, int(0.005 * sr)))
        env[-int(0.1 * sr):]  = np.linspace(1, 0, max(1, int(0.1 * sr)))
        # Sawtooth + detuned copy for richness
        phase = np.linspace(0, note_dur * 0.9, l)
        saw1  = signal.sawtooth(2 * np.pi * freq_hz * phase)
        saw2  = signal.sawtooth(2 * np.pi * freq_hz * 1.005 * phase)
        seg   = (saw1 + saw2) * 0.5 * env * 0.18
        mel[int(ts * sr):int(ts * sr) + l] += seg

    # ── Pad / atmosphere ───────────────────────────────────────────────────────
    pad = np.zeros(n)
    for freq_hz in [110, 165, 220, 275]:
        pad += np.sin(2 * np.pi * freq_hz * t) * 0.04

    # ── Build-up swell ─────────────────────────────────────────────────────────
    swell = np.linspace(0, 1, n) ** 1.5

    mix = (kick + hat + bass + mel * swell + pad) * 0.6
    # Soft limiter
    mix = np.tanh(mix * 1.2) * 0.85

    # Stereo
    stereo = np.stack([mix, mix], axis=1)
    stereo = (stereo * 32767).astype(np.int16)
    return stereo, sr


# ─── Visual helpers ───────────────────────────────────────────────────────────

def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)

def draw_gradient(draw: ImageDraw.ImageDraw, bbox, color_a, color_b, vertical=True):
    x0, y0, x1, y1 = bbox
    steps = y1 - y0 if vertical else x1 - x0
    for i in range(steps):
        r = i / max(steps - 1, 1)
        c = tuple(int(a + (b - a) * r) for a, b in zip(color_a, color_b))
        if vertical:
            draw.line([(x0, y0 + i), (x1, y0 + i)], fill=c)
        else:
            draw.line([(x0 + i, y0), (x0 + i, y1)], fill=c)

def draw_psg_badge(img: Image.Image, cx: int, cy: int, radius: int, alpha: float = 1.0):
    """Draw a simplified PSG shield badge."""
    draw = ImageDraw.Draw(img, "RGBA")
    a    = int(255 * alpha)

    # Outer circle — navy
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                 fill=(*PSG_NAVY, a), outline=(*PSG_GOLD, a), width=4)

    # Inner ring — red arc bands (simplified)
    inner = int(radius * 0.7)
    draw.ellipse([cx - inner, cy - inner, cx + inner, cy + inner],
                 fill=(*PSG_RED, a))

    # Centre circle — white
    tiny = int(radius * 0.4)
    draw.ellipse([cx - tiny, cy - tiny, cx + tiny, cy + tiny],
                 fill=(*PSG_WHITE, a))

    # "PSG" text in centre
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                  max(10, radius // 3))
    except Exception:
        font = ImageFont.load_default()
    draw.text((cx, cy), "PSG", fill=(*PSG_NAVY, a), font=font, anchor="mm")


def make_stars_layer(seed: int = 0) -> Image.Image:
    rng   = np.random.default_rng(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    for _ in range(200):
        x = rng.integers(0, W)
        y = rng.integers(0, H)
        r = rng.integers(1, 3)
        bri = rng.integers(150, 255)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(bri, bri, bri, bri))
    return layer


def make_moment_frame(player: str, moment: str, sub: str,
                      progress: float, is_intro: bool = False,
                      is_outro: bool = False) -> Image.Image:
    """Render a single frame for a highlight card."""
    img  = Image.new("RGB", (W, H), PSG_NAVY)
    draw = ImageDraw.Draw(img)

    # ── Background gradient ────────────────────────────────────────────────────
    draw_gradient(draw, (0, 0, W, H), PSG_NAVY, (0, 10, 60), vertical=True)

    # ── Diagonal accent stripe ─────────────────────────────────────────────────
    stripe_x = int(W * 0.6 + progress * 0 )
    poly = [(stripe_x, 0), (stripe_x + 200, 0),
            (stripe_x + 200 - 300, H), (stripe_x - 300, H)]
    draw.polygon(poly, fill=(PSG_RED[0], PSG_RED[1], PSG_RED[2]))

    # ── Stars ──────────────────────────────────────────────────────────────────
    stars = make_stars_layer(42)
    img.paste(Image.new("RGB", (W, H), PSG_NAVY), (0, 0))  # refresh base
    # Re-draw gradient on clean base
    draw = ImageDraw.Draw(img)
    draw_gradient(draw, (0, 0, W, H), PSG_NAVY, (0, 10, 60), vertical=True)
    draw.polygon(poly, fill=PSG_RED)
    img = Image.alpha_composite(img.convert("RGBA"), stars).convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Horizontal red bar at bottom ───────────────────────────────────────────
    draw.rectangle([0, H - 8, W, H], fill=PSG_RED)
    draw.rectangle([0, H - 16, W, H - 8], fill=PSG_GOLD)

    # ── Badge ──────────────────────────────────────────────────────────────────
    badge_alpha = ease_in_out(min(progress * 3, 1.0))
    badge_x     = int(W * 0.82)
    badge_y     = int(H * 0.5)
    draw_psg_badge(img, badge_x, badge_y, 120, badge_alpha)

    # ── Fonts ──────────────────────────────────────────────────────────────────
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    def load_font(size):
        for p in font_paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    font_huge   = load_font(100)
    font_big    = load_font(72)
    font_med    = load_font(44)
    font_small  = load_font(30)

    # ── Slide-in animation ─────────────────────────────────────────────────────
    ease       = ease_in_out(min(progress * 2, 1.0))
    slide_off  = int((1.0 - ease) * 120)

    # ── Player name ───────────────────────────────────────────────────────────
    py = int(H * 0.35) - slide_off
    # Shadow
    draw.text((82, py + 4), player, font=font_big,
              fill=(0, 0, 0), anchor="lm")
    draw.text((80, py), player, font=font_big,
              fill=PSG_WHITE, anchor="lm")

    # ── Moment text ───────────────────────────────────────────────────────────
    my = int(H * 0.52) - slide_off
    draw.text((82, my + 3), moment, font=font_huge,
              fill=(0, 0, 0), anchor="lm")
    draw.text((80, my), moment, font=font_huge,
              fill=PSG_RED, anchor="lm")

    # ── Sub text ──────────────────────────────────────────────────────────────
    sy = int(H * 0.66) - slide_off
    draw.text((80, sy), sub, font=font_med,
              fill=PSG_GOLD, anchor="lm")

    # ── Progress bar ──────────────────────────────────────────────────────────
    bar_w = int(W * 0.55 * progress)
    draw.rectangle([80, H - 30, 80 + bar_w, H - 22], fill=PSG_WHITE)

    return img


def make_flash_frame(progress: float, color=PSG_WHITE) -> Image.Image:
    """White / coloured flash frame for transitions."""
    alpha = max(0, 1.0 - progress * 4)
    img   = Image.new("RGB", (W, H), color)
    overlay = Image.new("RGB", (W, H), PSG_NAVY)
    img     = Image.blend(img, overlay, 1.0 - alpha)
    return img


# ─── Build video ──────────────────────────────────────────────────────────────

def build_video():
    print("🎬  Generating PSG highlights edit…")

    clips = []

    for idx, (start, dur, player, moment, sub) in enumerate(MOMENTS):
        is_intro = idx == 0
        is_outro = idx == len(MOMENTS) - 1

        def make_frame(t, _player=player, _moment=moment, _sub=sub,
                       _dur=dur, _is_intro=is_intro, _is_outro=is_outro):
            progress = t / _dur
            return np.array(make_moment_frame(
                _player, _moment, _sub, progress, _is_intro, _is_outro))

        clip = VideoClip(make_frame, duration=dur).with_fps(FPS)

        # Flash transition (except last)
        if not is_outro:
            def make_flash(t):
                return np.array(make_flash_frame(t, PSG_WHITE))
            flash = VideoClip(make_flash, duration=0.2).with_fps(FPS)
            clips.append(clip)
            clips.append(flash)
        else:
            # Fade-out on last clip
            clip = clip.with_effects([mp.video.fx.FadeOut(1.0)])
            clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")

    # ── Audio ──────────────────────────────────────────────────────────────────
    print("🎵  Synthesising soundtrack…")
    audio_arr, sr = synth_audio(final.duration)
    audio_arr_float = audio_arr.astype(np.float32) / 32767.0
    audio_clip = AudioArrayClip(audio_arr_float, fps=sr)
    audio_clip = audio_clip.with_effects([mp.audio.fx.AudioFadeOut(1.5)])

    final = final.with_audio(audio_clip)

    print(f"⏱   Duration: {final.duration:.1f}s  ({FPS} fps  {W}×{H})")
    print(f"💾  Writing → {OUT_FILE}")
    final.write_videofile(
        OUT_FILE,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        logger="bar",
    )
    print(f"\n✅  Done! → {OUT_FILE}")
    return OUT_FILE


if __name__ == "__main__":
    build_video()
