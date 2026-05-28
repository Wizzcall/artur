"""
PSG TikTok Edit – 9:16 · 1080×1920 · 30 fps · ~30 s
Phonk soundtrack + beat-synced cuts + glitch/zoom transitions + color grade
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops
from moviepy import VideoClip, AudioClip, CompositeVideoClip, concatenate_videoclips
from moviepy.audio.AudioClip import AudioArrayClip
import moviepy as mp
import scipy.signal as signal
import scipy.ndimage as ndimage
import math, random, os

# ─── Config ───────────────────────────────────────────────────────────────────
W, H    = 1080, 1920
FPS     = 30
BPM     = 140
SR      = 44100
BEAT    = 60.0 / BPM          # ~0.429 s
OUT     = "psg_tiktok.mp4"

# Color palettes
NAVY    = np.array([0,   20,  80 ], dtype=np.uint8)
RED     = np.array([220, 20,  40 ], dtype=np.uint8)
WHITE   = np.array([255, 255, 255], dtype=np.uint8)
GOLD    = np.array([255, 200, 30 ], dtype=np.uint8)
PURPLE  = np.array([80,  0,   160], dtype=np.uint8)
CYAN    = np.array([0,   200, 255], dtype=np.uint8)

rng = np.random.default_rng(7)

# ─── Phonk music ──────────────────────────────────────────────────────────────

def generate_phonk(total: float) -> tuple[np.ndarray, int]:
    n = int(total * SR)
    t = np.linspace(0, total, n, endpoint=False)
    out = np.zeros(n, dtype=np.float64)

    def env_adsr(length, a=0.005, d=0.03, s=0.6, r=0.05):
        e = np.ones(length) * s
        ai = min(int(a * SR), length)
        di = min(int(d * SR), length - ai)
        ri = min(int(r * SR), length - ai - di)
        e[:ai] = np.linspace(0, 1, ai)
        e[ai:ai+di] = np.linspace(1, s, di)
        e[-ri:] = np.linspace(s, 0, ri)
        return e

    # ── 808 bass kick ──────────────────────────────────────────────────────────
    for i in range(int(total / BEAT) + 1):
        ts  = i * BEAT
        idx = int(ts * SR)
        if idx >= n: break
        dur = min(int(0.55 * SR), n - idx)
        env = np.exp(-6 * np.linspace(0, 1, dur))
        freq = 55 * np.exp(-18 * np.linspace(0, 0.08, dur))   # pitch sweep 55→~20 Hz
        punch_dur = min(int(0.025 * SR), dur)
        punch_freq = np.linspace(200, 55, punch_dur)
        osc = np.sin(2 * np.pi * np.cumsum(freq) / SR)
        distorted = np.tanh(osc * 3.5) * 0.7
        out[idx:idx+dur] += distorted * env * 0.85

    # ── Kick transient ─────────────────────────────────────────────────────────
    for i in range(int(total / BEAT) + 1):
        ts  = i * BEAT
        idx = int(ts * SR)
        if idx >= n: break
        l = min(int(0.04 * SR), n - idx)
        noise = rng.standard_normal(l)
        env   = np.exp(-80 * np.linspace(0, 1, l))
        out[idx:idx+l] += noise * env * 0.3

    # ── Snare (on 2 & 4) ──────────────────────────────────────────────────────
    for i in range(int(total / (BEAT * 2)) + 1):
        for offset in [BEAT, BEAT * 3]:
            ts  = i * BEAT * 4 + offset
            idx = int(ts * SR)
            if idx >= n: break
            l  = min(int(0.18 * SR), n - idx)
            noise = rng.standard_normal(l)
            env   = np.exp(-18 * np.linspace(0, 1, l))
            # Add a snare tone
            tone  = np.sin(2 * np.pi * 200 * np.linspace(0, 0.18, l)) * np.exp(-25 * np.linspace(0, 1, l))
            out[idx:idx+l] += (noise * env * 0.4 + tone * 0.3) * 0.55

    # ── Cowbell hi-hat (phonk signature) ──────────────────────────────────────
    cowbell_freqs = [562, 845]          # classic TR-808 cowbell harmonics
    for i in range(int(total / (BEAT / 2)) + 1):
        ts  = i * BEAT / 2
        # Accent every beat
        amp  = 0.35 if i % 2 == 0 else 0.2
        idx = int(ts * SR)
        if idx >= n: break
        l = min(int(0.12 * SR), n - idx)
        env = np.exp(-30 * np.linspace(0, 1, l))
        sig = np.zeros(l)
        for f in cowbell_freqs:
            sig += np.sin(2 * np.pi * f * np.linspace(0, 0.12, l))
        out[idx:idx+l] += sig * env * amp * 0.3

    # ── Closed hi-hat (16th grid) ──────────────────────────────────────────────
    for i in range(int(total / (BEAT / 4)) + 1):
        ts  = i * BEAT / 4
        idx = int(ts * SR)
        if idx >= n: break
        l   = min(int(0.015 * SR), n - idx)
        noise = rng.standard_normal(l)
        env   = np.exp(-200 * np.linspace(0, 1, l))
        out[idx:idx+l] += noise * env * 0.12

    # ── Dark phonk chord (Memphis trap chords) ─────────────────────────────────
    chord_prog = [
        (0,     [46, 50, 53]),   # Bb minor
        (BEAT*8, [44, 47, 51]),  # Ab minor
        (BEAT*16,[41, 44, 48]),  # F minor
        (BEAT*24,[43, 46, 50]),  # G minor
    ]
    for start_beat, notes in chord_prog * (int(total / (BEAT * 32)) + 1):
        for note in notes:
            ts  = start_beat
            if ts >= total: break
            freq_hz = 440 * 2 ** ((note - 69) / 12)
            dur_s   = min(BEAT * 8, total - ts)
            l       = int(dur_s * SR)
            if l <= 0: break
            env = env_adsr(l)
            phase = np.linspace(0, dur_s, l)
            # Detuned saw pad (classic phonk chord)
            saw = sum(signal.sawtooth(2 * np.pi * freq_hz * d * phase) for d in [1.0, 1.008, 0.993]) / 3
            # Heavy LP filter  (dark phonk tone)
            b, a = signal.butter(2, 800 / (SR / 2), btype='low')
            saw  = signal.lfilter(b, a, saw)
            idx  = int(ts * SR)
            end  = min(idx + l, n)
            out[idx:end] += saw[:end-idx] * env[:end-idx] * 0.18

    # ── Sub bass (phonk walk) ──────────────────────────────────────────────────
    bass_notes = [34, 34, 36, 38, 34, 34, 31, 33]   # low sub octave
    for i, note in enumerate(bass_notes * (int(total / (BEAT * len(bass_notes))) + 1)):
        ts = i * BEAT
        if ts >= total: break
        freq_hz = 440 * 2 ** ((note - 69) / 12)
        dur_s   = min(BEAT * 0.9, total - ts)
        l       = int(dur_s * SR)
        if l <= 0: break
        env   = env_adsr(l, a=0.003, d=0.05, s=0.7, r=0.04)
        phase = np.linspace(0, dur_s, l)
        sub   = np.sin(2 * np.pi * freq_hz * phase)
        sub   = np.tanh(sub * 4) * 0.6    # soft clip for that distorted 808 sub
        idx   = int(ts * SR)
        end   = min(idx + l, n)
        out[idx:end] += sub[:end-idx] * env[:end-idx] * 0.5

    # ── Master ────────────────────────────────────────────────────────────────
    # Sidechain compression simulation (duck on beat)
    sidechain = np.ones(n)
    for i in range(int(total / BEAT) + 1):
        idx = int(i * BEAT * SR)
        if idx >= n: break
        l = min(int(0.15 * SR), n - idx)
        duck = 1 - 0.7 * np.exp(-30 * np.linspace(0, 1, l))
        sidechain[idx:idx+l] = np.minimum(sidechain[idx:idx+l], duck)

    out = out * sidechain

    # Build-up volume swell over 30s
    swell = np.clip(np.linspace(0.5, 1.0, n) ** 0.7, 0, 1)
    out  *= swell

    # Hard limiter
    out = np.tanh(out * 1.4) * 0.92

    # Fade in/out
    fade = min(int(0.2 * SR), n)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)

    stereo = np.stack([out, out], axis=1).astype(np.float32)
    return stereo, SR


# ─── Scene generators ─────────────────────────────────────────────────────────

def noise2d(h, w, scale=8, octaves=4):
    """Simple fractal noise."""
    arr = np.zeros((h, w))
    amp, freq = 1.0, 1.0
    for _ in range(octaves):
        s  = max(1, int(scale / freq))
        base = rng.random((h // s + 2, w // s + 2))
        zoomed = ndimage.zoom(base, (h / base.shape[0], w / base.shape[1]), order=1)
        arr += zoomed[:h, :w] * amp
        amp  *= 0.5
        freq *= 2.0
    return (arr - arr.min()) / (arr.max() - arr.min() + 1e-8)

def make_pitch_bg(progress: float = 0.0, cam_shake: float = 0.0) -> np.ndarray:
    """Generate a football pitch view (top-down / slight tilt)."""
    img = np.zeros((H, W, 3), dtype=np.uint8)

    # ── Grass ────────────────────────────────────────────────────────────────
    grass_noise = noise2d(H, W, scale=40, octaves=3)
    stripe_mask = np.abs(np.sin(np.arange(H) * np.pi / 30))[:, None]  # (H,1)

    dark_green  = np.array([30,  80,  30 ])
    light_green = np.array([50,  110, 45 ])

    # grass: (H,3) → broadcast to (H,W,3)
    grass_1d = (dark_green * (1 - stripe_mask) + light_green * stripe_mask).astype(np.uint8)  # (H,3)
    grass    = np.broadcast_to(grass_1d[:, None, :], (H, W, 3)).copy()                         # (H,W,3)
    noise_rgb = (grass_noise[:, :, None] * 15).astype(np.int16)                                # (H,W,1)
    img = np.clip(grass.astype(np.int16) + noise_rgb, 0, 255).astype(np.uint8)

    # ── Pitch markings ────────────────────────────────────────────────────────
    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    lw   = 6

    # Border
    draw.rectangle([80, 120, W-80, H-120], outline=(230,230,230), width=lw)
    # Centre line (horizontal)
    draw.line([(80, H//2), (W-80, H//2)], fill=(230,230,230), width=lw)
    # Centre circle
    cx, cy, cr = W//2, H//2, 160
    draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], outline=(230,230,230), width=lw)
    draw.ellipse([cx-8, cy-8, cx+8, cy+8], fill=(230,230,230))
    # Penalty boxes
    pb_w, pb_h = 420, 260
    draw.rectangle([W//2-pb_w//2, 120, W//2+pb_w//2, 120+pb_h], outline=(230,230,230), width=lw)
    draw.rectangle([W//2-pb_w//2, H-120-pb_h, W//2+pb_w//2, H-120], outline=(230,230,230), width=lw)
    # Goals
    gw, gd = 180, 55
    draw.rectangle([W//2-gw//2, 60, W//2+gw//2, 120], outline=(230,230,230), width=lw)
    draw.rectangle([W//2-gw//2, H-120, W//2+gw//2, H-60], outline=(230,230,230), width=lw)

    img = np.array(pil)

    # Camera shake
    if cam_shake > 0:
        sx = int(rng.integers(-8, 8) * cam_shake)
        sy = int(rng.integers(-8, 8) * cam_shake)
        img = np.roll(img, sx, axis=1)
        img = np.roll(img, sy, axis=0)

    return img

def make_crowd_bg(progress: float = 0.0) -> np.ndarray:
    """Blurred crowd / stadium scene."""
    img = np.zeros((H, W, 3), dtype=np.uint8)

    # Background gradient – stadium night atmosphere
    for y in range(H):
        r = y / H
        color = (
            int(10 + r * 20),
            int(5  + r * 15),
            int(30 + r * 40),
        )
        img[y, :] = color

    # Crowd dots (bokeh lights)
    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    for _ in range(600):
        x = int(rng.integers(0, W))
        y = int(rng.integers(0, H * 2 // 3))
        r = int(rng.integers(2, 8))
        bri = int(rng.integers(120, 255))
        hue_r = [bri, int(bri * 0.2), int(bri * 0.1)]  # warm lights
        if rng.random() > 0.7:
            hue_r = [int(bri * 0.1), int(bri * 0.4), bri]  # cold lights
        draw.ellipse([x-r, y-r, x+r, y+r], fill=tuple(hue_r))

    img = np.array(pil)
    # Heavy blur → bokeh
    from scipy.ndimage import gaussian_filter
    img = gaussian_filter(img.astype(float), sigma=12).astype(np.uint8)
    return img

def make_action_scene(scene_id: int, progress: float, cam_shake: float = 0.0) -> np.ndarray:
    """Compose a 'match action' frame."""
    if scene_id % 3 == 0:
        bg = make_pitch_bg(progress, cam_shake)
    else:
        bg = make_crowd_bg(progress)

    pil = Image.fromarray(bg).convert("RGBA")

    # ── Simulated player silhouette ───────────────────────────────────────────
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    # Simple player shapes using ellipses + rectangles
    positions = [
        (W//2 - 100, H*2//3 - 80),
        (W//2 + 60,  H*2//3 - 40),
        (W//2 - 200, H*2//3),
    ]
    for px, py in positions:
        # Body
        draw.ellipse([px-25, py-80, px+25, py+30], fill=(30,30,30,200))
        # Head
        draw.ellipse([px-18, py-110, px+18, py-75], fill=(60,40,30,200))
        # Legs
        leg_swing = int(20 * math.sin(progress * math.pi * 4))
        draw.line([(px-10, py+30), (px-15+leg_swing, py+90)], fill=(30,30,30,200), width=12)
        draw.line([(px+10, py+30), (px+15-leg_swing, py+90)], fill=(30,30,30,200), width=12)

    # Ball
    bx = int(W//2 + 80 * math.sin(progress * math.pi * 2))
    by = int(H*2//3 + 20 * math.cos(progress * math.pi * 3))
    draw.ellipse([bx-20, by-20, bx+20, by+20], fill=(240,240,240,230))
    draw.ellipse([bx-20, by-20, bx+20, by+20], outline=(50,50,50,200), width=3)

    pil = Image.alpha_composite(pil, overlay)
    return np.array(pil)[:, :, :3]


# ─── TikTok Visual FX ─────────────────────────────────────────────────────────

def color_grade_phonk(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Apply a purple/teal phonk color grade (shadows→purple, highlights→teal)."""
    f   = img.astype(np.float32) / 255.0
    lum = 0.2126 * f[:,:,0] + 0.7152 * f[:,:,1] + 0.0722 * f[:,:,2]
    lum = lum[:, :, None]

    # Lift shadows to purple
    shadow_mask = np.clip(1.0 - lum * 2, 0, 1)
    highlight_mask = np.clip(lum * 2 - 1, 0, 1)

    purple = np.array([0.35, 0.0, 0.65])
    teal   = np.array([0.0,  0.8, 0.9])

    f += shadow_mask    * purple * 0.25 * strength
    f += highlight_mask * teal   * 0.15 * strength

    # Crushed blacks (lift contrast)
    f = np.clip(f * 1.3 - 0.05, 0, 1)

    # Saturation boost
    lum3 = 0.2126 * f[:,:,0:1] + 0.7152 * f[:,:,1:2] + 0.0722 * f[:,:,2:3]
    f    = lum3 + (f - lum3) * (1.4 * strength)

    return np.clip(f * 255, 0, 255).astype(np.uint8)

