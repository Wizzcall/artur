"""~33 s trailer: hook -> beat-cut montage -> TOP 3 craziest moments
-> "who's number 1?" teaser (no spoiler) -> call to action.
Run after final.py (uses the spot base.mkv renders).
Usage: python3 fortnite_kit/trailer.py
"""
import math
import os
import wave

import numpy as np
from PIL import Image, ImageDraw

import final as Fi
import overlays as O
import spot_edit as SE
import make_music as MM

W, H, FPS, SR = Fi.W, Fi.H, Fi.FPS, Fi.SR
WORK = os.path.join(Fi.R, "work", "trailer")
run, paste, ease_back, ease = Fi.run, Fi.paste, Fi.ease_back, Fi.ease

# (key, global source time of the moment, lead-in, duration, title, subtitle)
TOP3 = [
    ("spot1_rubber_resort", 18.6, 0.7, 4.0, "#3", "3 COFFRES CASSÉS EN VOITURE"),
    ("spot5_the_chest", 42.4, 1.6, 5.0, "#2", "3 COFFRES EN 7 SECONDES"),
    ("spot3_loguetown", 94.8, 0.8, 5.0, "#1", "DOUBLE COFFRE ENTERRÉ"),
]


def clip(src, st, d, out, blur=False, audio=True):
    z = "(1.03+0.10*exp(-t*9))"
    vf = (f"fps={FPS},scale={W}:{H},setsar=1,scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame,"
          f"crop={W}:{H},eq=saturation=1.3:contrast=1.06" + (",boxblur=14:2,eq=brightness=-0.2" if blur else ""))
    af = f"aresample={SR},aformat=channel_layouts=stereo,volume={1.0 if audio else 0}"
    run(["ffmpeg", "-y", "-ss", f"{st:.3f}", "-t", f"{d:.3f}", "-i", src, "-vf", vf, "-af", af,
         "-frames:v", str(round(d * FPS)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
         "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest", out])
    return out


def build():
    os.makedirs(WORK, exist_ok=True)
    BEAT = 60 / MM.PRESETS["intro"]["bpm"]
    segs, marks, t = [], {}, 0.0

    def add(name, src, st, d, **kw):
        nonlocal t
        p = clip(src, st, d, os.path.join(WORK, f"{len(segs):02d}_{name}.mkv"), **kw)
        marks.setdefault(name, t)
        segs.append(p)
        t += d

    b = Fi.base
    # hook (blurred) + 8 fast beat cuts
    add("hook", b("spot3_loguetown"), 30.0, 2.6, blur=True, audio=False)
    pool = []
    for k in ["spot2_lantern_landing", "spot4_arlong_park", "spot3_loguetown", "spot1_rubber_resort"]:
        pool += [(b(k), max(0.0, x - 0.3)) for x in Fi.chest_moments(k, 2)]
    for i, (src, st) in enumerate(pool[:8]):
        add("montage", src, st, BEAT, audio=False)
    # TOP 3: rank card (blurred freeze) + the moment with game audio
    for k, g, lead, d, rank, sub in TOP3:
        te = Fi.edit_t(k, g)
        add(f"card{rank}", b(k), te - lead, 1.2, blur=True, audio=False)
        add(f"moment{rank}", b(k), te - lead, d)
    # teaser + call to action
    add("teaser", b("spot3_loguetown"), 60.0, 3.6, blur=True, audio=False)
    add("cta", b("spot5_the_chest"), 8.0, 4.4, blur=True, audio=False)
    D = t

    lst = os.path.join(WORK, "segs.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in segs)
    bgv = os.path.join(WORK, "bg.mkv")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", bgv])
    game = os.path.join(WORK, "game.wav")
    run(["ffmpeg", "-y", "-i", bgv, "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", game])

    # ---------------------------------------------------------------- overlays
    C = SE.Cache()
    rays = Fi.rays_img()
    hook1 = O.text_3d("J'AI TESTÉ LES 5 MEILLEURS SPOTS", 92, O.WHITE, (190, 215, 255), glow_color=O.CYAN)
    hook2 = O.text_3d("POUR FARMER LES COFFRES", 80, O.YELLOW, O.GOLD, glow_color=O.GOLD)
    top = O.text_3d("TOP 3 DES MOMENTS LES PLUS FOUS", 64, O.WHITE, (190, 215, 255), alt=True)
    ranks = {r: O.text_3d(r, 330, *(((O.YELLOW, O.GOLD) if r == "#1" else (O.WHITE, (185, 215, 255)))),
                          glow_color=O.GOLD if r == "#1" else O.CYAN) for *_, r, _ in TOP3}
    subs = {r: O.box_3d(s, None, rarity="legendary" if r == "#1" else "epic", size=58) for *_, r, s in TOP3}
    q1 = O.text_3d("MAIS QUEL SPOT", 130, O.WHITE, (190, 215, 255), glow_color=O.MAGENTA)
    q2 = O.text_3d("EST N°1 ?", 200, O.YELLOW, O.GOLD, tilt=-3, glow_color=O.GOLD)
    cta1 = O.box_3d("VIDÉO COMPLÈTE", "SUR LA CHAÎNE", rarity="legendary", size=74)
    cta2 = O.text_3d(Fi.CHANNEL, 180, O.WHITE, (185, 215, 255), tilt=-2, glow_color=O.CYAN)
    sub_btn = O.text_3d("ABONNE-TOI !", 110, O.RED, (170, 0, 30), glow_color=O.RED)
    impacts = [0.0, marks["montage"]] + [marks[f"card{r}"] for *_, r, _ in TOP3] + \
              [marks[f"moment{r}"] for *_, r, _ in TOP3] + [marks["teaser"], marks["teaser"] + 1.0, marks["cta"]]
    cut_times = [marks["montage"] + i * BEAT for i in range(8)]
    rng = np.random.default_rng(9)
    qmarks = [(rng.uniform(80, W - 80), rng.uniform(80, H - 80), rng.uniform(0.6, 1.4), rng.uniform(0, 3))
              for _ in range(14)]
    qm = O.text_3d("?", 140, O.YELLOW, O.GOLD, glow_color=O.GOLD)

    def shake(t):
        s = sum(24 * math.exp(-(t - a) * 9) for a in impacts if 0 <= t - a < 0.6)
        return s * math.sin(t * 90), s * math.cos(t * 77) * 0.6

    def fr(cv, t):
        sx, sy = shake(t)
        d = ImageDraw.Draw(cv)
        for a in impacts + cut_times:  # flash on every hit/cut
            dt = t - a
            if 0 <= dt < 0.14:
                d.rectangle([0, 0, W, H], fill=(255, 255, 255, int(160 * (1 - dt / 0.14))))
        if t < marks["montage"]:
            paste(cv, hook1, W / 2 + sx, H * 0.42 + sy, ease_back(t / 0.3))
            paste(cv, hook2, W / 2, H * 0.60, ease_back((t - 0.7) / 0.3))
        elif t < marks["card#3"]:
            dd = t - marks["montage"]
            paste(cv, top, W / 2, H - 90, ease_back(dd / 0.3) * (1 + 0.03 * math.sin(dd * 2 * math.pi / BEAT)))
        for _k, _g, _l, md, r, _s in TOP3:
            c0, m0 = marks[f"card{r}"], marks[f"moment{r}"]
            if c0 <= t < m0:
                dd = t - c0
                if r == "#1":
                    rr = C.get_or(("r", int(t * 12) % 180), lambda: rays.rotate((t * 12) % 180 * 2))
                    paste(cv, rr, W / 2, H / 2)
                paste(cv, ranks[r], W / 2 + sx, H * 0.45 + sy, 2.0 - ease_back(dd / 0.3))
            if m0 <= t < m0 + md:
                dd = t - m0
                paste(cv, ranks[r], 190, 170, 0.42 * ease_back(dd / 0.25))
                paste(cv, subs[r], W / 2, H - 140, ease_back((dd - 0.15) / 0.3), 1 - ease((dd - md + 0.3) / 0.3))
        if marks["teaser"] <= t < marks["cta"]:
            dd = t - marks["teaser"]
            for x, y, sc, ph in qmarks:
                k = ease_back((dd - ph * 0.25) / 0.3)
                if k > 0:
                    paste(cv, qm, x, y + 10 * math.sin(dd * 4 + ph), sc * k, 0.55)
            paste(cv, q1, W / 2 + sx, H * 0.36 + sy, ease_back(dd / 0.3))
            paste(cv, q2, W / 2 + sx, H * 0.60 + sy, 2.0 - ease_back((dd - 1.0) / 0.3))
        if t >= marks["cta"]:
            dd = t - marks["cta"]
            rr = C.get_or(("rb", int(t * 12) % 180), lambda: rays.rotate((t * 12) % 180 * 2))
            paste(cv, rr, W / 2, H * 0.45)
            paste(cv, cta1, W / 2, H * 0.25, ease_back(dd / 0.35))
            paste(cv, cta2, W / 2 + sx, H * 0.53 + sy, ease_back((dd - 0.3) / 0.35))
            paste(cv, sub_btn, W / 2, H * 0.80, ease_back((dd - 0.8) / 0.35) * (1 + 0.05 * math.sin(dd * 6)))

    v = Fi.render_section(bgv, D, fr, os.path.join(WORK, "trailer_v.mp4"))

    # ---------------------------------------------------------------- audio
    imp, wh, ding, coin = SE._sfx_impact(), SE._sfx_whoosh(), SE._sfx_ding(), SE._sfx_coins()
    riser, pop = SE._sfx_riser(1.2), SE._sfx_pop()
    sfx = [(imp, 0.0, 1.6), (pop, 0.75, 1.0), (riser, marks["montage"] - 1.2, 1.0), (imp, marks["montage"], 1.6)]
    sfx += [(wh, c - 0.1, 0.6) for c in cut_times[1:]]
    for *_, r, _s in TOP3:
        sfx += [(wh, marks[f"card{r}"] - 0.15, 1.1), (imp, marks[f"card{r}"], 1.8), (imp, marks[f"moment{r}"], 0.9)]
    sfx += [(wh, marks["teaser"] - 0.1, 1.0), (imp, marks["teaser"], 1.2), (riser, marks["teaser"] - 0.2, 0.8),
            (imp, marks["teaser"] + 1.0, 1.8), (wh, marks["cta"] - 0.15, 1.1), (imp, marks["cta"], 1.8),
            (coin, marks["cta"] + 0.35, 1.2), (ding, marks["cta"] + 0.8, 1.2)]
    mus = Fi.music_bed("intro", D, os.path.join(WORK, "music.wav"), sfx, drop_at=marks["montage"], gain=0.7)
    m = SE._read_wav(mus)
    g = SE._read_wav(game)
    n = min(len(m), len(g))
    duck = np.ones(n)
    for *_, r, _s in TOP3:  # music down under each moment so the game audio speaks
        a, bb = int(marks[f"moment{r}"] * SR), int((marks[f"moment{r}"] + 4.6) * SR)
        duck[a:bb] = 0.5
    k = int(0.1 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same")
    mix = m[:n] * duck[:, None] + g[:n] * 1.3
    mix = np.tanh(mix / (np.max(np.abs(mix)) + 1e-9) * 1.3) / math.tanh(1.3) * 0.93
    wav = os.path.join(WORK, "mix.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    out = os.path.join(Fi.R, "download", "WIZZCALL_TRAILER.mp4")
    run(["ffmpeg", "-y", "-i", v, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow",
         "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
    # vertical 9:16 version for Shorts / TikTok (blurred fill + centred 16:9)
    vert = os.path.join(Fi.R, "download", "WIZZCALL_TRAILER_vertical.mp4")
    run(["ffmpeg", "-y", "-i", out, "-filter_complex",
         "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2,eq=brightness=-0.15[bg];"
         "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-c:a", "copy",
         "-movflags", "+faststart", vert])
    print("TRAILER", out, f"{D:.1f}s", marks)
    return out


if __name__ == "__main__":
    build()
