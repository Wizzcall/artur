"""
SHORT DYNAMIC EDIT — rend un short 9:16 plus dynamique.

- Légère accélération (x1.10, voix sans changement de hauteur)
- Étalonnage (contraste / saturation / vignette) + zoom lent continu
- Effet différent à chaque coupure (punch-zoom + flash, glitch RGB + shake,
  whip-blur, zoom-out rebond) + whoosh / boom sonores
- 3 dernières secondes : écran de fin « MA DERNIÈRE VIDÉO » + « ABONNE-TOI »
  (bouton qui se fait cliquer -> « ABONNÉ ✓ » + cloche)

USAGE
  pip install numpy pillow
  python short_dynamic_edit.py INPUT.mov [--thumb miniature.jpg] [--out out.mp4]
  --thumb : miniature (image) de ta dernière vidéo. Sans ça, une image du clip
            sert de remplaçant.
"""

import argparse, subprocess, tempfile, wave, math, os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H, FPS, SR = 1080, 1920, 30, 44100
SPEED = 1.10
END_DUR = 3.0
FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
RED = (230, 20, 35)
RNG = np.random.default_rng(7)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# ─── analysis ──────────────────────────────────────────────────────────────
def probe_duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


def detect_cuts(path, thr=0.11, min_t=1.0):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path,
                        "-vf", f"scale=270:-2,select='gt(scene,{thr})',metadata=print:file=-",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    cuts = []
    for line in p.stdout.splitlines():
        if "pts_time:" in line:
            t = float(line.split("pts_time:")[1].split()[0])
            if t >= min_t and (not cuts or t - cuts[-1] > 0.8):
                cuts.append(t)
    return cuts


# ─── easing ────────────────────────────────────────────────────────────────
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.9):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


# ─── frame effects ─────────────────────────────────────────────────────────
def zoom(img, z, cx=0.5, cy=0.5, dx=0, dy=0):
    if abs(z - 1) < 1e-3 and dx == 0 and dy == 0:
        return img
    cw, ch = W / z, H / z
    x0 = clamp(cx * W - cw / 2 + dx, 0, W - cw) if z >= 1 else cx * W - cw / 2 + dx
    y0 = clamp(cy * H - ch / 2 + dy, 0, H - ch) if z >= 1 else cy * H - ch / 2 + dy
    return img.transform((W, H), Image.Transform.EXTENT,
                         (x0, y0, x0 + cw, y0 + ch), Image.Resampling.BILINEAR)


def rgb_split(arr, off):
    out = arr.copy()
    out[..., 0] = np.roll(arr[..., 0], off, axis=1)
    out[..., 2] = np.roll(arr[..., 2], -off, axis=1)
    return out


def glitch_slices(arr, strength):
    out = arr.copy()
    for _ in range(int(6 * strength) + 1):
        y = RNG.integers(0, H - 60)
        h = RNG.integers(15, 120)
        out[y:y + h] = np.roll(out[y:y + h], RNG.integers(-80, 80), axis=1)
    return out