def apply_vignette(img: np.ndarray, strength: float = 0.7) -> np.ndarray:
    ys = np.linspace(-1, 1, H)[:, None]
    xs = np.linspace(-1, 1, W)[None, :]
    vignette = 1.0 - strength * np.clip(ys**2 + xs**2, 0, 1)
    vignette = vignette[:, :, None]
    return np.clip(img.astype(float) * vignette, 0, 255).astype(np.uint8)

def apply_grain(img: np.ndarray, amount: float = 0.04) -> np.ndarray:
    noise = rng.standard_normal(img.shape).astype(np.float32) * amount * 255
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

def apply_glitch(img: np.ndarray, intensity: float = 1.0) -> np.ndarray:
    """RGB channel shift + horizontal tear."""
    out = img.copy()
    shift = int(rng.integers(5, 25) * intensity)
    out[:, :, 0] = np.roll(img[:, :, 0], shift,  axis=1)   # R shift right
    out[:, :, 2] = np.roll(img[:, :, 2], -shift, axis=1)   # B shift left

    # Horizontal tear
    n_tears = int(rng.integers(2, 5) * intensity)
    for _ in range(n_tears):
        y    = int(rng.integers(0, H))
        h_   = int(rng.integers(2, 12))
        off  = int(rng.integers(-30, 30) * intensity)
        band = img[y:y+h_, :, :]
        out[y:y+h_, :, :] = np.roll(band, off, axis=1)

    return out

