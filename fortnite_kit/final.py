"""Assemble the full video:
  cold open (rage + best moments, ~13 s) -> animated intro (~24 s)
  -> 5 spot sections -> animated ranking (by chest count) + outro.

Run after spots.py has rendered every section into renders/.
Usage: python3 fortnite_kit/final.py
"""
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlays as O
import make_music as MM
import spot_edit as SE
from cold_open import build_cold_open
from spots import SPOTS

W, H, FPS, SR = 1920, 1080, 30, 48000
R = "renders"
WORK = os.path.join(R, "work", "final")
CHANNEL = "WIZZCALL"

# ranking by number of chests (ties: faster farm time first)
RESULTS = [  # key, display name, chests, filmed farm seconds
    ("spot3_loguetown", "LOGUETOWN", 12, 210),
    ("spot1_rubber_resort", "RUBBER RESORT", 11, 119),
    ("spot4_arlong_park", "BIVOUAC DES BOUCANIERS", 8, 115),
    ("spot2_lantern_landing", "LANTERN LANDING", 7, 150),
    ("spot5_the_chest", "FORTERESSE DE LIL' UZI", 5, 57),
]
ORDER = ["spot1_rubber_resort", "spot2_lantern_landing", "spot3_loguetown",
         "spot4_arlong_park", "spot5_the_chest"]
NAMES = {k: n for k, n, *_ in RESULTS}

ease_back, ease = SE.ease_out_back, SE.ease_out
paste = SE.paste_center
run = SE.run


def base(key):
    return os.path.join(R, "work", key, "base.mkv")


def norm(key, clip_name):
    spec = SPOTS[key]
    path = next(p for p, *_ in spec["clips"] if os.path.basename(p) == clip_name)
    return SE.normalize_source(path, os.path.join(R, "work", key))


def edit_t(key, g):
    return SE.Timeline(SPOTS[key]).edit_at(g)


# ------------------------------------------------------------ cold open
def cold_open():
    out = os.path.join(WORK, "cold_open.mp4")
    moments = [
        dict(src=base("spot1_rubber_resort"), start=edit_t("spot1_rubber_resort", 18.6) - 0.5, dur=1.2,
             kind="best", caption="EN VOITURE !"),
        dict(src=base("spot1_rubber_resort"), start=edit_t("spot1_rubber_resort", 40.73) - 0.9, dur=1.1,
             kind="best", caption="DOUBLE COFFRE !"),
        dict(src=norm("spot2_lantern_landing", "part4.mp4"), start=4.4, dur=1.4, kind="rage", caption="NOOON !!"),
        dict(src=base("spot5_the_chest"), start=24.3, dur=1.2, kind="best", caption="3 COFFRES EN 7 S"),
        dict(src=base("spot2_lantern_landing"), start=15.6, dur=1.3, kind="best", caption="ÉLIMINATION !"),
        dict(src=norm("spot2_lantern_landing", "part5.mp4"), start=14.8, dur=1.4, kind="rage", caption="SORS DE LÀ !!"),
        dict(src=base("spot4_arlong_park"), start=43.9, dur=1.0, kind="best", caption="DANS LA TEMPÊTE"),
        dict(src=norm("spot2_lantern_landing", "part6.mp4"), start=22.0, dur=1.3, kind="rage",
             caption="C'EST PAS POSSIBLE"),
        dict(src=base("spot3_loguetown"), start=17.4, dur=1.0, kind="best", caption="4 COFFRES EN 25 S"),
        dict(src=norm("spot4_arlong_park", "clip2_part1_0-30s.mp4"), start=25.95, dur=1.5, kind="rage",
             caption="MAIS NON !"),
        dict(src=base("spot3_loguetown"), start=33.7, dur=2.0, kind="slowmo", caption="12 COFFRES ?!"),
    ]
    return build_cold_open(moments, music=None, out=out)


