"""
PSG STORM EDIT — TikTok 9:16 · Phonk · Speed-ramp · Color grade

USAGE
-----
1. Get a FREE Pexels API key at https://www.pexels.com/api/  (takes 30s)
2. pip install moviepy pillow numpy scipy requests tqdm
3. python psg_storm_edit.py --pexels-key YOUR_KEY
   OR put your own clips in ./clips/ and run:
   python psg_storm_edit.py --clips-dir ./clips/

OUTPUT : psg_storm_tiktok.mp4  (1080×1920 · 30fps · ~30s)
"""

import argparse, os, sys, math, random, shutil, subprocess, urllib.request, ssl
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance
import scipy.ndimage as ndimage
import scipy.signal as signal
from moviepy import VideoClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip
from moviepy.audio.AudioClip import AudioArrayClip
import moviepy as mp

# ─── Constants ────────────────────────────────────────────────────────────────
W, H   = 1080, 1920
FPS    = 30
BPM    = 140
BEAT   = 60.0 / BPM   # 0.4286 s
SR     = 44100
OUT    = "psg_storm_tiktok.mp4"

RNG = np.random.default_rng(42)

# ─── Color palette ────────────────────────────────────────────────────────────
PSG_BLUE = (0, 20, 90)
PSG_RED  = (220, 20, 40)
WHITE    = (255, 255, 255)
GOLD     = (255, 195, 20)
BLACK    = (0, 0, 0)


# ══════════════════════════════════════════════════════════════════════════════
#  PEXELS DOWNLOADER
# ══════════════════════════════════════════════════════════════════════════════

PEXELS_QUERIES = [
    "soccer goal scored",
    "football player dribbling",
    "soccer match stadium crowd",
    "football player running",
    "soccer celebration",
    "football kick ball",
    "soccer game night stadium",
]

