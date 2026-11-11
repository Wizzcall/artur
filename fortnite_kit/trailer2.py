"""Trailer v2 — no music, game audio + SFX only.
  Fortnite-style intro (storm, lightning, rarity colour flip, "WOW!")
  -> hook -> slow-mo elimination at the chest -> slow-mo dance that opens
  the rock -> quick hype cut -> end card: the video thumbnail framed by a
  glowing rectangle ("REGARDE LA VIDÉO").
Also writes the thumbnail itself (renders/download/WIZZCALL_MINIATURE.png).
Usage: python3 fortnite_kit/trailer2.py
"""
import math
import os
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

import final as Fi
import overlays as O
import spot_edit as SE

W, H, FPS, SR = Fi.W, Fi.H, Fi.FPS, Fi.SR
WORK = os.path.join(Fi.R, "work", "trailer2")
DL = os.path.join(Fi.R, "download")
run, paste, ease_back, ease = Fi.run, Fi.paste, Fi.ease_back, Fi.ease


# ----------------------------------------------------------------- media
def piece(src, st, d_src, speed, out, blur=False, smooth=False, gain=1.0):
    """Cut [st, st+d_src] from src, play it at `speed` (0.4 = slow motion)."""
    d_out = d_src / speed
    mi = ",minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1" if smooth and speed < 1 else ""
    vf = (f"trim=start={st:.3f}:duration={d_src:.3f},setpts=(PTS-STARTPTS)/{speed}{mi},fps={FPS},"
          f"scale={W}:{H}:flags=lanczos,setsar=1,eq=saturation=1.3:contrast=1.07"
          + (",boxblur=14:2,eq=brightness=-0.22" if blur else ""))
    tempo, s = [], speed
    while s < 0.5 - 1e-9:
        tempo.append("atempo=0.5")
        s /= 0.5
    if abs(s - 1) > 1e-6:
        tempo.append(f"atempo={s:.5f}")
    af = ",".join([f"atrim=start={st:.3f}:duration={d_src:.3f}", "asetpts=PTS-STARTPTS"] + tempo +
                  [f"aresample={SR}", "aformat=channel_layouts=stereo", f"volume={gain}", "apad",
                   f"atrim=duration={d_out:.3f}"])
    run(["ffmpeg", "-y", "-i", src, "-vf", vf, "-af", af, "-frames:v", str(round(d_out * FPS)),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", out])
    return out, d_out


def still_bg(img, d, out):
    p = out + ".png"
    img.convert("RGB").save(p)
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", p, "-f", "lavfi",
         "-t", f"{d:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo", "-vf", f"scale={W}:{H},setsar=1,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-c:a", "pcm_s16le", "-shortest", out])
    return out, d


# ----------------------------------------------------------------- sounds (no music)
def sfx_wow():
    """Synthesised vocal-like 'wooOOW' (formant glide u -> a -> u)."""
    d = 1.1
    n = int(d * SR)
    t = np.arange(n) / SR
    x = t / d
    f0 = 170 + 110 * np.sin(np.pi * np.clip(x * 1.15, 0, 1)) - 40 * x
    ph = 2 * np.pi * np.cumsum(f0 * (1 + 0.012 * np.sin(2 * np.pi * 5.5 * t))) / SR
    src = sum(np.sin(k * ph) / k for k in range(1, 40))
    shape = np.sin(np.pi * np.clip(x * 1.05, 0, 1)) ** 0.8
    F1 = 320 + 450 * np.sin(np.pi * x) ** 1.5
    F2 = 800 + 450 * np.sin(np.pi * x) ** 1.5
    y = np.zeros(n)
    for F, bw, g in ((F1, 90, 1.0), (F2, 120, 0.6), (2600 + 0 * x, 200, 0.15)):
        # time-varying 2-pole resonator
        out = np.zeros(n)
        y1 = y2 = 0.0
        for i in range(n):
            r = math.exp(-math.pi * bw / SR)
            c = 2 * r * math.cos(2 * math.pi * F[i] / SR)
            v = src[i] + c * y1 - r * r * y2
            out[i] = v
            y2, y1 = y1, v
        y += out / (np.max(np.abs(out)) + 1e-9) * g
    y = y * shape
    return y / (np.max(np.abs(y)) + 1e-9) * 0.8