def whip_blur(arr, amount):
    n = 7
    acc = np.zeros_like(arr, dtype=np.float32)
    for i in range(n):
        acc += np.roll(arr, int((i - n // 2) * amount), axis=0)
    return (acc / n).astype(np.uint8)


def make_vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return np.clip(1.0 - 0.35 * np.clip(d - 0.55, 0, None) ** 1.5, 0.55, 1.0)[..., None]


VIGNETTE = None


def grade(img):
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.30)
    img = ImageEnhance.Brightness(img).enhance(1.04)
    return img


# ─── transitions at cuts ───────────────────────────────────────────────────
TRANS_LEN = 0.35


def apply_cut_fx(img, kind, u):
    """u: 0 at the cut -> 1 at end of the transition."""
    k = 1 - ease_out_cubic(u)
    if kind == 0:          # punch zoom + white flash
        img = zoom(img, 1 + 0.22 * k)
        arr = np.asarray(img).astype(np.float32)
        arr = arr + (255 - arr) * (0.85 * max(0, 1 - u * 3))
        return Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    if kind == 1:          # glitch RGB + shake
        dx, dy = RNG.integers(-30, 30) * k, RNG.integers(-30, 30) * k
        img = zoom(img, 1.08 + 0.06 * k, dx=dx, dy=dy)
        arr = np.asarray(img)
        if u < 0.7:
            arr = rgb_split(arr, int(28 * k) + 2)
            arr = glitch_slices(arr, k)
        return Image.fromarray(arr)
    if kind == 2:          # whip blur vertical + zoom
        img = zoom(img, 1 + 0.15 * k, dy=-220 * k)
        arr = np.asarray(img)
        if k > 0.05:
            arr = whip_blur(arr, 40 * k)
        return Image.fromarray(arr)
    # kind 3: zoom-out bounce + soft flash
    z = 0.86 + 0.14 * ease_out_back(u)
    bg = img.filter(ImageFilter.GaussianBlur(25)) if z < 1 else None
    fg = zoom(img, z)
    if bg is not None:
        small = img.resize((int(W * z), int(H * z)), Image.Resampling.BILINEAR)
        bg = zoom(bg, 1.2)
        bg.paste(small, ((W - small.width) // 2, (H - small.height) // 2))
        fg = bg
    arr = np.asarray(fg).astype(np.float32)
    arr = arr + (255 - arr) * (0.5 * max(0, 1 - u * 4))
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


# ─── end card ──────────────────────────────────────────────────────────────
def rounded_mask(size, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def build_thumb_card(thumb, regrade=True):
    t = thumb.convert("RGB")
    landscape = t.width > t.height * 1.2
    cw, ch = (960, 540) if landscape else (560, 760)
    s = max(cw / t.width, ch / t.height)
    t = t.resize((int(t.width * s) + 1, int(t.height * s) + 1), Image.Resampling.LANCZOS)
    t = t.crop(((t.width - cw) // 2, (t.height - ch) // 2,
                (t.width - cw) // 2 + cw, (t.height - ch) // 2 + ch))
    if regrade:
        t = grade(t)
    b = 10
    card = Image.new("RGBA", (cw + 2 * b, ch + 2 * b), (0, 0, 0, 0))
    card.paste(Image.new("RGBA", card.size, (255, 255, 255, 255)), (0, 0),
               rounded_mask(card.size, 42))
    card.paste(t, (b, b), rounded_mask((cw, ch), 34))
    d = ImageDraw.Draw(card)
    # play button (centre en portrait, coin bas-gauche en paysage pour ne rien masquer)
    if landscape:
        cx, cy, r = 92, card.height - 92, 52
    else:
        cx, cy, r = card.width // 2, card.height // 2, 70
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0, 150), outline=(255, 255, 255, 230), width=6)
    k = r / 70
    d.polygon([(cx - 22 * k, cy - 36 * k), (cx - 22 * k, cy + 36 * k), (cx + 38 * k, cy)], fill=(255, 255, 255, 255))
    # "NOUVEAU" badge
    f = font(FONT_BLACK, 34)
    d.rounded_rectangle((28, 28, 232, 84), 14, fill=RED + (255,))
    d.text((130, 56), "NOUVEAU", font=f, fill="white", anchor="mm")
    return card, landscape


def shadowed(layer, blur=22, off=(0, 14), alpha=150):
    pad = blur * 3
    sh = Image.new("RGBA", (layer.width + 2 * pad, layer.height + 2 * pad), (0, 0, 0, 0))
    a = layer.split()[3].point(lambda v: v * alpha // 255)
    blk = Image.new("RGBA", layer.size, (0, 0, 0, 255))
    blk.putalpha(a)
    sh.paste(blk, (pad + off[0], pad + off[1]), blk)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(layer, (pad, pad))
    return sh, pad


def draw_bell(d, cx, cy, s, angle, color):
    pts = [(-0.75 * s, 0.45 * s), (-0.55 * s, -0.15 * s)] + \
          [(-0.55 * s * math.cos(a), -0.15 * s - 0.55 * s * math.sin(a)) for a in np.linspace(0, math.pi, 20)] + \
          [(0.55 * s, -0.15 * s), (0.75 * s, 0.45 * s)]
    ca, sa = math.cos(angle), math.sin(angle)
    rot = lambda p: (cx + p[0] * ca - (p[1] + 0.6 * s) * sa, cy + p[0] * sa + (p[1] + 0.6 * s) * ca - 0.6 * s)
    d.polygon([rot(p) for p in pts], fill=color)
    bx, by = rot((0, 0.62 * s))
    d.ellipse((bx - 0.18 * s, by - 0.18 * s, bx + 0.18 * s, by + 0.18 * s), fill=color)


def draw_cursor(d, x, y, sc, pressed):
    s = 1.6 * sc * (0.85 if pressed else 1.0)
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    poly = [(x + px * s, y + py * s) for px, py in pts]
    d.polygon(poly, fill="white", outline="black", width=4)


class EndCard:
    def __init__(self, thumb, custom=False):
        card, self.landscape = build_thumb_card(thumb, regrade=not custom)
        self.card, self.cpad = shadowed(card)
        self.f_title = font(FONT_BLACK, 74)
        self.f_btn = font(FONT_BLACK, 66)

    def render(self, bg, t):
        """t: seconds since start of end card (0..END_DUR)."""
        k_bg = ease_out_cubic(t / 0.35)
        if k_bg > 0:
            blurred = bg.filter(ImageFilter.GaussianBlur(4 + 22 * k_bg))
            blurred = ImageEnhance.Brightness(blurred).enhance(1 - 0.5 * k_bg)
            bg = Image.blend(bg, blurred, min(1.0, k_bg * 1.5))
        canvas = bg.convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # ── title
        a = clamp((t - 0.05) / 0.25)
        if a > 0:
            y = 250 - 60 * (1 - ease_out_cubic(a))
            txt = "MA DERNIÈRE VIDÉO"
            d.text((W // 2 + 5, y + 6), txt, font=self.f_title, fill=(0, 0, 0, int(160 * a)), anchor="mm")
            d.text((W // 2, y), txt, font=self.f_title, fill=(255, 255, 255, int(255 * a)), anchor="mm",
                   stroke_width=3, stroke_fill=(0, 0, 0, int(200 * a)))
            # underline bar
            bw = int(560 * ease_out_cubic((t - 0.2) / 0.3))
            if bw > 0:
                d.rounded_rectangle((W // 2 - bw // 2, y + 52, W // 2 + bw // 2, y + 64), 6, fill=RED + (255,))
        canvas.alpha_composite(ov)

        # ── thumbnail card (slides up + pop, then gentle float)
        u = (t - 0.12) / 0.5
        if u > 0:
            sc = 0.55 + 0.45 * ease_out_back(u, 1.6)
            float_y = 8 * math.sin(t * 3.2) if u >= 1 else 0
            card = self.card
            if abs(sc - 1) > 1e-3:
                card = card.resize((int(card.width * sc), int(card.height * sc)), Image.Resampling.BILINEAR)
            cy = 860 + 260 * (1 - ease_out_cubic(u)) + float_y
            ang = -3 * (1 - ease_out_cubic(u)) * 4 + (1.2 * math.sin(t * 2.4) if u >= 1 else 0)
            if abs(ang) > 0.05:
                card = card.rotate(ang, Image.Resampling.BILINEAR, expand=True)
            canvas.alpha_composite(card, (int(W / 2 - card.width / 2), int(cy - card.height / 2)))

        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        # ── bouncing arrows pointing at the card
        a = clamp((t - 0.5) / 0.2)
        if a > 0 and self.landscape:
            # flèche vers le bas entre le titre et la carte
            by = 455 + 22 * abs(math.sin(t * 9))
            d.polygon([(W // 2 - 60, by), (W // 2 + 60, by), (W // 2, by + 70)],
                      fill=(255, 255, 255, int(255 * a)), outline=(0, 0, 0, int(200 * a)), width=4)
        elif a > 0:
            for side in (-1, 1):
                bx = W // 2 + side * (345 + 18 * abs(math.sin(t * 9)))
                by = 860
                tip = bx - side * 50
                d.polygon([(tip, by), (bx + side * 10, by - 46), (bx + side * 10, by + 46)],
                          fill=(255, 255, 255, int(255 * a)), outline=(0, 0, 0, int(200 * a)), width=4)
        canvas.alpha_composite(ov)

        # ── subscribe button
        bu = (t - 0.75) / 0.35
        clicked_t = 1.85
        if bu > 0:
            clicked = t >= clicked_t
            press = 1 - 0.08 * max(0, 1 - abs(t - clicked_t) / 0.08) if t > clicked_t - 0.08 else 1
            pulse = 1 + (0.04 * math.sin((t - 0.75) * 10) if not clicked and bu >= 1 else 0)
            sc = ease_out_back(bu, 2.2) * press * pulse
            bw, bh = 700, 150
            btn = Image.new("RGBA", (bw + 60, bh + 60), (0, 0, 0, 0))
            bd = ImageDraw.Draw(btn)
            col = (70, 70, 70, 255) if clicked else RED + (255,)
            bd.rounded_rectangle((30, 30, 30 + bw, 30 + bh), bh // 2, fill=col, outline="white", width=6)
            label = "ABONNÉ" if clicked else "ABONNE-TOI"
            if clicked:
                bd.text((30 + bw // 2 + 40, 30 + bh // 2), label, font=self.f_btn, fill="white", anchor="mm")
                cx0, cy0 = 30 + 150, 30 + bh // 2
                bd.line([(cx0 - 28, cy0), (cx0 - 6, cy0 + 24), (cx0 + 34, cy0 - 26)], fill="white", width=14, joint="curve")
            else:
                bd.text((30 + bw // 2 - 30, 30 + bh // 2), label, font=self.f_btn, fill="white", anchor="mm")
                ang = 0.35 * math.sin(t * 22) * (1 if bu >= 1 else 0)
                draw_bell(bd, 30 + bw - 95, 30 + bh // 2 + 2, 34, ang, (255, 255, 255, 255))
            btn, pad = shadowed(btn, blur=18, off=(0, 10), alpha=170)
            if sc > 0.02:
                btn = btn.resize((max(1, int(btn.width * sc)), max(1, int(btn.height * sc))), Image.Resampling.BILINEAR)
                bx, by = W // 2, 1560
                canvas.alpha_composite(btn, (int(bx - btn.width / 2), int(by - btn.height / 2)))
                # ring burst on click
                if clicked and t - clicked_t < 0.45:
                    r = 120 + 700 * ease_out_cubic((t - clicked_t) / 0.45)
                    al = int(220 * (1 - (t - clicked_t) / 0.45))
                    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    ImageDraw.Draw(ov).ellipse((bx - r, by - r * 0.45, bx + r, by + r * 0.45),
                                               outline=(255, 255, 255, al), width=10)
                    canvas.alpha_composite(ov)

            # ── cursor coming in to click
            cu = (t - 1.25) / 0.55
            if cu > 0 and t < 2.75:
                e = ease_out_cubic(cu)
                x = W + 80 + (W // 2 + 120 - (W + 80)) * e
                y = 1900 + (1575 - 1900) * e
                ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                draw_cursor(ImageDraw.Draw(ov), x, y, 1.4, abs(t - clicked_t) < 0.1)
                canvas.alpha_composite(ov)
        return canvas.convert("RGB")


# ─── audio ─────────────────────────────────────────────────────────────────
def lowpass_sweep(x, f0, f1):
    out = np.empty_like(x)
    y = 0.0
    n = len(x)
    for i in range(n):
        fc = f0 + (f1 - f0) * (i / n)
        a = 1 - math.exp(-2 * math.pi * fc / SR)
        y += a * (x[i] - y)
        out[i] = y
    return out


def sfx_whoosh(dur=0.45):
    n = int(SR * dur)
    t = np.linspace(0, 1, n)
    noise = RNG.standard_normal(n)
    sig = lowpass_sweep(noise, 300, 5000)
    env = np.sin(np.pi * t ** 0.6) ** 2
    return (sig * env * 0.9).astype(np.float32)


def sfx_boom(dur=0.5):
    t = np.arange(int(SR * dur)) / SR
    f = 90 * np.exp(-t * 6) + 45
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t * 7) * 0.9).astype(np.float32)


def sfx_pop(dur=0.15):
    t = np.arange(int(SR * dur)) / SR
    f = 400 + 1400 * t / dur
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30) * 0.6).astype(np.float32)


def sfx_click(dur=0.06):
    t = np.arange(int(SR * dur)) / SR
    return (RNG.standard_normal(len(t)) * np.exp(-t * 120) * 0.7 +
            np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 80) * 0.4).astype(np.float32)


def add(track, sfx, at, gain):
    i = int(at * SR)
    if i < 0:
        sfx, i = sfx[-i:], 0
    j = min(len(track), i + len(sfx))
    if j > i:
        track[i:j] += sfx[:j - i, None] * gain


# ─── main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--thumb", help="image miniature de ta dernière vidéo")
    ap.add_argument("--out", default="short_dynamique.mp4")
    args = ap.parse_args()

    global VIGNETTE
    VIGNETTE = make_vignette()
    tmp = Path(tempfile.mkdtemp())

    src_dur = probe_duration(args.input)
    cuts = [c / SPEED for c in detect_cuts(args.input)]
    dur = src_dur / SPEED
    nframes = int(dur * FPS)
    dur = nframes / FPS
    end_start = dur - END_DUR
    cuts = [c for c in cuts if c < end_start - 0.3]
    print(f"durée {src_dur:.2f}s -> {dur:.2f}s ; coupures : {[round(c, 2) for c in cuts]}")

    # thumbnail
    if args.thumb:
        thumb = Image.open(args.thumb)
    else:
        p = tmp / "thumb.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "24", "-i", args.input,
                        "-frames:v", "1", str(p)], check=True)
        thumb = Image.open(p)
    endcard = EndCard(thumb, custom=bool(args.thumb))

    # audio: sped-up original + sfx
    wav = tmp / "a.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", args.input, "-vn",
                    "-af", f"atempo={SPEED}", "-ar", str(SR), "-ac", "2", str(wav)], check=True)
    with wave.open(str(wav)) as wf:
        a = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    track = np.zeros((int(dur * SR), 2), np.float32)
    n = min(len(a), len(track))
    track[:n] = a[:n] * 0.82
    # duck original under end card a bit
    e0 = int(end_start * SR)
    ramp = np.clip((np.arange(len(track) - e0)) / (0.3 * SR), 0, 1)
    track[e0:] *= (1 - 0.45 * ramp)[:, None]
    whoosh = sfx_whoosh(); boom = sfx_boom()
    add(track, boom, 0.0, 0.5)
    for c in cuts:
        add(track, whoosh, c - 0.3, 0.35)
        add(track, boom, c, 0.45)
    add(track, whoosh, end_start - 0.25, 0.4)
    add(track, boom, end_start, 0.4)
    add(track, sfx_pop(), end_start + 0.8, 0.5)
    add(track, sfx_click(), end_start + 1.85, 0.8)
    add(track, sfx_pop(), end_start + 1.87, 0.45)
    track = np.tanh(track * 1.1) / np.tanh(1.1)
    mix = tmp / "mix.wav"
    with wave.open(str(mix), "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((track * 32767).astype(np.int16).tobytes())

    # video pipes
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", args.input, "-an",
                            "-vf", f"setpts=PTS/{SPEED},fps={FPS},scale={W}:{H}:flags=lanczos,format=rgb24",
                            "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-i", str(mix), "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", args.out],
                           stdin=subprocess.PIPE)
    fsz = W * H * 3
    last = None
    seg_starts = [0.0] + cuts
    for i in range(nframes):
        buf = dec.stdout.read(fsz)
        if len(buf) == fsz:
            last = buf
        t = i / FPS
        img = Image.frombuffer("RGB", (W, H), last)
        img = grade(img)
        # slow continuous zoom, alternating direction per segment
        seg = max(j for j, s in enumerate(seg_starts) if s <= t)
        s0 = seg_starts[seg]
        s1 = seg_starts[seg + 1] if seg + 1 < len(seg_starts) else dur
        p = (t - s0) / max(0.1, s1 - s0)
        z = 1.02 + 0.07 * (p if seg % 2 == 0 else 1 - p)
        img = zoom(img, z)
        # hook at t=0 (punch-in) + transition at each cut
        if t < TRANS_LEN:
            img = apply_cut_fx(img, 0, t / TRANS_LEN)
        for ci, c in enumerate(cuts):
            if c <= t < c + TRANS_LEN:
                img = apply_cut_fx(img, (ci + 1) % 4, (t - c) / TRANS_LEN)
            elif c - 0.1 <= t < c:  # pre-cut whip into the cut
                img = zoom(img, 1.06)
        if t >= end_start - 0.2 and t < end_start:
            img = apply_cut_fx(img, 2, 1 - (end_start - t) / 0.2 * 0.6)
        arr = (np.asarray(img).astype(np.float32) * VIGNETTE).astype(np.uint8)
        img = Image.fromarray(arr)
        if t >= end_start:
            img = endcard.render(img, t - end_start)
        enc.stdin.write(img.tobytes())
        if i % 60 == 0:
            print(f"  frame {i}/{nframes}", flush=True)
    enc.stdin.close(); enc.wait(); dec.kill()
    print("OK ->", args.out)


if __name__ == "__main__":
    main()