def pexels_download(api_key: str, out_dir: Path, n_clips: int = 8):
    """Download n royalty-free football clips from Pexels."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = ssl._create_unverified_context()
    clips = []

    for query in PEXELS_QUERIES:
        if len(clips) >= n_clips:
            break
        url = f"https://api.pexels.com/videos/search?query={query.replace(' ','+')}&per_page=3&size=medium"
        req = urllib.request.Request(url, headers={"Authorization": api_key})
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=15)
            import json
            data = json.loads(resp.read())
            for vid in data.get("videos", []):
                if len(clips) >= n_clips:
                    break
                # Pick SD or HD file (prefer 1920 height or closest)
                files = vid.get("video_files", [])
                files.sort(key=lambda f: abs(f.get("height", 0) - 1080))
                best = files[0] if files else None
                if not best:
                    continue
                vid_url  = best["link"]
                fname    = out_dir / f"clip_{len(clips):02d}.mp4"
                print(f"  Downloading: {vid_url[:70]}…")
                req2 = urllib.request.Request(vid_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, context=ctx, timeout=60) as r, \
                     open(fname, "wb") as f:
                    shutil.copyfileobj(r, f)
                clips.append(str(fname))
                print(f"    Saved → {fname.name} ({fname.stat().st_size//1024} KB)")
        except Exception as e:
            print(f"  Pexels error ({query}): {e}")

    print(f"Downloaded {len(clips)} clips.")
    return clips


# ══════════════════════════════════════════════════════════════════════════════
#  PHONK GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def gen_phonk(duration: float) -> tuple[np.ndarray, int]:
    n = int(duration * SR)
    t = np.linspace(0, duration, n, endpoint=False)
    out = np.zeros(n, dtype=np.float64)

    def adsr(length, a=0.003, d=0.04, s=0.65, r=0.06):
        e = np.ones(length) * s
        ai = min(int(a * SR), length)
        di = min(int(d * SR), length - ai)
        ri = min(int(r * SR), length - ai - di)
        e[:ai] = np.linspace(0, 1, max(1, ai))
        e[ai:ai+di] = np.linspace(1, s, max(1, di))
        e[max(0, length - ri):] = np.linspace(s, 0, max(1, ri))
        return e

    # ── 808 kick with pitch sweep ──────────────────────────────────────────────
    for i in range(int(duration / BEAT) + 2):
        ts  = i * BEAT
        idx = int(ts * SR)
        if idx >= n: break
        dur = min(int(0.55 * SR), n - idx)
        freq = 55 * np.exp(-22 * np.linspace(0, 1, dur))
        osc  = np.sin(2 * np.pi * np.cumsum(freq) / SR)
        env  = np.exp(-5 * np.linspace(0, 1, dur))
        out[idx:idx+dur] += np.tanh(osc * 4) * env * 0.8

    # ── Kick transient noise ───────────────────────────────────────────────────
    for i in range(int(duration / BEAT) + 2):
        idx = int(i * BEAT * SR)
        if idx >= n: break
        l = min(int(0.04 * SR), n - idx)
        out[idx:idx+l] += RNG.standard_normal(l) * np.exp(-80 * np.linspace(0,1,l)) * 0.28

    # ── Snare on beats 2 & 4 ──────────────────────────────────────────────────
    for i in range(int(duration / (BEAT * 4)) + 2):
        for offset in [BEAT, BEAT * 3]:
            ts  = i * BEAT * 4 + offset
            idx = int(ts * SR)
            if idx >= n: break
            l = min(int(0.2 * SR), n - idx)
            snr = RNG.standard_normal(l) * np.exp(-18 * np.linspace(0,1,l))
            tone = np.sin(2*np.pi*200*np.linspace(0,0.2,l)) * np.exp(-28*np.linspace(0,1,l))
            out[idx:idx+l] += (snr * 0.38 + tone * 0.25) * 0.55

    # ── Cowbell hi-hat (TR-808 style) ─────────────────────────────────────────
    cb_freqs = [562, 845]
    for i in range(int(duration / (BEAT / 2)) + 2):
        ts  = i * BEAT / 2
        amp = 0.32 if i % 2 == 0 else 0.18
        idx = int(ts * SR)
        if idx >= n: break
        l = min(int(0.10 * SR), n - idx)
        env = np.exp(-35 * np.linspace(0, 1, l))
        sig = sum(np.sin(2*np.pi*f*np.linspace(0,0.1,l)) for f in cb_freqs)
        out[idx:idx+l] += sig * env * amp * 0.28

    # ── Closed HH 16th notes ──────────────────────────────────────────────────
    for i in range(int(duration / (BEAT / 4)) + 2):
        idx = int(i * BEAT / 4 * SR)
        if idx >= n: break
        l = min(int(0.012 * SR), n - idx)
        out[idx:idx+l] += RNG.standard_normal(l) * np.exp(-250*np.linspace(0,1,l)) * 0.1

    # ── Memphis trap chords ────────────────────────────────────────────────────
    # Bm - Am - Fm - Gm looping  (transposed down an octave for dark feel)
    chord_patterns = [
        [46, 50, 53],   # Bbm
        [44, 47, 51],   # Abm
        [41, 44, 48],   # Fm
        [43, 46, 50],   # Gm
    ]
    chord_dur = BEAT * 8
    total_chords = int(duration / chord_dur) + 2
    for ci in range(total_chords):
        chord = chord_patterns[ci % len(chord_patterns)]
        ts = ci * chord_dur
        if ts >= duration: break
        for note in chord:
            fhz  = 440 * 2**((note-69)/12)
            l    = min(int(chord_dur * SR), n - int(ts*SR))
            if l <= 0: break
            e    = adsr(l)
            ph   = np.linspace(0, chord_dur, l)
            saw  = (signal.sawtooth(2*np.pi*fhz*ph) +
                    signal.sawtooth(2*np.pi*fhz*1.007*ph)) / 2
            b, a = signal.butter(2, 900/(SR/2), btype='low')
            saw  = signal.lfilter(b, a, saw)
            idx  = int(ts*SR)
            out[idx:idx+l] += saw * e * 0.16

    # ── Sub bass ──────────────────────────────────────────────────────────────
    bass_seq = [34, 34, 36, 38, 34, 34, 31, 33]
    for i, note in enumerate(bass_seq * (int(duration/(BEAT*len(bass_seq)))+2)):
        ts = i * BEAT
        if ts >= duration: break
        fhz = 440 * 2**((note-69)/12)
        l   = min(int(BEAT*0.88*SR), n - int(ts*SR))
        if l <= 0: break
        e   = adsr(l, a=0.002, d=0.05, s=0.7, r=0.04)
        ph  = np.linspace(0, BEAT*0.88, l)
        sub = np.tanh(np.sin(2*np.pi*fhz*ph) * 5) * 0.5
        idx = int(ts*SR)
        out[idx:idx+l] += sub * e * 0.45

    # ── Sidechain pump ────────────────────────────────────────────────────────
    sc = np.ones(n)
    for i in range(int(duration/BEAT)+2):
        idx = int(i*BEAT*SR)
        if idx >= n: break
        l = min(int(0.18*SR), n-idx)
        sc[idx:idx+l] = np.minimum(sc[idx:idx+l],
                                    1 - 0.65*np.exp(-28*np.linspace(0,1,l)))
    out *= sc

    # Volume swell
    out *= np.clip(np.linspace(0.4, 1.0, n)**0.6, 0, 1)

    # Limiter
    out = np.tanh(out * 1.35) * 0.9

    # Fade in/out
    fi = min(int(0.15*SR), n)
    out[:fi]  *= np.linspace(0, 1, fi)
    out[-fi:] *= np.linspace(1, 0, fi)

    return np.stack([out, out], -1).astype(np.float32), SR


# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO EFFECTS  (Storm style)
# ══════════════════════════════════════════════════════════════════════════════

def to_9x16_frame(frame: np.ndarray) -> np.ndarray:
    """Crop/pad any frame to 1080×1920."""
    h, w = frame.shape[:2]
    target_ratio = W / H   # 9/16
    src_ratio    = w / h

    if src_ratio > target_ratio:
        # Wider: crop sides
        new_w = int(h * target_ratio)
        x0    = (w - new_w) // 2
        frame = frame[:, x0:x0+new_w]
    else:
        # Taller: crop top/bottom
        new_h = int(w / target_ratio)
        y0    = (h - new_h) // 2
        frame = frame[y0:y0+new_h, :]

    pil = Image.fromarray(frame).resize((W, H), Image.LANCZOS)
    return np.array(pil)


def storm_color_grade(img: np.ndarray) -> np.ndarray:
    """
    'Storm' cinematic color grade:
    - Slight desaturation
    - Crushed blacks
    - Lifted shadows → teal
    - Highlights → warm gold
    - High contrast
    """
    f = img.astype(np.float32) / 255.0

    # Luma
    lum = 0.2126*f[:,:,0] + 0.7152*f[:,:,1] + 0.0722*f[:,:,2]
    lum3 = lum[:,:,None]

    # Slight desaturation (0.85 sat)
    f = lum3 * 0.15 + f * 0.85

    # Crushed blacks
    f = np.power(np.clip(f, 0, 1), 1.15)

    # Shadow teal tint
    shadow = np.clip(1.0 - lum3 * 2.5, 0, 1)
    teal   = np.array([0.0, 0.25, 0.35], dtype=np.float32)
    f      = f + shadow * teal * 0.18

    # Highlight gold tint
    high   = np.clip(lum3 * 2.0 - 1.0, 0, 1)
    gold   = np.array([0.15, 0.08, -0.05], dtype=np.float32)
    f      = f + high * gold * 0.25

    # Contrast S-curve
    f = np.clip(f, 0, 1)
    f = 0.5 + (f - 0.5) * 1.18

    return np.clip(f * 255, 0, 255).astype(np.uint8)


def vignette(img: np.ndarray, strength: float = 0.55) -> np.ndarray:
    ys = np.linspace(-1, 1, H)[:, None]
    xs = np.linspace(-1, 1, W)[None, :]
    v  = 1.0 - strength * (ys**2 + xs**2) ** 0.7
    return np.clip(img.astype(float) * v[:, :, None], 0, 255).astype(np.uint8)


def grain(img: np.ndarray, amount: float = 0.018) -> np.ndarray:
    n = RNG.standard_normal(img.shape).astype(np.float32) * amount * 255
    return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)


def glitch_rgb(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    s = int(RNG.integers(4, 18) * strength)
    out = img.copy()
    out[:,:,0] = np.roll(img[:,:,0],  s, axis=1)
    out[:,:,2] = np.roll(img[:,:,2], -s, axis=1)
    for _ in range(int(3 * strength)):
        y  = int(RNG.integers(0, H))
        lh = int(RNG.integers(3, 14))
        dx = int(RNG.integers(-25, 25) * strength)
        out[y:y+lh,:,:] = np.roll(img[y:y+lh,:,:], dx, axis=1)
    return out


def motion_blur_h(img: np.ndarray, length: int = 30, angle: float = 0.0) -> np.ndarray:
    """Horizontal motion blur (whip pan effect)."""
    kernel    = np.zeros((1, length), dtype=np.float32)
    kernel[0] = 1.0 / length
    blurred   = ndimage.convolve(img.astype(np.float32),
                                  kernel[:, :, None], mode='reflect')
    return blurred.astype(np.uint8)


def zoom_frame(img: np.ndarray, factor: float) -> np.ndarray:
    if abs(factor - 1.0) < 0.001:
        return img
    nh = max(1, int(H / factor))
    nw = max(1, int(W / factor))
    y0 = (H - nh) // 2
    x0 = (W - nw) // 2
    crop = img[y0:y0+nh, x0:x0+nw]
    return np.array(Image.fromarray(crop).resize((W, H), Image.LANCZOS))


def flash(img: np.ndarray, alpha: float) -> np.ndarray:
    white = np.full_like(img, 255)
    return np.clip(img*(1-alpha) + white*alpha, 0, 255).astype(np.uint8)


def speed_ramp(frames: list[np.ndarray],
               original_fps: float = 30.0,
               output_fps: float = 30.0,
               slow_factor: float = 0.25,
               slow_start: float = 0.4,
               slow_end: float = 0.65) -> list[np.ndarray]:
    """
    Speed ramp: full speed → slow (slow_factor) → snap back.
    Returns the new frame list at output_fps.
    """
    n = len(frames)
    out = []
    t   = 0.0
    dur = n / original_fps
    while t < dur:
        norm = t / dur
        # Compute playback speed at this moment
        if slow_start <= norm <= slow_end:
            speed = slow_factor
        elif norm < slow_start:
            # Linear ramp down
            alpha = (norm) / slow_start if slow_start > 0 else 1.0
            speed = 1.0 - (1.0 - slow_factor) * alpha
        else:
            # Snap back to 1.0
            speed = 1.0

        frame_idx = min(int(t * original_fps), n - 1)
        out.append(frames[frame_idx])
        t += speed / output_fps

    return out


def letterbox(img: np.ndarray, bar_h: int = 90) -> np.ndarray:
    """Add cinematic letterbox bars."""
    out = img.copy()
    out[:bar_h, :, :] = 0
    out[H-bar_h:, :, :] = 0
    return out


# ─── Text overlay ─────────────────────────────────────────────────────────────

def load_font(size: int):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_text_storm(img: np.ndarray, text: str, sub: str = "",
                    y_frac: float = 0.78, alpha: float = 1.0,
                    size: int = 110) -> np.ndarray:
    """Bold uppercase Storm-style text with thick stroke."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)
    a    = int(255 * alpha)
    cy   = int(H * y_frac)

    f1   = load_font(size)
    f2   = load_font(size // 2)

    for font, t, y, fill in [(f1, text, cy, (255,255,255,a)),
                              (f2, sub,  cy + size + 10, (255,195,20,a))]:
        if not t: continue
        # Thick black stroke
        for dx, dy in [(-5,0),(5,0),(0,-5),(0,5),(-5,-5),(5,5),(-5,5),(5,-5)]:
            draw.text((W//2+dx, y+dy), t, font=font, fill=(0,0,0,a), anchor="mm")
        draw.text((W//2, y), t, font=font, fill=fill, anchor="mm")

    return np.array(Image.alpha_composite(pil, ovl).convert("RGB"))


def draw_psg_badge(img: np.ndarray, alpha: float = 0.85) -> np.ndarray:
    """PSG badge watermark top-left."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)
    a    = int(255 * alpha)
    cx, cy, r = 100, 115, 80
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*PSG_BLUE, a), outline=(*GOLD, a), width=5)
    draw.ellipse([cx-int(r*.65), cy-int(r*.65), cx+int(r*.65), cy+int(r*.65)],
                 fill=(*PSG_RED, a))
    draw.ellipse([cx-int(r*.38), cy-int(r*.38), cx+int(r*.38), cy+int(r*.38)],
                 fill=(*WHITE, a))
    draw.text((cx, cy), "PSG", font=load_font(28), fill=(*PSG_BLUE, a), anchor="mm")
    return np.array(Image.alpha_composite(pil, ovl).convert("RGB"))


def draw_beat_flash_bar(img: np.ndarray, progress: float) -> np.ndarray:
    pil  = Image.fromarray(img).convert("RGBA")
    draw = ImageDraw.Draw(pil)
    bw   = int(W * progress)
    draw.rectangle([0, H-8, bw, H], fill=(*GOLD, 200))
    return np.array(pil.convert("RGB"))


def draw_bottom_label(img: np.ndarray, text: str, alpha: float = 1.0) -> np.ndarray:
    """PSG-red label strip at the bottom."""
    pil  = Image.fromarray(img).convert("RGBA")
    ovl  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)
    a    = int(255 * alpha)
    bar_h = 90
    draw.rectangle([0, H-bar_h-8, W, H-8], fill=(*PSG_RED, a))
    draw.text((W//2, H-bar_h//2-8), text, font=load_font(44),
              fill=(*WHITE, a), anchor="mm")
    return np.array(Image.alpha_composite(pil, ovl).convert("RGB"))


# ══════════════════════════════════════════════════════════════════════════════
#  CLIP PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def load_clip_frames(path: str, target_dur: float = 2.5,
                     target_fps: float = 30.0) -> list[np.ndarray]:
    """Load a video clip, extract target_dur seconds, return frame list."""
    cap = VideoFileClip(path)
    fps = cap.fps or 25.0
    total = cap.duration

    # Pick a random start point (avoid first / last 5% of clip)
    margin = total * 0.05
    max_start = max(0.0, total - target_dur - margin)
    start = random.uniform(margin, max_start) if max_start > 0 else 0.0
    end   = min(start + target_dur, total)

    sub  = cap.subclipped(start, end)
    # Resample to target_fps
    frames = []
    t = 0.0
    while t < (end - start):
        f = sub.get_frame(t)
        frames.append(to_9x16_frame(f.astype(np.uint8)))
        t += 1.0 / target_fps

    cap.close()
    return frames


SEGMENT_LABELS = [
    ("PARIS",         "SAINT-GERMAIN",     False, True,  False),  # intro
    ("IBRAHIMOVIĆ",   "THE KING OF PARIS", True,  False, True ),
    ("NEYMAR JR",     "MAGIE PURE",        False, True,  True ),
    ("MBAPPÉ",        "BONDY LE GÉNIE",    True,  False, False),
    ("6-1 BARÇA",     "PARC DES PRINCES",  True,  True,  True ),
    ("CAVANI",        "200 BUTS",          False, False, True ),
    ("UCL 2020",      "LISBONNE · FINALE", True,  False, False),
    ("ICI C'EST PARIS","#PSG",             False, True,  True ),
]


def build_segment(clip_frames: list[np.ndarray],
                  label: tuple,
                  seg_idx: int,
                  total_segs: int) -> list[np.ndarray]:
    """
    Process one clip segment:
    - Speed ramp
    - Storm color grade
    - Zoom transitions
    - Glitch on beat
    - Text overlay
    - Vignette + grain
    """
    line1, line2, do_glitch, do_zoom_in, do_zoom_out = label
    total_dur = len(clip_frames) / FPS
    out = []

    # Apply speed ramp
    ramped = speed_ramp(clip_frames, FPS, FPS,
                        slow_factor=0.2,
                        slow_start=0.35,
                        slow_end=0.60)

    for fi, frame in enumerate(ramped):
        t        = fi / FPS
        progress = t / max(total_dur, 0.001)
        beat_p   = (t % BEAT) / BEAT
        on_beat  = beat_p < 0.10

        # ── Color grade ────────────────────────────────────────────────────────
        f = storm_color_grade(frame)

        # ── Zoom transitions ───────────────────────────────────────────────────
        if do_zoom_in and progress < 0.30:
            factor = 1.0 + 0.18 * (1.0 - progress / 0.30)
            f = zoom_frame(f, factor)
        if do_zoom_out and progress > 0.70:
            factor = 1.0 + 0.18 * ((progress - 0.70) / 0.30)
            f = zoom_frame(f, factor)

        # ── Glitch on beat ─────────────────────────────────────────────────────
        if do_glitch and on_beat and beat_p < 0.05:
            f = glitch_rgb(f, strength=1.2 + 0.5 * int(on_beat))

        # ── Vignette + grain ───────────────────────────────────────────────────
        f = vignette(f, 0.55)
        f = grain(f, 0.022)

        # ── Letterbox ──────────────────────────────────────────────────────────
        f = letterbox(f, bar_h=80)

        # ── Beat flash ─────────────────────────────────────────────────────────
        if on_beat and beat_p < 0.035:
            f = flash(f, 0.30 * (1.0 - beat_p / 0.035))

        # ── Text ───────────────────────────────────────────────────────────────
        text_alpha = min(1.0, progress * 5.0)
        if progress > 0.80:
            text_alpha *= (1.0 - progress) / 0.20
        f = draw_text_storm(f, line1, line2, y_frac=0.78, alpha=text_alpha)

        # ── Badge & bar ────────────────────────────────────────────────────────
        f = draw_psg_badge(f, 0.75)
        f = draw_beat_flash_bar(f, progress)

        out.append(f)

    return out


# ─── Transition between segments ──────────────────────────────────────────────

def make_transition(from_frame: np.ndarray,
                    to_frame: np.ndarray,
                    kind: str = "whip") -> list[np.ndarray]:
    """Generate 3-6 frame transition."""
    frames = []
    if kind == "whip":
        # Horizontal motion blur sweep
        n = 5
        for i in range(n):
            p     = i / (n - 1)
            blur  = int(20 + p * 60)
            mixed = from_frame if p < 0.5 else to_frame
            blurred = motion_blur_h(mixed, length=blur)
            frames.append(blurred)
    elif kind == "flash":
        n = 4
        for i in range(n):
            p = i / (n - 1)
            src = from_frame if p < 0.5 else to_frame
            frames.append(flash(src, 1.0 - abs(p - 0.5) * 2))
    elif kind == "cut":
        # Hard cut: just 1 frame of white/red flash
        frames.append(np.full((H, W, 3), 255, dtype=np.uint8))
    return frames


# ── Intro / Outro ─────────────────────────────────────────────────────────────

def make_intro_frames(n: int = 60) -> list[np.ndarray]:
    """Black → PSG badge explode intro."""
    frames = []
    for fi in range(n):
        p   = fi / n
        img = np.zeros((H, W, 3), dtype=np.uint8)
        # Gradient background
        for y in range(H):
            r = y / H
            img[y, :] = (int(p * 0*(1-r)), int(p * 10*r), int(p * 40*r))

        pil  = Image.fromarray(img)
        draw = ImageDraw.Draw(pil)

        # Pulsing rings
        for ring in range(3):
            ring_r = int((0.1 + ring * 0.15 + p * 0.4) * W * 0.5)
            a      = max(0, int(255 * (1.0 - p - ring * 0.2)))
            if a <= 0: continue
            c = PSG_RED if ring % 2 == 0 else PSG_BLUE
            draw.ellipse([W//2-ring_r, H//2-ring_r, W//2+ring_r, H//2+ring_r],
                         outline=(*c, a), width=4)

        img = np.array(pil)
        img = draw_psg_badge(img, alpha=p)
        img = draw_text_storm(img, "PARIS", "SAINT-GERMAIN",
                              y_frac=0.62, alpha=p * 1.2, size=130)
        img = grain(img, 0.02)
        frames.append(img)
    return frames


def make_outro_frames(last_frame: np.ndarray, n: int = 45) -> list[np.ndarray]:
    """Slow zoom + fade to black."""
    frames = []
    for fi in range(n):
        p   = fi / n
        f   = zoom_frame(last_frame, 1.0 + p * 0.12)
        f   = np.clip(f.astype(float) * (1.0 - p), 0, 255).astype(np.uint8)
        f   = draw_text_storm(f, "ICI C'EST PARIS", "#PSG",
                              y_frac=0.5, alpha=1.0 - p * 1.5, size=115)
        frames.append(f)
    return frames


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def build(clip_paths: list[str]):
    print(f"\n🎬  PSG Storm Edit — {len(clip_paths)} clips")

    # ── Intro ──────────────────────────────────────────────────────────────────
    all_frames = make_intro_frames(60)
    prev_last   = all_frames[-1]

    trans_types = ["whip", "flash", "cut", "whip", "flash", "whip", "cut"]

    for seg_idx, (clip_path, label) in enumerate(
            zip(clip_paths, SEGMENT_LABELS[1:len(clip_paths)+1])):
        print(f"   [{seg_idx+1}/{len(clip_paths)}] {label[0]} — {Path(clip_path).name}")

        # Load clip (2-3 beats = ~0.9-1.3 s of content → extend with speed ramp)
        n_beats    = 4 if seg_idx == 0 else 2
        target_dur = n_beats * BEAT * 3    # will be sped/slowed
        clip_frames = load_clip_frames(clip_path, target_dur=target_dur)

        # Transition
        trans = make_transition(prev_last, clip_frames[0],
                                kind=trans_types[seg_idx % len(trans_types)])
        all_frames.extend(trans)

        # Build segment
        seg_frames = build_segment(clip_frames, label, seg_idx, len(clip_paths))
        all_frames.extend(seg_frames)
        prev_last = seg_frames[-1]

    # ── Outro ──────────────────────────────────────────────────────────────────
    all_frames.extend(make_outro_frames(prev_last, 45))

    total_dur = len(all_frames) / FPS
    print(f"\n   Total: {total_dur:.1f}s · {len(all_frames)} frames")

    # ── Build MoviePy VideoClip ────────────────────────────────────────────────
    frame_arr = np.array(all_frames, dtype=np.uint8)

    def get_frame(t):
        idx = min(int(t * FPS), len(frame_arr) - 1)
        return frame_arr[idx]

    video = VideoClip(get_frame, duration=total_dur).with_fps(FPS)

    # ── Phonk audio ────────────────────────────────────────────────────────────
    print("🎵  Generating phonk soundtrack…")
    audio_data, sr = gen_phonk(total_dur + 0.5)
    audio_clip     = AudioArrayClip(audio_data, fps=sr).subclipped(0, total_dur)
    audio_clip     = audio_clip.with_effects([mp.audio.fx.AudioFadeOut(1.0)])
    video          = video.with_audio(audio_clip)

    # ── Render ─────────────────────────────────────────────────────────────────
    print(f"💾  Rendering → {OUT}")
    video.write_videofile(
        OUT,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        bitrate="8000k",
        logger="bar",
    )
    print(f"\n✅  Done → {OUT}")


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="PSG Storm TikTok Edit")
    parser.add_argument("--pexels-key",  type=str, default=None,
                        help="Pexels API key (get free at pexels.com/api)")
    parser.add_argument("--clips-dir",   type=str, default="./clips",
                        help="Directory containing your own .mp4 clips")
    parser.add_argument("--n-clips",     type=int, default=8,
                        help="Number of clips to use (default 8)")
    args = parser.parse_args()

    clips_dir = Path(args.clips_dir)

    # ── Source: Pexels or local dir ────────────────────────────────────────────
    clip_paths = []

    if args.pexels_key:
        print("📥  Downloading clips from Pexels…")
        dl_dir     = Path("clips_pexels")
        clip_paths = pexels_download(args.pexels_key, dl_dir, args.n_clips)

    if not clip_paths and clips_dir.exists():
        clip_paths = sorted([str(p) for p in clips_dir.glob("*.mp4")])[:args.n_clips]
        if clip_paths:
            print(f"📂  Using {len(clip_paths)} local clips from {clips_dir}/")

    if not clip_paths:
        print("""
❌  No clips found. Options:
    1) Get a FREE Pexels API key (30s): https://www.pexels.com/api/
       Then run: python psg_storm_edit.py --pexels-key YOUR_KEY

    2) Drop your own .mp4 clips into ./clips/ then run:
       python psg_storm_edit.py --clips-dir ./clips/
""")
        sys.exit(1)

    build(clip_paths[:args.n_clips])


if __name__ == "__main__":
    main()