def sfx_boom(d=2.2):
    """Cinematic slow-motion hit: sub drop + noise swell tail."""
    n = int(d * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(38 + 90 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.6)
    rng = np.random.default_rng(21)
    nz = np.convolve(rng.uniform(-1, 1, n), np.ones(40) / 40, mode="same") * np.exp(-t * 2.2) * 2.0
    return np.tanh((sub * 1.2 + nz) * 1.4) * 0.8


def sfx_thunder():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(23)
    crack = rng.uniform(-1, 1, n) * np.exp(-t * 18)
    rumble = np.convolve(rng.uniform(-1, 1, n), np.ones(120) / 120, mode="same") * np.exp(-t * 1.8) * 6
    return np.tanh((crack * 0.8 + rumble) * 1.2) * 0.7


def sfx_shimmer(d=1.2):
    n = int(d * SR)
    t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * f * t + k) for k, f in enumerate((1568, 2093, 2637, 3136, 4186)))
    return y * np.exp(-t * 2.5) * (1 - np.exp(-t * 40)) * 0.12


# ----------------------------------------------------------------- thumbnail
def make_thumbnail():
    key, g = "spot3_loguetown", 94.8
    te = Fi.edit_t(key, g)
    p = os.path.join(WORK, "thumb_src.png")
    run(["ffmpeg", "-y", "-ss", f"{te + 0.25:.3f}", "-i", Fi.base(key), "-frames:v", "1", p])
    bg = Image.open(p).convert("RGB").resize((W, H))
    bg = ImageEnhance.Color(bg).enhance(1.5)
    bg = ImageEnhance.Contrast(bg).enhance(1.15).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(W // 2):  # dark gradient on the right for the text
        a = int(200 * (i / (W / 2)) ** 1.4)
        d.line([(W // 2 + i, 0), (W // 2 + i, H)], fill=(15, 5, 45, a))
    bg.alpha_composite(ov)
    bg.alpha_composite(Fi.rays_img(1300).rotate(10), (W - 1150, -150))
    t1 = O.text_3d("12 COFFRES", 210, O.YELLOW, O.GOLD, tilt=4, glow_color=O.GOLD)
    t2 = O.text_3d("EN 3:30 ?!", 170, O.WHITE, (190, 215, 255), tilt=4, glow_color=O.CYAN)
    t3 = O.box_3d("MEILLEUR SPOT", "JETON PIRATE", rarity="epic", size=70)
    paste(bg, t1, W * 0.70, H * 0.26)
    paste(bg, t2, W * 0.72, H * 0.50)
    paste(bg, t3, W * 0.72, H * 0.78)
    paste(bg, O.chest_icon(300, open_=True), W * 0.40, H * 0.80)
    paste(bg, O.circular_timer(210, 210, size=260), W * 0.12, H * 0.20)
    arr = O.arrow_3d(300, (255, 60, 60), angle=200)
    paste(bg, arr, W * 0.42, H * 0.42)
    bg = bg.convert("RGB")
    os.makedirs(DL, exist_ok=True)
    bg.resize((1280, 720), Image.LANCZOS).save(os.path.join(DL, "WIZZCALL_MINIATURE.png"))
    return bg


# ----------------------------------------------------------------- build
def build():
    os.makedirs(WORK, exist_ok=True)
    thumb = make_thumbnail()
    s5a = Fi.norm("spot5_the_chest", "clip3_part1_0-30s.mp4")
    s5b = Fi.norm("spot5_the_chest", "clip3_part2_30-60s.mp4")
    s2 = Fi.norm("spot2_lantern_landing", "part2.mp4")
    b = Fi.base

    segs, marks, t = [], {}, 0.0

    def add(name, res):
        nonlocal t
        p, d = res
        marks.setdefault(name, t)
        segs.append(p)
        t += d

    P = lambda n: os.path.join(WORK, f"{len(segs):02d}_{n}.mkv")
    # 1. intro (storm background built from blurred gameplay)
    add("intro", piece(b("spot3_loguetown"), 60.0, 5.2, 1.0, P("intro"), blur=True, gain=0))
    # 2. hook: 3 hard cuts
    for k in ("spot1_rubber_resort", "spot4_arlong_park", "spot3_loguetown"):
        add("hook", piece(b(k), Fi.chest_moments(k, 2)[-1] - 0.4, 0.8, 1.0, P("hook"), gain=0.8))
    # 3. elimination at the chest (spot 2, part 2)
    add("kill", piece(s2, 5.0, 1.6, 1.0, P("kill_a")))
    add("kill_slow", piece(s2, 6.6, 1.4, 0.35, P("kill_b"), smooth=True))
    add("kill_end", piece(s2, 8.0, 2.3, 1.0, P("kill_c")))
    # 4. dance in front of the rock -> it opens (spot 5)
    add("dance", piece(s5a, 25.9, 2.4, 1.0, P("dance_a")))
    add("dance_slow", piece(s5a, 28.3, 1.7, 0.4, P("dance_b"), smooth=True))
    add("dance_chest", piece(s5b, 2.0, 0.9, 0.5, P("dance_c"), smooth=True))
    add("dance_end", piece(s5b, 2.9, 1.2, 1.0, P("dance_d")))
    # 5. one last hype cut
    add("hype", piece(b("spot3_loguetown"), Fi.edit_t("spot3_loguetown", 94.8) - 0.5, 2.4, 1.0, P("hype")))
    # 6. end card on the blurred thumbnail
    blurred = thumb.filter(ImageFilter.GaussianBlur(18))
    blurred = ImageEnhance.Brightness(blurred).enhance(0.55)
    add("end", still_bg(blurred, 6.0, P("end")))
    D = t

    lst = os.path.join(WORK, "segs.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in segs)
    bgv = os.path.join(WORK, "bg.mkv")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", bgv])
    game = os.path.join(WORK, "game.wav")
    run(["ffmpeg", "-y", "-i", bgv, "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", game])

    # ------------------------------------------------------------- overlays
    C = SE.Cache()
    rays = Fi.rays_img()
    rarities = [((200, 200, 200), (130, 130, 130)), (O.GREEN, (30, 160, 70)), (O.CYAN, O.BLUE),
                ((220, 140, 255), O.PURPLE), (O.YELLOW, O.GOLD)]
    names = [O.text_3d(Fi.CHANNEL, 200, top, bot, tilt=-3, glow_color=top) for top, bot in rarities]
    wow = O.text_3d("WOW !", 300, O.YELLOW, O.GOLD, tilt=-6, glow_color=O.GOLD)
    pres = O.box_3d("5 SPOTS • JETON PIRATE", None, rarity="epic", size=62)
    hook = O.text_3d("J'AI TESTÉ LES 5 MEILLEURS SPOTS...", 84, O.WHITE, (190, 215, 255), glow_color=O.CYAN)
    kill1 = O.box_3d("PREMIER SANG", "PILE SUR LE COFFRE", rarity="legendary", size=66)
    slow = O.text_3d("RALENTI", 60, O.WHITE, (200, 210, 255), alt=True, glow_color=O.BLUE)
    dance1 = O.text_3d("JE DANSE DEVANT LE ROCHER...", 92, O.WHITE, (190, 215, 255), glow_color=O.MAGENTA)
    dance2 = O.text_3d("ET IL S'OUVRE ?!", 170, O.YELLOW, O.GOLD, tilt=-4, glow_color=O.GOLD)
    rare = O.box_3d("COFFRE RARE CACHÉ", None, rarity="epic", size=62)
    hype = O.text_3d("12 COFFRES ?!", 200, O.YELLOW, O.GOLD, tilt=-4, glow_color=O.GOLD)
    look = O.text_3d("REGARDE LA VIDÉO !", 110, O.WHITE, (190, 215, 255), glow_color=O.CYAN)
    clic = O.box_3d("CLIQUE ICI", f"CHAÎNE {Fi.CHANNEL}", rarity="legendary", size=56)
    arr_l = O.arrow_3d(220, O.YELLOW, angle=0)
    arr_r = O.arrow_3d(220, O.YELLOW, angle=180)
    tw, th = 1100, 619
    thumb_s = thumb.resize((tw, th), Image.LANCZOS).convert("RGBA")
    hits = [0.0, 2.4, marks["hook"], marks["hook"] + 0.8, marks["hook"] + 1.6, marks["kill_slow"],
            marks["kill_end"] + 1.8, marks["dance_slow"] + 2.6, marks["dance_chest"], marks["hype"], marks["end"]]
    rng = np.random.default_rng(3)
    bolts = []
    for k in range(3):  # lightning bolts for the intro
        x = rng.uniform(300, W - 300)
        pts, y = [(x, 0)], 0
        while y < H * 0.75:
            y += rng.uniform(40, 90)
            x += rng.uniform(-70, 70)
            pts.append((x, y))
        bolts.append((0.25 + k * 0.55, pts))

    def shake(t):
        s = sum(26 * math.exp(-(t - a) * 9) for a in hits if 0 <= t - a < 0.6)
        return s * math.sin(t * 90), s * math.cos(t * 77) * 0.6

    def letterbox(d, k):
        h = int(110 * k)
        if h > 0:
            d.rectangle([0, 0, W, h], fill=(0, 0, 0, 255))
            d.rectangle([0, H - h, W, H], fill=(0, 0, 0, 255))

    def fr(cv, t):
        sx, sy = shake(t)
        d = ImageDraw.Draw(cv)
        # ---- intro: storm + lightning + rarity flip + WOW
        if t < marks["hook"]:
            d.rectangle([0, 0, W, H], fill=(40, 10, 80, int(150 * (1 - ease((t - 4.9) / 0.3)))))
            R = 1500 - 900 * ease(t / 2.4)  # storm circle closing
            d.ellipse([W / 2 - R, H / 2 - R, W / 2 + R, H / 2 + R], outline=(200, 90, 255, 200), width=26)
            for t0, pts in bolts:
                if 0 <= t - t0 < 0.22:
                    a = int(255 * (1 - (t - t0) / 0.22))
                    d.rectangle([0, 0, W, H], fill=(230, 220, 255, int(a * 0.35)))
                    d.line(pts, fill=(255, 255, 255, a), width=9)
                    d.line(pts, fill=(200, 160, 255, a // 2), width=26)
            if t >= 1.0:
                k = min(4, int((t - 1.0) / 0.28))
                paste(cv, names[k], W / 2 + sx, H * (0.40 - 0.10 * ease((t - 2.2) / 0.3)) + sy, ease_back((t - 1.0) / 0.3) * (1.06 if k == 4 else 1))
            if t >= 2.4:
                rr = C.get_or(("r", int(t * 14) % 180), lambda: rays.rotate((t * 14) % 180 * 2))
                paste(cv, rr, W / 2, H * 0.62, 0.9)
                paste(cv, wow, W / 2 + sx, H * 0.70 + sy, 2.2 - 1.2 * ease_back((t - 2.4) / 0.3))
                paste(cv, pres, W / 2, H * 0.10, ease_back((t - 3.0) / 0.3))
            if 2.4 <= t < 2.55:
                d.rectangle([0, 0, W, H], fill=(255, 255, 255, int(220 * (1 - (t - 2.4) / 0.15))))
        # ---- hook
        if marks["hook"] <= t < marks["kill"]:
            dd = t - marks["hook"]
            paste(cv, hook, W / 2 + sx, H * 0.82 + sy, ease_back(dd / 0.25))
        # ---- elimination
        if marks["kill"] <= t < marks["dance"]:
            dd = t - marks["kill"]
            sl0, sl1 = marks["kill_slow"], marks["kill_end"]
            letterbox(d, ease((t - sl0 + 0.3) / 0.3) * (1 - ease((t - sl1) / 0.3)))
            if sl0 <= t < sl1:
                paste(cv, slow, W - 200, 170, ease_back((t - sl0) / 0.3))
            if t >= marks["kill_end"] - 0.2:
                e = t - marks["kill_end"] + 0.2
                paste(cv, kill1, W / 2, H - 170, ease_back(e / 0.3), 1 - ease((t - marks["dance"] + 0.3) / 0.3))
        # ---- dance -> rock opens
        if marks["dance"] <= t < marks["hype"]:
            dd = t - marks["dance"]
            sl0, sl1 = marks["dance_slow"], marks["dance_end"]
            letterbox(d, ease((t - sl0 + 0.3) / 0.3) * (1 - ease((t - sl1) / 0.3)))
            if dd < marks["dance_slow"] - marks["dance"] + 1.5:
                paste(cv, dance1, W / 2, H * 0.80, ease_back(dd / 0.3),
                      1 - ease((dd - (marks["dance_slow"] - marks["dance"]) - 1.2) / 0.3))
            if sl0 <= t < sl1:
                paste(cv, slow, W - 200, 170, ease_back((t - sl0) / 0.3))
            k0 = marks["dance_slow"] + 2.6
            if t >= k0:
                paste(cv, dance2, W / 2 + sx, H * 0.40 + sy, 2.0 - ease_back((t - k0) / 0.3))
            if t >= marks["dance_chest"]:
                paste(cv, rare, W / 2, H - 170, ease_back((t - marks["dance_chest"]) / 0.3))
        # ---- hype
        if marks["hype"] <= t < marks["end"]:
            dd = t - marks["hype"]
            paste(cv, hype, W / 2 + sx, H * 0.45 + sy, 2.0 - ease_back(dd / 0.3))
        # ---- end card: thumbnail in a glowing rectangle
        if t >= marks["end"]:
            dd = t - marks["end"]
            k = ease_back(dd / 0.45)
            cx, cy = W / 2, H * 0.47
            if k > 0.01:
                sw, sh = tw * k, th * k
                pulse = 0.5 + 0.5 * math.sin(dd * 6)
                for gw, ga in ((46, 50), (30, 90), (16, 255)):
                    col = (255, 220 - int(60 * pulse), 40, int(ga * (0.7 + 0.3 * pulse)))
                    d.rounded_rectangle([cx - sw / 2 - gw, cy - sh / 2 - gw, cx + sw / 2 + gw, cy + sh / 2 + gw],
                                        28, outline=col, width=10)
                paste(cv, thumb_s, cx, cy, k)
                # animated corner dashes running around the frame
                per = 2 * (sw + sh) + 160
                for j in range(10):
                    pos = (dd * 900 + j * per / 10) % per
                    x0, y0 = cx - sw / 2 - 40, cy - sh / 2 - 40
                    w2, h2 = sw + 80, sh + 80
                    if pos < w2:
                        p1 = (x0 + pos, y0)
                    elif pos < w2 + h2:
                        p1 = (x0 + w2, y0 + pos - w2)
                    elif pos < 2 * w2 + h2:
                        p1 = (x0 + w2 - (pos - w2 - h2), y0 + h2)
                    else:
                        p1 = (x0, y0 + h2 - (pos - 2 * w2 - h2))
                    d.ellipse([p1[0] - 9, p1[1] - 9, p1[0] + 9, p1[1] + 9], fill=(255, 255, 255, 230))
            paste(cv, look, W / 2, 75, ease_back((dd - 0.3) / 0.3))
            bob = 25 * math.sin(dd * 7)
            paste(cv, arr_l, cx - tw / 2 - 210 + bob, cy, ease_back((dd - 0.6) / 0.3))
            paste(cv, arr_r, cx + tw / 2 + 210 - bob, cy, ease_back((dd - 0.6) / 0.3))
            paste(cv, clic, W / 2, H - 85, ease_back((dd - 0.9) / 0.3) * (1 + 0.04 * math.sin(dd * 6)))

    v = Fi.render_section(bgv, D, fr, os.path.join(WORK, "trailer_v.mp4"))

    # ------------------------------------------------------------- audio: game + SFX, no music
    g = SE._read_wav(game)
    N = len(g)
    mix = g * 1.2
    imp, wh, coin, ding = SE._sfx_impact(), SE._sfx_whoosh(), SE._sfx_coins(), SE._sfx_ding()
    boom, thunder, shim, wow_s = sfx_boom(), sfx_thunder(), sfx_shimmer(), sfx_wow()
    riser, pop = SE._sfx_riser(2.0), SE._sfx_pop()

    def put(sig, at, gain):
        i = int(at * SR)
        if 0 <= i < N:
            j = min(N, i + len(sig))
            mix[i:j] += (sig[:j - i] * gain)[:, None]

    for t0, _ in bolts:
        put(thunder, t0, 1.0)
    for k in range(5):
        put(pop, 1.0 + k * 0.28, 0.9)
        put(shim, 1.0 + k * 0.28, 0.6)
    put(riser, 0.5, 0.8)
    put(imp, 2.4, 1.8)
    put(wow_s, 2.42, 1.4)
    put(coin, 2.6, 1.0)
    put(wh, 2.9, 0.9)
    for k in range(3):
        put(wh, marks["hook"] + k * 0.8 - 0.12, 0.9)
        put(imp, marks["hook"] + k * 0.8, 1.2)
    put(boom, marks["kill_slow"], 1.5)
    put(wh, marks["kill_end"] - 0.15, 1.0)
    put(imp, marks["kill_end"] + 1.8, 1.0)
    put(ding, marks["kill_end"] + 1.8, 1.2)
    put(riser, marks["dance_slow"] - 1.0, 0.9)
    put(boom, marks["dance_slow"], 1.5)
    put(imp, marks["dance_slow"] + 2.6, 1.8)
    put(wow_s, marks["dance_slow"] + 2.65, 1.1)
    put(shim, marks["dance_chest"], 1.0)
    put(ding, marks["dance_chest"] + 0.6, 1.3)
    put(coin, marks["dance_chest"] + 0.7, 1.2)
    put(wh, marks["hype"] - 0.15, 1.0)
    put(imp, marks["hype"], 1.8)
    put(coin, marks["hype"] + 0.2, 1.2)
    put(wh, marks["end"] - 0.15, 1.1)
    put(imp, marks["end"], 1.6)
    put(shim, marks["end"] + 0.3, 1.0)
    put(pop, marks["end"] + 0.9, 1.0)
    fo = int(0.6 * SR)
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    mix = np.tanh(mix / (np.max(np.abs(mix)) + 1e-9) * 1.4) / math.tanh(1.4) * 0.93
    wav = os.path.join(WORK, "mix.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    out = os.path.join(DL, "WIZZCALL_TRAILER_V2.mp4")
    run(["ffmpeg", "-y", "-i", v, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
    vert = os.path.join(DL, "WIZZCALL_TRAILER_V2_vertical.mp4")
    run(["ffmpeg", "-y", "-i", out, "-filter_complex",
         "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2,eq=brightness=-0.15[bg];"
         "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-c:a", "copy",
         "-movflags", "+faststart", vert])
    print("TRAILER2", out, f"{D:.1f}s", {k: round(v_, 2) for k, v_ in marks.items()})


if __name__ == "__main__":
    build()
