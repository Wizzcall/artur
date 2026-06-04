"""
Coupe du Monde 2026 — Les Favoris
Format : 9:16  (1080×1920)  30 fps  ~38 s
Mots-clés 3D animés  +  musique épique générée
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import VideoClip, concatenate_videoclips
from moviepy.audio.AudioClip import AudioArrayClip
import math, os

# ─── Config ───────────────────────────────────────────────────────────────────
W, H    = 1080, 1920
FPS     = 30
SR      = 44100
BPM     = 128
BEAT    = 60.0 / BPM
FONT    = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
OUT     = '/home/user/artur/coupe_du_monde_2026.mp4'
rng     = np.random.default_rng(42)

INTRO_DUR = 3.0
TEAM_DUR  = 5.0
OUTRO_DUR = 4.0

# ─── Teams ────────────────────────────────────────────────────────────────────
TEAMS = [
    dict(name='BRESIL',     player='VINICIUS JR',     cups=5,
         kw=['SELECAO', '5 TITRES', 'FAVORI N°1'],
         bg1=(0,80,30),  bg2=(0,50,15),  hi=(255,215,0),   ac=(3,4,120)),
    dict(name='ARGENTINE',  player='LIONEL MESSI',    cups=3,
         kw=['ALBICELESTE', '3 TITRES', 'TENANTS'],
         bg1=(40,100,170), bg2=(20,60,120), hi=(255,255,255), ac=(64,180,220)),
    dict(name='FRANCE',     player='KYLIAN MBAPPE',   cups=2,
         kw=['LES BLEUS', '2 TITRES', 'DANGER MAX'],
         bg1=(0,30,140),  bg2=(0,15,80),  hi=(237,41,57),   ac=(255,255,255)),
    dict(name='ESPAGNE',    player='LAMINE YAMAL',    cups=4,
         kw=['FURIA ROJA', '4 TITRES', 'EURO 2024'],
         bg1=(160,10,20), bg2=(100,5,10), hi=(241,190,0),   ac=(255,255,255)),
    dict(name='ANGLETERRE', player='J. BELLINGHAM',   cups=1,
         kw=['THREE LIONS', 'QUART SIECLE', 'FAVORI'],
         bg1=(0,20,100),  bg2=(0,10,60),  hi=(200,16,46),   ac=(255,255,255)),
    dict(name='ALLEMAGNE',  player='FLORIAN WIRTZ',   cups=4,
         kw=['MANNSCHAFT', '4 TITRES', 'PUISSANCE'],
         bg1=(20,20,20),  bg2=(5,5,5),   hi=(255,206,0),   ac=(220,20,30)),
]

TOTAL_DUR = INTRO_DUR + len(TEAMS) * TEAM_DUR + OUTRO_DUR

# ─── Helpers ──────────────────────────────────────────────────────────────────

def fnt(size):
    return ImageFont.truetype(FONT, size)

def ease_out(x, p=3):
    x = float(np.clip(x, 0, 1))
    return 1 - (1 - x) ** p

def lerp(a, b, t):
    return a + (b - a) * float(np.clip(t, 0, 1))

def lerp_c(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))

def text_size(text, f):
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bb = draw.textbbox((0, 0), text, font=f)
    return bb[2] - bb[0], bb[3] - bb[1]

def gradient(c1, c2, w=W, h=H):
    arr = np.zeros((h, w, 3), np.uint8)
    for y in range(h):
        arr[y] = lerp_c(c1, c2, y / (h - 1))
    return Image.fromarray(arr)

# ─── 3D Extrude Text ─────────────────────────────────────────────────────────

def extrude_text(img, text, cx, cy, f, color, depth=14, shadow_dir=135):
    """3D extruded text centered at (cx, cy)."""
    tw, th = text_size(text, f)
    x0, y0 = cx - tw // 2, cy - th // 2
    rad = math.radians(shadow_dir)
    dx = math.cos(rad)
    dy = math.sin(rad) * 0.45

    draw = ImageDraw.Draw(img)
    # Back-to-front extrusion layers
    for i in range(depth, 0, -1):
        shade = tuple(max(0, int(c * (0.12 + 0.22 * (i / depth)))) for c in color)
        draw.text((x0 + dx * i, y0 + dy * i), text, font=f, fill=shade)
    # Front face
    draw.text((x0, y0), text, font=f, fill=color)
    return img

# ─── Scale-from-zero ("zoom in") animation ───────────────────────────────────

def zoom_text(img, text, cx, cy, f, color, prog, extrude=True, depth=14):
    """Text zooms in from a point — simulates 3D fly-in toward camera."""
    prog = ease_out(prog, 2.5)
    scale = 0.05 + 0.95 * prog

    tw, th = text_size(text, f)
    pad = depth + 4
    tmp = Image.new('RGBA', (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)

    bx, by = pad, pad
    if extrude:
        for i in range(depth, 0, -1):
            shade = tuple(max(0, int(c * (0.12 + 0.22 * (i / depth)))) for c in color) + (255,)
            d.text((bx + i, by + int(i * 0.45)), text, font=f, fill=shade)
    d.text((bx, by), text, font=f, fill=color + (255,))

    nw = max(2, int(tmp.width * scale))
    nh = max(2, int(tmp.height * scale))
    tmp = tmp.resize((nw, nh), Image.LANCZOS)

    px = max(0, cx - nw // 2)
    py = max(0, cy - nh // 2)

    base = img.convert('RGBA')
    base.paste(tmp, (px, py), tmp)
    return base.convert('RGB')

# ─── Slide-in animation ───────────────────────────────────────────────────────

def slide_text(img, text, cx, cy, f, color, prog, direction='left', extrude=True, depth=14):
    """Text slides in from left/right/top/bottom with 3D extrusion."""
    prog = ease_out(prog, 3)
    tw, th = text_size(text, f)

    if direction == 'left':
        cx_real = int(lerp(cx - W, cx, prog))
        cy_real = cy
    elif direction == 'right':
        cx_real = int(lerp(cx + W, cx, prog))
        cy_real = cy
    elif direction == 'top':
        cx_real = cx
        cy_real = int(lerp(cy - H // 3, cy, prog))
    elif direction == 'bottom':
        cx_real = cx
        cy_real = int(lerp(cy + H // 3, cy, prog))
    else:
        cx_real, cy_real = cx, cy

    if extrude:
        return extrude_text(img, text, cx_real, cy_real, f, color, depth)
    else:
        draw = ImageDraw.Draw(img)
        draw.text((cx_real - tw // 2, cy_real - th // 2), text, font=f, fill=color)
        return img

# ─── Spin-in (Y-axis rotation simulation) ────────────────────────────────────

def spin_text(img, text, cx, cy, f, color, prog, depth=14):
    """Simulates 3D Y-axis rotation: text 'spins' into position."""
    angle = lerp(math.pi / 2, 0, ease_out(prog, 2))  # 90° → 0°
    cos_a = abs(math.cos(angle))

    tw, th = text_size(text, f)
    pad = depth + 4
    full = Image.new('RGBA', (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(full)
    bx, by = pad, pad

    for i in range(depth, 0, -1):
        shade = tuple(max(0, int(c * (0.12 + 0.22 * (i / depth)))) for c in color) + (255,)
        d.text((bx + i, by + int(i * 0.45)), text, font=f, fill=shade)
    d.text((bx, by), text, font=f, fill=color + (255,))

    nw = max(2, int(full.width * cos_a))
    squeezed = full.resize((nw, full.height), Image.LANCZOS)

    px = cx - nw // 2
    py = cy - squeezed.height // 2
    base = img.convert('RGBA')
    base.paste(squeezed, (max(0, px), max(0, py)), squeezed)
    return base.convert('RGB')

# ─── Particles ────────────────────────────────────────────────────────────────

def add_particles(img, colors, n=60, seed=0, t=0.0):
    rp = np.random.default_rng(seed)
    xs = rp.integers(0, W, n)
    ys = rp.integers(0, H, n)
    rs = rp.integers(2, 7, n)
    sp = rp.uniform(15, 70, n)
    ph = rp.uniform(0, math.pi * 2, n)
    ci = rp.integers(0, len(colors), n)

    base = img.convert('RGBA')
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    for i in range(n):
        py = int((ys[i] - sp[i] * t) % H)
        px = int(xs[i] + math.sin(t * 1.8 + ph[i]) * 18) % W
        r = rs[i]
        c = colors[ci[i]]
        a = int(np.clip(150 + 80 * math.sin(t * 2.5 + ph[i]), 60, 230))
        d.ellipse([(px - r, py - r), (px + r, py + r)], fill=c + (a,))

    return Image.alpha_composite(base, ov).convert('RGB')

# ─── Flash on cut ─────────────────────────────────────────────────────────────

def entry_flash(img, t, duration=0.12):
    if t >= duration:
        return img
    alpha = (1 - t / duration) * 0.85
    white = Image.new('RGB', img.size, (255, 255, 255))
    return Image.blend(img, white, alpha)

# ─── Decorative stripes ───────────────────────────────────────────────────────

def diagonal_stripes(img, c1, c2, t=0.0, n=8, alpha=22):
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    sw = W // n
    off = int((t * 25) % (sw * 2))
    for i in range(-1, n + 3):
        x = i * sw * 2 - off
        c = c1 if i % 2 == 0 else c2
        pts = [(x - H, 0), (x, 0), (x + H, H), (x - H + H, H)]
        d.polygon(pts, fill=c + (alpha,))
    return Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')

# ─── Stars row ────────────────────────────────────────────────────────────────

def draw_stars(img, n, cx, cy, color, size=70, prog=1.0):
    prog = ease_out(prog, 2)
    draw = ImageDraw.Draw(img)
    star = '★'  # ★
    f = fnt(size)
    sw, sh = text_size(star, f)
    gap = sw + 8
    total = n * gap - 8
    x0 = cx - total // 2
    for i in range(n):
        item_prog = min(1.0, max(0, (prog * n - i)))
        if item_prog <= 0:
            continue
        a = int(255 * item_prog)
        px = int(x0 + i * gap)
        draw.text((px, cy - sh // 2), star, font=f, fill=tuple(color) + (a,))
    return img

# ─── Number counter animation ─────────────────────────────────────────────────

def draw_counter(img, value, cx, cy, f, color, prog):
    prog = ease_out(prog, 2)
    shown = max(0, int(round(value * prog)))
    text = str(shown)
    draw = ImageDraw.Draw(img)
    tw, th = text_size(text, f)
    draw.text((cx - tw // 2, cy - th // 2), text, font=f, fill=color)
    return img

# ─── Music ────────────────────────────────────────────────────────────────────

def gen_music(dur):
    n   = int(dur * SR)
    t   = np.linspace(0, dur, n, False)
    out = np.zeros(n)

    def adsr(ln, a=0.005, d=0.02, s=0.65, r=0.08):
        e = np.ones(ln) * s
        ai = min(int(a * SR), ln)
        di = min(int(d * SR), ln - ai)
        ri = min(int(r * SR), ln - ai - di)
        e[:ai] = np.linspace(0, 1, ai)
        e[ai:ai+di] = np.linspace(1, s, di)
        e[-ri:] = np.linspace(s, 0, ri)
        return e

    # Kick
    for i in range(int(dur / BEAT) + 1):
        idx = int(i * BEAT * SR)
        ln  = min(int(0.55 * SR), n - idx)
        if ln < 2: continue
        env  = np.exp(-7 * np.linspace(0, 1, ln))
        freq = 60 * np.exp(-18 * np.linspace(0, 0.08, ln))
        osc  = np.sin(2 * np.pi * np.cumsum(freq) / SR)
        out[idx:idx+ln] += np.tanh(osc * 3) * env * 0.75

    # Kick transient click
    for i in range(int(dur / BEAT) + 1):
        idx = int(i * BEAT * SR)
        ln  = min(int(0.035 * SR), n - idx)
        if ln < 2: continue
        noise = rng.standard_normal(ln)
        env   = np.exp(-90 * np.linspace(0, 1, ln))
        out[idx:idx+ln] += noise * env * 0.28

    # Snare (beats 2 & 4)
    for i in range(int(dur / (BEAT * 2)) + 1):
        for off in [BEAT, BEAT * 3]:
            ts  = i * BEAT * 4 + off
            idx = int(ts * SR)
            ln  = min(int(0.18 * SR), n - idx)
            if ln < 2: continue
            noise = rng.standard_normal(ln)
            env   = np.exp(-28 * np.linspace(0, 1, ln))
            out[idx:idx+ln] += noise * env * 0.42

    # Hi-hat (8ths)
    for i in range(int(dur / (BEAT / 2)) + 1):
        ts  = i * BEAT / 2
        idx = int(ts * SR)
        ln  = min(int(0.025 * SR), n - idx)
        if ln < 2: continue
        noise = rng.standard_normal(ln)
        env   = np.exp(-120 * np.linspace(0, 1, ln))
        out[idx:idx+ln] += noise * env * 0.14

    # Bass
    bass = [55, 55, 49, 52]
    for i in range(int(dur / BEAT) + 1):
        ts  = i * BEAT
        idx = int(ts * SR)
        ln  = min(int(BEAT * 0.75 * SR), n - idx)
        if ln < 2: continue
        f0  = bass[i % len(bass)]
        env = adsr(ln, a=0.01, d=0.04, s=0.5, r=0.12)
        osc = np.sin(2 * np.pi * f0 * np.arange(ln) / SR)
        osc += 0.25 * np.sin(2 * np.pi * f0 * 2 * np.arange(ln) / SR)
        out[idx:idx+ln] += np.tanh(osc * 2.2) * env * 0.55

    # Epic pad chord
    for freq in [220, 277.2, 329.6, 369.99]:  # Am chord
        osc = np.sin(2 * np.pi * freq * t)
        osc += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        env = np.clip(t / 2.5, 0, 1) * np.clip((dur - t) / 1.5, 0, 1)
        out += osc * env * 0.07

    # Brass stabs (every 4 beats)
    brass = [440, 523.25, 587.33, 493.88]
    for i, ts in enumerate(np.arange(BEAT * 2, dur, BEAT * 4)):
        idx = int(ts * SR)
        ln  = min(int(0.45 * SR), n - idx)
        if ln < 2: continue
        f0  = brass[i % len(brass)]
        env = adsr(ln, a=0.02, d=0.08, s=0.35, r=0.18)
        osc  = np.sin(2 * np.pi * f0 * np.arange(ln) / SR)
        osc += 0.45 * np.sin(2 * np.pi * f0 * 2 * np.arange(ln) / SR)
        osc += 0.18 * np.sin(2 * np.pi * f0 * 3 * np.arange(ln) / SR)
        out[idx:idx+ln] += np.tanh(osc * 1.6) * env * 0.30

    # Normalize
    mx = np.max(np.abs(out))
    if mx > 0:
        out = out / mx * 0.88
    stereo = np.column_stack([out, out]).astype(np.float32)
    return AudioArrayClip(stereo, fps=SR)

# ─── Frame generators ─────────────────────────────────────────────────────────

def intro_frame(t):
    bg = gradient((5, 5, 40), (15, 5, 70))
    bg = add_particles(bg, [(255,215,0), (200,220,255), (255,100,100)], n=90, seed=0, t=t)

    # "COUPE DU MONDE" — zoom in
    p1 = min(1.0, t / 0.7)
    bg = zoom_text(bg, 'COUPE DU MONDE', W//2, H//2 - 350, fnt(88), (255, 215, 0), p1)

    # "2026" — spin in
    p2 = max(0.0, (t - 0.45) / 0.8)
    bg = spin_text(bg, '2026', W//2, H//2 - 60, fnt(220), (255, 255, 255), p2, depth=20)

    # "LES FAVORIS" — slide from bottom
    p3 = max(0.0, (t - 1.1) / 0.65)
    bg = slide_text(bg, 'LES FAVORIS', W//2, H//2 + 220, fnt(78), (100, 200, 255), p3,
                    direction='bottom', extrude=True)

    # Sub-line
    p4 = max(0.0, (t - 1.8) / 0.5)
    if p4 > 0:
        col = tuple(int(c * ease_out(p4)) for c in (180, 180, 180))
        draw = ImageDraw.Draw(bg)
        f80 = fnt(44)
        txt = 'Qui soulèvera le trophée ?'
        tw, th = text_size(txt, f80)
        draw.text((W//2 - tw//2, H//2 + 380), txt, font=f80, fill=col)

    bg = entry_flash(bg, t, 0.1)
    return np.array(bg)


def team_frame(team, t):
    bg = gradient(team['bg1'], team['bg2'])
    bg = diagonal_stripes(bg, team['hi'], team['ac'], t=t)
    bg = add_particles(bg, [team['hi'], team['ac'], (255,255,255)],
                       n=55, seed=hash(team['name']) % 1000, t=t)

    draw = ImageDraw.Draw(bg)

    # Horizontal separator lines
    for y_off in [-2, 0, 2]:
        draw.line([(60, H//2 + y_off), (W - 60, H//2 + y_off)],
                  fill=team['hi'] + (60,), width=1)

    # ── Team name (big, zoom in) ──
    p_name = min(1.0, t / 0.55)
    bg = zoom_text(bg, team['name'], W//2, H//2 - 520, fnt(115), team['hi'], p_name, depth=16)

    # ── Player name (slide from left) ──
    p_player = max(0.0, (t - 0.35) / 0.5)
    bg = slide_text(bg, team['player'], W//2, H//2 - 340, fnt(65),
                    (255, 255, 255), p_player, direction='left', extrude=True, depth=10)

    # ── Keyword 1 (spin in) ──
    p_kw1 = max(0.0, (t - 0.75) / 0.55)
    bg = spin_text(bg, team['kw'][0], W//2, H//2 - 140, fnt(90), team['hi'], p_kw1, depth=14)

    # ── Keyword 2 (slide from right) ──
    p_kw2 = max(0.0, (t - 1.15) / 0.5)
    bg = slide_text(bg, team['kw'][1], W//2, H//2 + 60, fnt(68),
                    team['ac'] if sum(team['ac']) > 200 else (220, 220, 220),
                    p_kw2, direction='right', extrude=True, depth=10)

    # ── Keyword 3 (zoom in) ──
    p_kw3 = max(0.0, (t - 1.55) / 0.5)
    bg = zoom_text(bg, team['kw'][2], W//2, H//2 + 240, fnt(72),
                   (200, 220, 255), p_kw3, extrude=True, depth=10)

    # ── Stars (animated row) ──
    p_stars = max(0.0, (t - 2.0) / 0.8)
    if p_stars > 0:
        bg = draw_stars(bg, team['cups'], W//2, H//2 + 430, team['hi'],
                        size=72, prog=p_stars)

    # ── "X TITRES MONDIAUX" label ──
    p_label = max(0.0, (t - 2.6) / 0.5)
    if p_label > 0:
        label_c = tuple(int(c * ease_out(p_label)) for c in (180, 180, 180))
        f44 = fnt(42)
        label = f'{team["cups"]} TITRES MONDIAUX'
        tw, th = text_size(label, f44)
        draw2 = ImageDraw.Draw(bg)
        draw2.text((W//2 - tw//2, H//2 + 540), label, font=f44, fill=label_c)

    # ── Pulsing border ring ──
    pulse = 0.5 + 0.5 * math.sin(t * 5)
    ov = Image.new('RGBA', bg.size, (0, 0, 0, 0))
    dov = ImageDraw.Draw(ov)
    b = 18
    a_border = int(40 + 40 * pulse)
    dov.rectangle([(b, b), (W - b, H - b)],
                  outline=team['hi'] + (a_border,), width=4)
    bg = Image.alpha_composite(bg.convert('RGBA'), ov).convert('RGB')

    bg = entry_flash(bg, t)
    return np.array(bg)


def outro_frame(t):
    bg = gradient((5, 5, 30), (30, 5, 60))
    bg = add_particles(bg, [(255,215,0),(255,80,80),(80,200,255),(80,255,140)],
                       n=120, seed=99, t=t)
    draw = ImageDraw.Draw(bg)

    # "QUI SERA CHAMPION ?" — big zoom
    p1 = min(1.0, t / 0.75)
    bg = zoom_text(bg, 'QUI SERA', W//2, H//2 - 680, fnt(105), (255, 215, 0), p1, depth=14)
    p2 = max(0.0, (t - 0.4) / 0.7)
    bg = spin_text(bg, 'CHAMPION ?', W//2, H//2 - 500, fnt(115), (255, 255, 255), p2, depth=16)

    # Animated horizontal bar
    bar_prog = ease_out(max(0.0, (t - 0.9) / 0.4))
    if bar_prog > 0:
        bw = int(W * bar_prog * 0.8)
        draw2 = ImageDraw.Draw(bg)
        draw2.rectangle([(W//2 - bw//2, H//2 - 360), (W//2 + bw//2, H//2 - 354)],
                        fill=(255, 215, 0, 200))

    # Teams list (slide in one by one)
    team_lines = [
        ('BRESIL',     (0, 156, 59)),
        ('ARGENTINE',  (116, 172, 223)),
        ('FRANCE',     (0, 35, 149)),
        ('ESPAGNE',    (170, 21, 27)),
        ('ANGLETERRE', (200, 16, 46)),
        ('ALLEMAGNE',  (220, 220, 220)),
    ]
    f_team = fnt(68)
    start_y = H//2 - 290

    for i, (name, color) in enumerate(team_lines):
        p = max(0.0, (t - 1.0 - i * 0.22) / 0.45)
        if p <= 0:
            continue
        prog = ease_out(p, 3)
        x_offset = int((1 - prog) * -W)
        tw, th = text_size(name, f_team)
        x = W//2 - tw//2 + x_offset
        y = start_y + i * 108
        ImageDraw.Draw(bg).text((x, y), name, font=f_team, fill=color)

    # Bottom tag line
    p_tag = max(0.0, (t - 3.0) / 0.5)
    if p_tag > 0:
        bg = slide_text(bg, 'COUPE DU MONDE 2026', W//2, H - 160,
                        fnt(56), (255, 215, 0), p_tag, direction='bottom', extrude=False)

    bg = entry_flash(bg, t, 0.12)
    return np.array(bg)

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print('🎬 Coupe du Monde 2026 — génération...')

    clips = []

    print('  [1/9] Intro…')
    clips.append(VideoClip(intro_frame, duration=INTRO_DUR).with_fps(FPS))

    for i, team in enumerate(TEAMS, 2):
        print(f'  [{i}/9] {team["name"]}…')
        def make(t, _t=team):
            return team_frame(_t, t)
        clips.append(VideoClip(make, duration=TEAM_DUR).with_fps(FPS))

    print('  [9/9] Outro…')
    clips.append(VideoClip(outro_frame, duration=OUTRO_DUR).with_fps(FPS))

    print('  Assemblage…')
    final = concatenate_videoclips(clips)

    print('  Musique…')
    audio = gen_music(TOTAL_DUR)
    final = final.with_audio(audio)

    print(f'  Export → {OUT}')
    final.write_videofile(
        OUT, fps=FPS,
        codec='libx264', audio_codec='aac',
        preset='fast', logger=None,
    )
    print(f'✅  {OUT}')

if __name__ == '__main__':
    main()