def apply_zoom(img: np.ndarray, factor: float = 1.05) -> np.ndarray:
    """Zoom crop for transition effect."""
    if abs(factor - 1.0) < 0.001:
        return img
    new_h = int(H / factor)
    new_w = int(W / factor)
    y0 = (H - new_h) // 2
    x0 = (W - new_w) // 2
    cropped = img[y0:y0+new_h, x0:x0+new_w]
    pil = Image.fromarray(cropped).resize((W, H), Image.LANCZOS)
    return np.array(pil)

def apply_flash(img: np.ndarray, alpha: float) -> np.ndarray:
    white = np.full_like(img, 255)
    return np.clip(img.astype(float) * (1 - alpha) + white * alpha, 0, 255).astype(np.uint8)

def draw_text_tiktok(img: np.ndarray, line1: str, line2: str = "",
                     y_center: float = 0.82, alpha: float = 1.0) -> np.ndarray:
    """Bold TikTok-style text with stroke."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)

    def load(size):
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
            try: return ImageFont.truetype(p, size)
            except: pass
        return ImageFont.load_default()

    f1 = load(90)
    f2 = load(56)
    cy = int(H * y_center)
    a  = int(255 * alpha)

    for font, text, y, col in [
        (f1, line1, cy,        (255, 255, 255, a)),
        (f2, line2, cy + 105,  (255, 200, 30,  a)),
    ]:
        if not text: continue
        # Stroke
        for dx, dy in [(-4,0),(4,0),(0,-4),(0,4),(-4,-4),(4,4)]:
            draw.text((W//2 + dx, y + dy), text, font=font,
                      fill=(0,0,0,a), anchor="mm")
        draw.text((W//2, y), text, font=font, fill=col, anchor="mm")

    result = Image.alpha_composite(pil, ovl).convert("RGB")
    return np.array(result)

def draw_psg_watermark(img: np.ndarray, alpha: float = 0.7) -> np.ndarray:
    """Small PSG badge watermark top-left."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)
    a    = int(255 * alpha)
    cx, cy, r = 90, 90, 70
    draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                 fill=(0, 20, 80, a), outline=(255,200,30,a), width=4)
    draw.ellipse([cx-int(r*.7), cy-int(r*.7), cx+int(r*.7), cy+int(r*.7)],
                 fill=(220,20,40,a))
    draw.ellipse([cx-int(r*.4), cy-int(r*.4), cx+int(r*.4), cy+int(r*.4)],
                 fill=(255,255,255,a))
    def load(size):
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
            try: return ImageFont.truetype(p, size)
            except: pass
        return ImageFont.load_default()
    draw.text((cx, cy), "PSG", font=load(24), fill=(0,20,80,a), anchor="mm")
    return np.array(Image.alpha_composite(pil, ovl).convert("RGB"))