# ------------------------------------------------------------ generic animated section
def bg_montage(snips, out, blur=True):
    """Background: given (src, start, dur) snippets, concat them, blurred + darkened."""
    parts = []
    for i, (src, st, d) in enumerate(snips):
        p = os.path.join(WORK, f"{os.path.basename(out)}_{i}.mkv")
        vf = f"fps={FPS},scale={W}:{H},setsar=1" + (",boxblur=12:2,eq=brightness=-0.18:saturation=1.2" if blur else "")
        run(["ffmpeg", "-y", "-ss", str(st), "-t", str(d), "-i", src, "-an", "-vf", vf,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", p])
        parts.append(p)
    lst = out + ".txt"
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


def render_section(bgv, duration, frame_fn, out):
    n = int(round(duration * FPS))
    cmd = ["ffmpeg", "-y", "-i", bgv, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration=30[b];[b][1:v]overlay=format=auto,format=yuv420p[v]",
           "-map", "[v]", "-frames:v", str(n), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-an", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for fi in range(n):
        cv = blank.copy()
        frame_fn(cv, fi / FPS)
        proc.stdin.write(cv.tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode()
    if proc.wait():
        raise RuntimeError(err[-2000:])
    return out


def music_bed(preset, duration, out, sfx=(), drop_at=None, gain=0.9):
    mw = os.path.join(WORK, f"music_{preset}.wav")
    if not os.path.exists(mw):
        MM.write(mw, MM.render(preset, duration=max(120, duration + 30),
                               seed=list(MM.PRESETS).index(preset) * 11 + 3))
    m = SE._read_wav(mw)
    off = 0.0 if drop_at is None else max(0.0, SE.drop_time(preset) - drop_at)
    N = int(duration * SR)
    idx = np.clip((np.arange(N) / SR + off) * 44100, 0, len(m) - 2)
    i0 = idx.astype(int)
    fr = (idx - i0)[:, None]
    mix = (m[i0] * (1 - fr) + m[i0 + 1] * fr) * gain
    for sig, at, g in sfx:
        i = int(at * SR)
        j = min(N, i + len(sig))
        if 0 <= i < N:
            mix[i:j] += (sig[:j - i] * g)[:, None]
    fo = int(1.0 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    mix = np.tanh(mix * 1.1) / math.tanh(1.1) * 0.9
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).tobytes())
    return out


def mux(video, audio, out):
    run(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest", out])
    return out


# ------------------------------------------------------------ intro
from PIL import ImageDraw, ImageFilter


def chest_moments(key, n=3):
    """Edit times (in the spot's base.mkv) of its chest openings, spread out."""
    spec = SPOTS[key]
    tl = SE.Timeline(spec)
    ts = [tl.edit_at(g) for g, *_ in sorted(spec["events"])]
    if len(ts) <= n:
        return ts
    return [ts[round(i * (len(ts) - 1) / (n - 1))] for i in range(n)]


def punch_montage(snips, out, dark=0.1):
    """Sharp beat-cut montage: every snippet starts with a zoom punch."""
    parts = []
    for i, (src, st, d) in enumerate(snips):
        p = os.path.join(WORK, f"{os.path.basename(out)}_{i}.mkv")
        z = "(1.03+0.12*exp(-t*9))"
        vf = (f"fps={FPS},scale={W}:{H},setsar=1,"
              f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame,"
              f"crop={W}:{H},eq=brightness={-dark}:saturation=1.3:contrast=1.06,setpts=PTS-STARTPTS")
        run(["ffmpeg", "-y", "-ss", f"{st:.3f}", "-t", f"{d:.3f}", "-i", src, "-an", "-vf", vf,
             "-frames:v", str(round(d * FPS)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-pix_fmt", "yuv420p", p])
        parts.append(p)
    lst = out + ".txt"
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


def rays_img(size=1500, n=16, col=(255, 220, 90)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size / 2
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = a0 + math.pi / n * 0.8
        d.polygon([(c, c), (c + c * 1.4 * math.cos(a0), c + c * 1.4 * math.sin(a0)),
                   (c + c * 1.4 * math.cos(a1), c + c * 1.4 * math.sin(a1))], fill=col + (70,))
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size, size], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(size / 6))
    img.putalpha(Image.composite(img.split()[3], Image.new("L", img.size, 0), m))
    return img.filter(ImageFilter.GaussianBlur(3))


def thumb_card(still, num, name, rarity):
    c1, c2 = O.RARITY[rarity]
    tw, th = 500, 281
    th_img = still.resize((tw, th), Image.LANCZOS).convert("RGBA")
    card = O.glass_card(tw + 24, th + 24, c1, c2, radius=26)
    m = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, tw - 1, th - 1], 20, fill=255)
    card.paste(th_img, (30 + 12, 30 + 12), m)
    badge = O.text_3d(str(num), 110, O.YELLOW, O.GOLD, glow_color=O.GOLD)
    card.alpha_composite(badge, (0, 0))
    label = O.box_3d(name, None, rarity=rarity, size=40)
    out = Image.new("RGBA", (max(card.width, label.width), card.height + label.height - 70), (0, 0, 0, 0))
    out.alpha_composite(card, ((out.width - card.width) // 2, 0))
    out.alpha_composite(label, ((out.width - label.width) // 2, card.height - 70))
    return out


def grab_still(key, t):
    p = os.path.join(WORK, f"still_{key}.png")
    run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", base(key), "-frames:v", "1", p])
    return Image.open(p).convert("RGB")


def intro():
    D = 24.0
    BEAT = 60 / MM.PRESETS["intro"]["bpm"]
    seg = 4 * BEAT  # cut every bar
    pool = []
    for k in ["spot3_loguetown", "spot1_rubber_resort", "spot5_the_chest", "spot2_lantern_landing",
              "spot4_arlong_park"]:
        pool += [(base(k), max(0.0, t - 0.5)) for t in chest_moments(k, 3)]
    order = [pool[i % len(pool)] for i in (0, 3, 6, 9, 12, 1, 4, 7, 10, 13, 2, 5, 8, 11, 14)]
    n = int(math.ceil(D / seg))
    bgv = punch_montage([(src, st, seg) for src, st in order[:n]], os.path.join(WORK, "intro_bg.mkv"))
    cut_times = [i * seg for i in range(n)]

    C = SE.Cache()
    rays = rays_img()
    rays_blue = rays_img(col=(120, 200, 255))
    ch = O.text_3d(CHANNEL, 190, O.WHITE, (185, 215, 255), tilt=-3, glow_color=O.CYAN)
    pres = O.text_3d("PRÉSENTE", 64, O.YELLOW, O.GOLD, alt=True, glow_color=O.GOLD)
    t1 = O.text_3d("5 SPOTS", 260, O.YELLOW, O.GOLD, tilt=-3, glow_color=O.GOLD)
    t2 = O.box_3d("POUR FARMER LE JETON PIRATE SHOP", None, rarity="epic", size=70)
    c1 = O.box_3d("JE TESTE LES 5 MEILLEURS SPOTS", "AVEC UN CHRONO DE 3:30", rarity="legendary", size=66)
    c2 = O.text_3d("LE PLUS DE COFFRES GAGNE !", 96, O.GREEN, (20, 160, 70), tilt=2, glow_color=O.GREEN)
    chest_s = O.chest_icon(150, open_=True)
    rar = ["epic", "rare", "legendary", "epic", "rare"]
    cards = [thumb_card(grab_still(k, chest_moments(k, 2)[-1]), i + 1, NAMES[k], rar[i]) for i, k in enumerate(ORDER)]
    pos = [(W * 0.2, 330), (W * 0.5, 330), (W * 0.8, 330), (W * 0.35, 760), (W * 0.65, 760)]
    q = O.text_3d("QUEL SPOT EST LE MEILLEUR ?", 104, O.WHITE, (190, 215, 255), glow_color=O.MAGENTA)
    go = O.text_3d("C'EST PARTI !", 200, O.GREEN, (20, 160, 70), tilt=-4, glow_color=O.GREEN)
    impacts = [0.0, 3.4, 8.2, 13.2] + [13.6 + i * 0.7 for i in range(5)] + [22.4]
    rng = np.random.default_rng(5)
    sparks = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(-60, 60), rng.uniform(-260, -90),
               rng.uniform(3, 8), rng.uniform(0, 1.2)) for _ in range(70)]
    rain = [(rng.uniform(100, W - 100), rng.uniform(0, 2.5), rng.uniform(-120, 120), rng.uniform(0.6, 1.1))
            for _ in range(16)]

    def shake(t):
        s = sum(22 * math.exp(-(t - a) * 9) for a in impacts if 0 <= t - a < 0.6)
        return s * math.sin(t * 90), s * math.cos(t * 77) * 0.6

    def fr(cv, t):
        sx, sy = shake(t)
        d = ImageDraw.Draw(cv)
        if t < 3.4:  # dark opening
            d.rectangle([0, 0, W, H], fill=(5, 3, 20, int(185 * (1 - ease((t - 3.1) / 0.3)))))
        else:        # vignette panel for readability
            d.rectangle([0, 0, W, H], fill=(10, 5, 35, 70))
        for ct in cut_times:  # white flash on every cut
            dt = t - ct
            if 0 <= dt < 0.15 and t > 3.3:
                d.rectangle([0, 0, W, H], fill=(255, 255, 255, int(150 * (1 - dt / 0.15))))
        # rotating rays behind the big titles
        if 3.4 <= t < 13.2 or t >= 22.4:
            rr = C.get_or(("rays", int(t * 12) % 180, t >= 22.4),
                          lambda: (rays_blue if t >= 22.4 else rays).rotate((t * 12) % 180 * 2, resample=Image.BILINEAR))
            paste(cv, rr, W / 2 + sx, H * 0.42 + sy, 1.0 + 0.04 * math.sin(t * 2 * math.pi / BEAT))
        # gold sparks rising
        if t >= 3.4:
            for x0, y0, vx, vy, r, ph in sparks:
                tt = (t + ph * 3) % 3.0
                x, y = x0 + vx * tt, (y0 + vy * tt) % H
                a = int(220 * (1 - tt / 3.0))
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 220, 90, a))
        # shockwave rings on impacts
        for a0 in impacts[:4] + impacts[-1:]:
            dt = t - a0
            if 0 <= dt < 0.5:
                R = 120 + 1400 * ease(dt / 0.5)
                d.ellipse([W / 2 - R, H * 0.42 - R * 0.6, W / 2 + R, H * 0.42 + R * 0.6],
                          outline=(255, 255, 255, int(220 * (1 - dt / 0.5))), width=14)

        if t < 3.4:
            a = 1 - ease((t - 3.05) / 0.35)
            paste(cv, ch, W / 2 + sx, H * 0.42 + sy, ease_back(t / 0.35) * (1 + 0.02 * math.sin(t * 9)), a)
            paste(cv, pres, W / 2, H * 0.64, ease_back((t - 0.6) / 0.35), a)
        if 3.4 <= t < 8.2:
            dd = t - 3.4
            a = 1 - ease((dd - 4.45) / 0.35)
            k = 1.8 - 0.8 * ease_back(dd / 0.3)  # slam from big to normal
            paste(cv, t1, W / 2 + sx, H * 0.38 + sy, k * (1 + 0.025 * math.sin(dd * 2 * math.pi / BEAT)), a)
            paste(cv, t2, W / 2 + (1 - ease_back((dd - 0.45) / 0.4)) * -1500, H * 0.70, 1, a)
            for i, xx in enumerate((W * 0.13, W * 0.87)):
                paste(cv, chest_s, xx, H * 0.40 + 20 * math.sin(dd * 3 + i), ease_back((dd - 0.8 - i * 0.15) / 0.35), a)
        if 8.2 <= t < 13.2:
            dd = t - 8.2
            a = 1 - ease((dd - 4.65) / 0.35)
            for x, ph, vx, sc in rain:  # chests raining down
                tt = dd - ph
                if tt > 0:
                    yy = -150 + 700 * tt * tt
                    if yy < H + 150:
                        im = C.get_or(("ch", round(sc * 10), int(tt * 8) % 12),
                                      lambda: O.chest_icon(int(150 * sc), open_=False).rotate((int(tt * 8) % 12) * 30, expand=True))
                        paste(cv, im, x + vx * tt, yy, 1, 0.9 * a)
            paste(cv, c1, W / 2 + sx, H * 0.26 + sy, ease_back(dd / 0.35), a)
            rem = SE.CHRONO - min(SE.CHRONO, max(0, dd - 0.5) * 60)
            tm = C.get_or(("t", round(rem)), lambda: O.circular_timer(max(rem, 0), SE.CHRONO, size=300))
            paste(cv, tm, W / 2, H * 0.62, ease_back((dd - 0.3) / 0.4), a)
            paste(cv, c2, W / 2, H * 0.90, ease_back((dd - 2.0) / 0.35) * (1 + 0.03 * math.sin(dd * 7)), a)
        if 13.2 <= t < 19.9:
            dd = t - 13.2
            a = 1 - ease((dd - 6.35) / 0.35)
            for i, (cd, (x, y)) in enumerate(zip(cards, pos)):
                k = ease_back((dd - 0.4 - i * 0.7) / 0.35)
                if k > 0:
                    paste(cv, cd, x + sx * 0.5, y + sy * 0.5 + 8 * math.sin(dd * 2 + i), 0.82 * k, a)
        if 19.9 <= t < 22.4:
            dd = t - 19.9
            paste(cv, q, W / 2 + sx, H * 0.45 + sy, ease_back(dd / 0.35) * (1 + 0.02 * math.sin(dd * 8)),
                  1 - ease((dd - 2.2) / 0.3))
        if t >= 22.4:
            dd = t - 22.4
            paste(cv, go, W / 2 + sx, H * 0.48 + sy, 2.0 - ease_back(dd / 0.3))
            if dd < 0.18:
                d.rectangle([0, 0, W, H], fill=(255, 255, 255, int(200 * (1 - dd / 0.18))))

    v = render_section(bgv, D, fr, os.path.join(WORK, "intro_v.mp4"))
    imp, wh, ding = SE._sfx_impact(), SE._sfx_whoosh(), SE._sfx_ding()
    coin, riser, pop = SE._sfx_coins(), SE._sfx_riser(2.0), SE._sfx_pop()
    sfx = [(imp, 0.0, 1.6), (riser, 1.4, 1.0), (imp, 3.4, 1.8), (wh, 3.75, 1.0), (coin, 4.2, 1.2),
           (wh, 8.1, 1.0), (imp, 8.2, 1.3), (ding, 9.0, 1.2), (coin, 10.2, 1.0), (ding, 10.4, 1.0),
           (wh, 13.1, 1.0), (imp, 13.2, 1.2)]
    sfx += [(wh, 13.5 + i * 0.7, 0.9) for i in range(5)] + [(pop, 13.65 + i * 0.7, 1.0) for i in range(5)]
    sfx += [(wh, 19.8, 1.0), (pop, 20.0, 1.0), (riser, 20.4, 1.2), (imp, 22.4, 2.0), (coin, 22.5, 1.2)]
    sfx += [(wh, ct - 0.12, 0.5) for ct in cut_times if ct > 3.5]
    a = music_bed("intro", D, os.path.join(WORK, "intro.wav"), sfx, drop_at=3.4, gain=0.75)
    return mux(v, a, os.path.join(WORK, "intro.mp4"))


# ------------------------------------------------------------ ranking + outro
def ranking():
    per = [5.5, 5.5, 5.5, 5.5, 8.0]  # 5th .. 1st
    D_rank = sum(per)
    D_sum, D_out = 6.0, 8.0
    D = D_rank + D_sum + D_out
    snips = {"spot5_the_chest": (24.0, 6), "spot2_lantern_landing": (40.0, 6), "spot1_rubber_resort": (15.0, 6),
             "spot4_arlong_park": (37.0, 6), "spot3_loguetown": (33.0, 8)}
    order = list(reversed(RESULTS))  # 5th first
    bgv = bg_montage([(base(k), snips[k][0], snips[k][1]) for k, *_ in order]
                     + [(base("spot3_loguetown"), 45, 6), (base("spot5_the_chest"), 10, 8)],
                     os.path.join(WORK, "rank_bg.mkv"))
    C = SE.Cache()
    head = O.box_3d("CLASSEMENT FINAL", "PAR NOMBRE DE COFFRES", rarity="legendary", size=60)
    starts = np.cumsum([0] + per[:-1])
    rar = {1: "legendary", 2: "epic", 3: "rare", 4: "rare", 5: "uncommon"}

    def fr(cv, t):
        if t < D_rank:
            paste(cv, head, W / 2, 120, ease_back(t / 0.4))
            i = int(np.searchsorted(starts, t, side="right") - 1)
            d = t - starts[i]
            k, name, chests, secs = order[i]
            rank = 5 - i
            a = 1 - ease((d - per[i] + 0.35) / 0.35)
            col = (O.YELLOW, O.GOLD) if rank == 1 else (O.WHITE, (190, 215, 255))
            big = C.get_or(("rk", rank), lambda: O.text_3d(f"#{rank}", 260 if rank == 1 else 200, *col,
                                                           glow_color=O.GOLD if rank == 1 else O.CYAN))
            paste(cv, big, W / 2 - 620, H * 0.52, ease_back(d / 0.35), a)
            nm = C.get_or(("nm", rank), lambda: O.box_3d(name, None, rarity=rar[rank], size=62))
            paste(cv, nm, W / 2 + 180, H * 0.40, ease_back((d - 0.2) / 0.4), a)
            n = min(chests, int(max(0, d - 0.8) * 9))
            pop = ((d - 0.8) * 9) % 1 if n < chests else 0
            cnt = C.get_or(("cn", n, round(pop * 10)), lambda: O.chest_counter(n, pop=pop if n else 0))
            paste(cv, cnt, W / 2 + 60, H * 0.66, ease_back((d - 0.5) / 0.4) * 1.25, a)
            tm = C.get_or(("tm", rank), lambda: O.box_3d(f"EN {SE.fmt_mmss(secs)} DE FARM", None, rarity="rare", size=44))
            paste(cv, tm, W / 2 + 520, H * 0.66, ease_back((d - 1.6) / 0.4), a)
            if rank == 1 and d > 2.6:
                win = C.get_or("win", lambda: O.text_3d("MEILLEUR SPOT !", 120, O.YELLOW, O.GOLD, tilt=-3,
                                                        glow_color=O.GOLD))
                paste(cv, win, W / 2, H * 0.86, ease_back((d - 2.6) / 0.35) * (1 + 0.04 * math.sin(d * 6)), a)
        elif t < D_rank + D_sum:
            d = t - D_rank
            a = 1 - ease((d - D_sum + 0.35) / 0.35)
            paste(cv, head, W / 2, 120, 1, a)
            for j, (k, name, chests, secs) in enumerate(RESULTS):
                row = C.get_or(("row", j), lambda: O.box_3d(f"#{j + 1}  {name}  -  {chests} COFFRES", None,
                                                            rarity=rar[j + 1], size=52))
                kk = ease_back((d - 0.2 - j * 0.25) / 0.35)
                if kk > 0:
                    paste(cv, row, W / 2 + (1 - kk) * 1600, 300 + j * 165, 1, a)
        else:
            d = t - D_rank - D_sum
            sub = C.get_or("sub", lambda: O.text_3d("ABONNE-TOI !", 170, O.RED, (170, 0, 30), tilt=-3,
                                                    glow_color=O.RED))
            ch = C.get_or("ch", lambda: O.text_3d(CHANNEL, 130, O.WHITE, (185, 215, 255), glow_color=O.CYAN))
            q = C.get_or("q", lambda: O.box_3d("ET TOI, TU FARMES OÙ ?", "DIS-LE EN COMMENTAIRE", rarity="epic", size=60))
            paste(cv, ch, W / 2, H * 0.22, ease_back(d / 0.4))
            paste(cv, sub, W / 2, H * 0.48, ease_back((d - 0.4) / 0.4) * (1 + 0.05 * math.sin(d * 5)))
            paste(cv, q, W / 2, H * 0.78, ease_back((d - 1.0) / 0.4))

    v = render_section(bgv, D, fr, os.path.join(WORK, "rank_v.mp4"))
    imp, wh, ding = SE._sfx_impact(), SE._sfx_whoosh(), SE._sfx_ding()
    sfx = [(imp, 0.0, 0.8)]
    for i, (k, name, chests, secs) in enumerate(order):
        s0 = float(starts[i])
        sfx += [(wh, s0, 1.1), (imp, s0 + 0.15, 1.3)]
        sfx += [(ding, s0 + 0.8 + c / 9, 0.6) for c in range(1, chests + 1)]
    sfx += [(imp, float(starts[4]) + 2.6, 1.8), (SE._sfx_coins(), float(starts[4]) + 2.7, 1.3)]
    sfx += [(wh, D_rank + 0.2 + j * 0.25, 0.45) for j in range(5)]
    sfx += [(imp, D_rank + D_sum, 1.5), (ding, D_rank + D_sum + 0.4, 1.2)]
    a = music_bed("classement", D, os.path.join(WORK, "rank.wav"), sfx, drop_at=float(starts[4]))
    return mux(v, a, os.path.join(WORK, "ranking.mp4"))


# ------------------------------------------------------------ assembly
def conform(src, out):
    run(["ffmpeg", "-y", "-i", src, "-vf", f"scale={W}:{H},fps={FPS},setsar=1,format=yuv420p",
         "-af", f"aresample={SR},aformat=channel_layouts=stereo", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "15", "-c:a", "pcm_s16le", out])
    return out


def duration(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)


def assemble(parts, out):
    TD = 0.35
    trans = ["zoomin"] + ["fadewhite"] * (len(parts) - 2)
    ins, fv, fa = [], [], []
    for p in parts:
        ins += ["-i", p]
    durs = [duration(p) for p in parts]
    off = 0.0
    vlab, alab = "[0:v]", "[0:a]"
    for i in range(1, len(parts)):
        off += durs[i - 1] - TD
        fv.append(f"{vlab}[{i}:v]xfade=transition={trans[i - 1]}:duration={TD}:offset={off:.3f}[v{i}]")
        fa.append(f"{alab}[{i}:a]acrossfade=d={TD}[a{i}]")
        vlab, alab = f"[v{i}]", f"[a{i}]"
    n = len(parts) - 1
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fv + fa), "-map", f"[v{n}]", "-map", f"[a{n}]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    return out


if __name__ == "__main__":
    os.makedirs(WORK, exist_ok=True)
    steps = sys.argv[1:] or ["cold", "intro", "rank", "final"]
    if "cold" in steps:
        cold_open()
    if "intro" in steps:
        intro()
    if "rank" in steps:
        ranking()
    if "final" in steps:
        parts = [os.path.join(WORK, "cold_open.mp4"), os.path.join(WORK, "intro.mp4")] + \
                [os.path.join(R, f"{k}.mp4") for k in ORDER] + [os.path.join(WORK, "ranking.mp4")]
        conf = [conform(p, os.path.join(WORK, f"c{i}.mkv")) for i, p in enumerate(parts)]
        out = assemble(conf, os.path.join(R, "WIZZCALL_5_spots_jeton_pirate.mp4"))
        print("FINAL", out, f"{duration(out):.1f}s")