def draw_beat_bar(img: np.ndarray, progress: float) -> np.ndarray:
    """Thin phonk beat visualiser bar at bottom."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0,0,0,0))
    draw = ImageDraw.Draw(ovl)
    bw   = int(W * progress)
    draw.rectangle([0, H-12, bw, H], fill=(255,200,30,200))
    return np.array(Image.alpha_composite(pil, ovl).convert("RGB"))


# ─── Clip segments ────────────────────────────────────────────────────────────

SEGMENTS = [
    # (duration_beats, scene_id, line1, line2, glitch, zoom_out, zoom_in)
    (4,  0, "PARIS",          "SAINT-GERMAIN",        False, False, True ),
    (2,  1, "RONALDINHO",     "2001 · MAGIE PURE",    False, False, False),
    (2,  2, "IBRAHIMOVIĆ",    "38 BUTS EN L1",        True,  True,  False),
    (2,  3, "CAVANI",         "200 BUTS ALL TIME",    False, False, True ),
    (2,  4, "6–1 BARÇA",      "PARC DES PRINCES",     True,  False, True ),
    (2,  5, "NEYMAR JR",      "222M€ · LE ROI",       False, True,  False),
    (2,  6, "MBAPPÉ",         "PRODIGE DE BONDY",     True,  False, True ),
    (2,  7, "UCL 2020",       "LISBONNE · FINALE",    False, True,  False),
    (2,  0, "MESSI",          "AU PARC",              True,  False, True ),
    (2,  8, "HAKIMI",         "LE TALENT AFRICAIN",   False, False, False),
    (2,  1, "MARQUINHOS",     "CAPITAINE DU PSG",     True,  True,  False),
    (4,  9, "ICI C'EST PARIS","#ICICESTPARIS",         False, False, True ),
]

def make_segment_frames(seg_idx: int, dur_beats: int, scene_id: int,
                        line1: str, line2: str,
                        do_glitch: bool, zoom_out: bool, zoom_in: bool):
    dur   = dur_beats * BEAT
    total_frames = int(dur * FPS)
    frames = []

    for fi in range(total_frames):
        t   = fi / FPS
        p   = t / dur           # 0→1 within segment
        beat_p = (t % BEAT) / BEAT  # 0→1 within current beat

        # Beat flash on kick (every beat start)
        on_beat = beat_p < 0.12

        # --- Scene frame -------------------------------------------------------
        cam_shake = 0.5 if on_beat else 0.0
        scene_frame = make_action_scene(scene_id, p, cam_shake)

        # --- Zoom transitions --------------------------------------------------
        if zoom_in and p < 0.25:
            factor = 1.0 + 0.12 * (1.0 - p / 0.25)   # zoom in at start
            scene_frame = apply_zoom(scene_frame, factor)
        elif zoom_out and p > 0.75:
            factor = 1.0 + 0.12 * ((p - 0.75) / 0.25)  # zoom out at end
            scene_frame = apply_zoom(scene_frame, factor)

        # --- Color grade -------------------------------------------------------
        grade_strength = 1.0 + 0.4 * float(on_beat)
        scene_frame = color_grade_phonk(scene_frame, grade_strength)

        # --- Glitch on beat ────────────────────────────────────────────────────
        if do_glitch and on_beat and beat_p < 0.06:
            scene_frame = apply_glitch(scene_frame, intensity=1.5)

        # --- Vignette + grain --------------------------------------------------
        scene_frame = apply_vignette(scene_frame, strength=0.65)
        scene_frame = apply_grain(scene_frame, amount=0.025)

        # --- Beat flash --------------------------------------------------------
        if on_beat and beat_p < 0.04:
            scene_frame = apply_flash(scene_frame, alpha=0.35 * (1.0 - beat_p / 0.04))

        # --- Text overlays -----------------------------------------------------
        # Slide in from bottom
        text_alpha = min(1.0, p * 6)
        if p > 0.85:
            text_alpha = (1.0 - p) / 0.15  # fade out at end
        scene_frame = draw_text_tiktok(scene_frame, line1, line2, alpha=text_alpha)

        # --- Watermark ---------------------------------------------------------
        scene_frame = draw_psg_watermark(scene_frame, alpha=0.6)

        # --- Progress bar ------------------------------------------------------
        scene_frame = draw_beat_bar(scene_frame, p)

        frames.append(scene_frame)

    return frames, dur


# ─── Hard cut flash between segments ─────────────────────────────────────────

def make_flash_frames(color_arr, n_frames=4):
    frames = []
    for i in range(n_frames):
        alpha = 1.0 - (i / n_frames)
        f = color_arr.copy()
        f = np.clip(f.astype(float) * alpha + 255 * (1 - alpha), 0, 255).astype(np.uint8)
        frames.append(f)
    return frames


# ─── Main builder ─────────────────────────────────────────────────────────────

def build():
    print("🎬  Building PSG TikTok Edit…")

    all_frames   = []
    total_dur    = 0.0

    for seg_idx, (beats, scene_id, l1, l2, glitch, zoom_out, zoom_in) in enumerate(SEGMENTS):
        print(f"   [{seg_idx+1}/{len(SEGMENTS)}] {l1}…")
        frames, seg_dur = make_segment_frames(seg_idx, beats, scene_id,
                                              l1, l2, glitch, zoom_out, zoom_in)
        all_frames.extend(frames)
        total_dur += seg_dur

        # Hard cut flash (white) except after last
        if seg_idx < len(SEGMENTS) - 1:
            # Alternate white / red flash
            flash_col = np.full((H, W, 3), 255 if seg_idx % 2 == 0 else 200, dtype=np.uint8)
            if seg_idx % 2 == 1:
                flash_col[:, :, 1] = 20
                flash_col[:, :, 2] = 40
            flash_frames = make_flash_frames(flash_col, n_frames=3)
            all_frames.extend(flash_frames)
            total_dur += len(flash_frames) / FPS

    print(f"   Total: {total_dur:.1f}s  ({len(all_frames)} frames)")

    # Convert to float32 array for MoviePy
    frame_arr = np.array(all_frames, dtype=np.uint8)

    def make_frame(t):
        idx = min(int(t * FPS), len(frame_arr) - 1)
        return frame_arr[idx]

    video = VideoClip(make_frame, duration=total_dur).with_fps(FPS)

    # ── Phonk audio ────────────────────────────────────────────────────────────
    print("🎵  Synthesising phonk soundtrack…")
    audio_data, sr = generate_phonk(total_dur + 0.5)
    audio_clip = AudioArrayClip(audio_data, fps=sr)
    audio_clip = audio_clip.subclipped(0, total_dur)
    audio_clip = audio_clip.with_effects([mp.audio.fx.AudioFadeOut(1.0)])
    video = video.with_audio(audio_clip)

    # ── Render ─────────────────────────────────────────────────────────────────
    print(f"💾  Rendering → {OUT}")
    video.write_videofile(
        OUT,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        bitrate="6000k",
        logger="bar",
    )
    print(f"\n✅  {OUT}")

if __name__ == "__main__":
    build()
