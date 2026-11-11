"""Render one "spot test" section of the video from raw clips + a spec.

Pipeline
  1. Cut the source into pieces (with speed ramps), colour-correct (HDR->SDR
     when needed), normalise to 1920x1080 @30 fps -> base.mkv (+ game audio).
  2. Render the overlay layer frame by frame in Python (title card, 3:30 neon
     chrono, chest counter synced to the exact frame of every opening, 3D rings,
     arrows, callout boxes, speed badge, result card) and composite it in ffmpeg.
  3. Mix audio in numpy: game audio + section music (ducked under the action,
     drop aligned to the landing) + SFX (chest "ding", whooshes, impacts).

All times in a spec are GLOBAL source times (seconds since the start of the
first clip of that spot); `edit` times are computed from the speed ramps.
"""
import math
import os
import subprocess
import wave
from bisect import bisect_right

import numpy as np
from PIL import Image

import overlays as O
import make_music as MM

W, H, FPS = 1920, 1080, 30
SR = 48000
CHRONO = 210.0  # 3:30
HERE = os.path.dirname(os.path.abspath(__file__))

HDR_VF = ("zscale=t=linear:npl=70,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:param=0.6:desat=0,"
          "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,"
          "colorlevels=rimin=0.16:gimin=0.16:bimin=0.16:rimax=0.95:gimax=0.95:bimax=0.95,eq=saturation=1.2")
SDR_VF = "eq=saturation=1.12:contrast=1.04"


def run(cmd, **kw):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-3000:])
    return r


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


# ----------------------------------------------------------------- timeline
class Timeline:
    """Maps edit time <-> global source time through the speed ramps."""

    def __init__(self, spec):
        self.clips = spec["clips"]  # [(path, global_offset, duration)]
        self.pieces = []            # dicts: edit0, frames, g0, g1, speed, clip, local0
        e = 0
        for g0, g1, speed in spec["segments"]:
            for path, off, dur in self.clips:  # split at clip boundaries
                a, b = max(g0, off), min(g1, off + dur)
                if b - a < 1e-3:
                    continue
                frames = max(1, round((b - a) / speed * FPS))
                self.pieces.append(dict(edit0=e, frames=frames, g0=a, g1=b, speed=speed,
                                        clip=path, local0=a - off))
                e += frames
        self.frames = e
        self.duration = e / FPS
        self.starts = [p["edit0"] for p in self.pieces]

    def g_at(self, t):
        f = t * FPS
        i = max(0, bisect_right(self.starts, f) - 1)
        p = self.pieces[i]
        k = min(max(f - p["edit0"], 0), p["frames"])
        return p["g0"] + k / p["frames"] * (p["g1"] - p["g0"]), p

    def edit_at(self, g):
        for p in self.pieces:
            if p["g0"] - 1e-6 <= g <= p["g1"] + 1e-6:
                return (p["edit0"] + (g - p["g0"]) / (p["g1"] - p["g0"]) * p["frames"]) / FPS
        # g falls in a cut gap: snap to next piece start
        for p in self.pieces:
            if p["g0"] > g:
                return p["edit0"] / FPS
        return self.duration


# ----------------------------------------------------------------- step 1
def render_base(spec, tl, work):
    pieces = []
    for i, p in enumerate(tl.pieces):
        import hashlib
        key = hashlib.md5(repr((p["clip"], round(p["local0"], 4), p["frames"], p["speed"],
                                spec.get("hdr"), HDR_VF, SDR_VF)).encode()).hexdigest()[:10]
        out = os.path.join(work, f"piece_{i:03d}_{key}.mkv")
        pieces.append(out)
        if os.path.exists(out):
            continue
        sp = p["speed"]
        src_dur = p["frames"] / FPS * sp
        a, b = p["local0"], p["local0"] + src_dur
        is_img = p["clip"].lower().endswith((".jpg", ".jpeg", ".png"))
        # cut on the file's own timestamps (video may start later than audio in
        # some recordings): trim both streams on the same clock, and let fps
        # pad the head with the first frame if the video starts after `a`.
        grade = "" if is_img else (HDR_VF if spec.get("hdr") else SDR_VF) + ","
        vf = (f"trim=start={a:.4f}:end={b + 0.1:.4f},setpts=(PTS-{a:.4f}/TB)/{sp},"
              f"fps={FPS}:start_time=0,{grade}scale={W}:{H}:flags=lanczos,setsar=1")
        tempo, s = [], sp
        while s > 2.0 + 1e-9:
            tempo.append("atempo=2.0")
            s /= 2.0
        if abs(s - 1) > 1e-6:
            tempo.append(f"atempo={s:.6f}")
        gain = 1.0 if sp == 1 else 0.22
        af = ",".join([f"atrim=start={a:.4f}:end={b + 0.1:.4f}", "asetpts=PTS-STARTPTS"] + tempo +
                      [f"volume={gain}", f"aresample={SR}", f"apad", f"atrim=duration={p['frames'] / FPS:.6f}"])
        if is_img:
            inputs = ["-loop", "1", "-framerate", str(FPS), "-t", f"{b + 0.2:.4f}", "-i", p["clip"],
                      "-f", "lavfi", "-t", f"{b + 0.2:.4f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
            maps = ["-map", "0:v", "-map", "1:a"]
        else:
            inputs, maps = ["-i", p["clip"]], []
        run(["ffmpeg", "-y", *inputs, *maps,
             "-vf", vf, "-af", af, "-frames:v", str(p["frames"]), "-ac", "2",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p",
             "-c:a", "pcm_s16le", out])
    lst = os.path.join(work, "pieces.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(x)}'\n" for x in pieces)
    base = os.path.join(work, "base.mkv")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", base])
    wav = os.path.join(work, "game.wav")
    run(["ffmpeg", "-y", "-i", base, "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", wav])
    return base, wav


# ----------------------------------------------------------------- step 2
class Cache(dict):
    def get_or(self, key, fn):
        if key not in self:
            if len(self) > 600:
                self.clear()
            self[key] = fn()
        return self[key]


def paste_center(canvas, img, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.split()[3].point(lambda v: int(v * alpha)))
    x, y = int(cx - img.width / 2), int(cy - img.height / 2)
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(img.width, canvas.width - x), min(img.height, canvas.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    canvas.alpha_composite(img, (max(0, x), max(0, y)), (sx0, sy0, sx1, sy1))


def fmt_mmss(s):
    s = max(0, int(round(s)))
    return f"{s // 60}:{s % 60:02d}"


def render_overlays(spec, tl, base, out_video, work, end_dur=6.0):
    t0 = spec["t0"]
    t0_edit = tl.edit_at(t0)
    events = sorted(spec["events"])
    ev_edit = [tl.edit_at(g) for g, *_ in events]
    texts = [(tl.edit_at(g), txt, sub, rar, dur) for g, txt, sub, rar, dur in spec["texts"]]
    rages = [(tl.edit_at(g), txt, dur) for g, txt, dur in spec.get("rages", [])]
    total = tl.duration + end_dur
    nframes = int(round(total * FPS))
    base_end = tl.duration
    last_g = tl.pieces[-1]["g1"]
    gaps = spec.get("gaps", [])  # unfilmed stretches: the chrono is paused there

    def rt(g):  # run time (filmed farm time since landing) at global time g
        r = g - t0
        for a, b in gaps:
            r -= max(0.0, min(g, b) - max(a, t0))
        return r

    over = rt(last_g) > CHRONO                   # footage continues after 3:30
    limit_edit = None
    if over:
        lo, hi = t0, last_g
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if rt(mid) < CHRONO else (lo, mid)
        limit_edit = tl.edit_at(hi)
    run_end = min(rt(last_g), CHRONO)
    # openings after 3:30 are shown as "hors chrono" bonus, never counted
    events = [(g, x, y, kind if rt(g) <= CHRONO else "bonus") for g, x, y, kind in events]
    counted = [te for (g, *_), te in zip(events, ev_edit) if rt(g) <= CHRONO]
    final_count = len(counted)
    n_bonus = len(events) - final_count

    C = Cache()
    title = O.box_3d(f"SPOT {spec['number']} : {spec['name']}", "CHRONO 3:30", rarity="epic", size=62)
    go_txt = O.text_3d("C'EST PARTI !", 120, O.GREEN, (20, 160, 70), tilt=-3, glow_color=O.GREEN)
    arrow = O.arrow_3d(230, O.YELLOW, angle=-90)

    cmd = ["ffmpeg", "-y", "-i", base,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-filter_complex",
           f"[0:v]tpad=stop_mode=clone:stop_duration={end_dur},"
           f"boxblur=10:2:enable='gte(t,{base_end:.3f})',"
           f"eq=brightness=-0.12:enable='gte(t,{base_end:.3f})'[b];[b][1:v]overlay=format=auto,format=yuv420p[v]",
           "-map", "[v]", "-frames:v", str(nframes),
           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-an", out_video]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    for fi in range(nframes):
        t = fi / FPS
        cv = blank.copy()
        in_end = t >= base_end
        g, piece = tl.g_at(min(t, base_end - 1e-6))
        run_t = rt(g)

        # --- title card (slides in, holds, slides out)
        if t < 3.4:
            k_in, k_out = ease_out_back((t - 0.15) / 0.45), ease_out((t - 2.9) / 0.4)
            x = -700 + (W / 2 + 700) * k_in + (W + 800) * k_out
            paste_center(cv, title, x, 200)

        # --- air phase: 3D arrow + ring on the target
        if run_t < 0 and t > 0.4:
            ax, ay = spec.get("target", (W / 2, H * 0.62))
            ring = C.get_or(("ring", round(t * 10)), lambda: O.ring_3d(130, O.CYAN, t))
            paste_center(cv, ring, ax, ay)
            bob = 18 * math.sin(t * 2 * math.pi * 1.6)
            paste_center(cv, arrow, ax, ay - 210 + bob)

        # --- "C'EST PARTI" at landing
        dt = t - t0_edit
        if 0 <= dt < 1.4:
            paste_center(cv, go_txt, W / 2, H * 0.40, ease_out_back(dt / 0.3), 1 - ease_out((dt - 1.1) / 0.3))

        # --- chrono + counter (after landing)
        if run_t >= 0 or in_end:
            k = ease_out_back(dt / 0.35) if dt < 0.4 else 1
            rem = max(0.0, CHRONO - (run_end if in_end else min(run_t, CHRONO)))
            timer = C.get_or(("timer", round(rem * 10)), lambda: O.circular_timer(rem, CHRONO))
            if not in_end:
                paste_center(cv, timer, W - 160 + (1 - k) * 400, 165)
            n = sum(1 for e in counted if e <= t)
            last = max([e for e in counted if e <= t], default=-9)
            q = round((t - last) / 0.6 * 20)
            q = q if 0 < q < 20 else 0
            cnt = C.get_or(("cnt", n, q), lambda: O.chest_counter(n, pop=q / 20))
            if not in_end:
                paste_center(cv, cnt, 290 - (1 - k) * 600, H - 140)

        # --- event highlight ring on the chest
        for (g_e, x, y, kind), te in zip(events, ev_edit):
            d = t - te
            if -0.25 < d < 1.0 and not in_end:
                ring = C.get_or(("ering", kind, round(d * 15)),
                                lambda: O.ring_3d(110, O.YELLOW if kind == "chest" else O.CYAN, d * 2))
                if kind == "bonus":
                    ring = C.get_or(("bring", round(d * 15)), lambda: O.ring_3d(110, O.MAGENTA, d * 2))
                paste_center(cv, ring, x, y + 40, 0.7 + 0.3 * ease_out_back((d + 0.25) / 0.3),
                             1 - ease_out((d - 0.75) / 0.25))
                lab = C.get_or(("elab", kind), lambda: O.text_3d(
                    {"chest": "+1 COFFRE", "loot": "+1 BUTIN", "bonus": "BONUS HORS CHRONO"}[kind],
                    64 if kind != "bonus" else 54,
                    {"chest": O.YELLOW, "loot": O.CYAN, "bonus": (255, 170, 255)}[kind],
                    {"chest": O.GOLD, "loot": O.BLUE, "bonus": O.PURPLE}[kind],
                    glow_color={"chest": O.GOLD, "loot": O.CYAN, "bonus": O.MAGENTA}[kind]))
                if d > 0:
                    paste_center(cv, lab, x, y - 120 - 60 * d, ease_out_back(d / 0.25), 1 - ease_out((d - 0.7) / 0.3))

        # --- end of the 3:30: "TEMPS ÉCOULÉ" + persistent "hors chrono" tag
        if over and not in_end:
            d = t - limit_edit
            if 0 <= d < 2.0:
                img = C.get_or("ecoule", lambda: O.text_3d("TEMPS ÉCOULÉ !", 150, (255, 90, 80), (190, 0, 30),
                                                           tilt=-3, glow_color=O.RED))
                paste_center(cv, img, W / 2, H * 0.42, ease_out_back(d / 0.3), 1 - ease_out((d - 1.7) / 0.3))
            if d >= 0:
                tag = C.get_or("hctag", lambda: O.text_3d("HORS CHRONO", 40, (255, 170, 255), O.PURPLE,
                                                          depth=3, outline=4, alt=True, glow_color=O.MAGENTA))
                paste_center(cv, tag, W - 160, 300, ease_out_back((d - 0.3) / 0.3))

        # --- speed badge
        if not in_end and piece["speed"] > 1:
            sp = piece["speed"]
            badge = C.get_or(("speed", sp), lambda: O.text_3d(
                f"ACCÉLÉRÉ x{sp:g}", 46, O.WHITE, (190, 210, 255),
                depth=3, outline=4, alt=True, glow_color=O.BLUE))
            paste_center(cv, badge, W / 2, H - 75)

        # --- callout boxes
        for te, txt, sub, rar, dur in texts:
            d = t - te
            if 0 <= d < dur and not in_end:
                box = C.get_or(("box", txt, sub, rar), lambda: O.box_3d(txt, sub, rarity=rar, size=56))
                paste_center(cv, box, W / 2, 170 if t > 3.4 else 380,
                             ease_out_back(d / 0.3), 1 - ease_out((d - dur + 0.3) / 0.3))

        # --- rage captions (red, shaking)
        for te, txt, dur in rages:
            d = t - te
            if 0 <= d < dur and not in_end:
                img = C.get_or(("rage", txt), lambda: O.text_3d(txt, 120, (255, 90, 80), (190, 0, 30),
                                                                 tilt=-4, glow_color=O.RED))
                sh = 14 * math.sin(d * 70) * math.exp(-d * 2)
                paste_center(cv, img, W / 2 + sh, H * 0.70 + sh * 0.6, ease_out_back(d / 0.2),
                             1 - ease_out((d - dur + 0.25) / 0.25))

        # --- result card
        if in_end:
            d = t - base_end
            name = C.get_or("rname", lambda: O.text_3d(spec["name"], 120, O.WHITE, (185, 215, 255),
                                                       tilt=-2, glow_color=O.CYAN))
            paste_center(cv, name, W / 2, 230, ease_out_back(d / 0.4))
            big = C.get_or("rbig", lambda: O.text_3d(f"{final_count} COFFRES", 190, O.YELLOW, O.GOLD,
                                                     glow_color=O.GOLD))
            paste_center(cv, big, W / 2, 500, ease_out_back((d - 0.35) / 0.45))
            sub = C.get_or("rsub", lambda: O.box_3d(
                f"EN {fmt_mmss(run_end)} DE FARM",
                f"SPOT {spec['number']} / 5" + (f"  +  {n_bonus} BONUS HORS CHRONO" if n_bonus else ""),
                rarity="rare", size=54))
            paste_center(cv, sub, W / 2, 780, ease_out_back((d - 0.8) / 0.4))
            paste_center(cv, C.get_or("rcnt", lambda: O.chest_icon(220, open_=True)),
                         W / 2 - 640, 500, ease_out_back((d - 0.5) / 0.4))
            paste_center(cv, C.get_or("rtim", lambda: O.circular_timer(CHRONO - run_end, CHRONO)),
                         W / 2 + 640, 500, ease_out_back((d - 0.6) / 0.4))

        proc.stdin.write(cv.tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode()
    if proc.wait():
        raise RuntimeError(err[-3000:])
    return dict(t0_edit=t0_edit, ev_edit=ev_edit, limit_edit=limit_edit, texts=[x[0] for x in texts], total=total,
                base_end=base_end, final_count=final_count, run_end=run_end)


# ----------------------------------------------------------------- step 3
def _read_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def _sfx_ding():
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for f0, dly in ((1318.5, 0.0), (1975.5, 0.07), (2637.0, 0.14)):  # E6 B6 E7 arpeggio
        m = t >= dly
        tt = t[m] - dly
        y[m] += np.sin(2 * np.pi * f0 * tt + 1.5 * np.exp(-tt * 8) * np.sin(2 * np.pi * f0 * 2 * tt)) * np.exp(-tt * 7)
    rng = np.random.default_rng(3)
    y += rng.uniform(-1, 1, n) * np.exp(-t * 30) * 0.15
    return y * 0.33


def _sfx_whoosh(d=0.35):
    n = int(d * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(5)
    x = rng.uniform(-1, 1, n)
    env = np.sin(np.pi * t / d) ** 2
    # sweep a one-pole lowpass upwards
    y = np.empty(n)
    acc = 0.0
    for i in range(n):
        a = math.exp(-2 * math.pi * (300 + 5000 * t[i] / d) / SR)
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y * env * 0.5


def _sfx_impact():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * np.cumsum(45 + 140 * np.exp(-t * 22)) / SR) * np.exp(-t * 4.5)
    return np.tanh(y * 2.2) * 0.55


def drop_time(preset):
    p = MM.PRESETS[preset]
    bar = 4 * 60 / p["bpm"]
    bars = 0
    for sec, nb in p["form"]:
        if sec == "drop":
            return bars * bar
        bars += nb
    return 0.0


def mix_audio(spec, tl, info, game_wav, out_wav, work):
    total = info["total"]
    N = int(total * SR)
    mix = np.zeros((N, 2), np.float32)
    game = _read_wav(game_wav)[:N]
    mix[:len(game)] += game * 1.0

    # music: start so that the first drop lands on the landing
    mus_wav = os.path.join(work, "music.wav")
    if not os.path.exists(mus_wav):
        MM.write(mus_wav, MM.render(spec["music"], duration=max(150, total + 60),
                                    seed=list(MM.PRESETS).index(spec["music"]) * 11 + 3))
    music = _read_wav(mus_wav)
    mus_sr = 44100
    offset = max(0.0, drop_time(spec["music"]) - info["t0_edit"])
    idx = (np.arange(N) / SR + offset) * mus_sr
    idx = np.clip(idx, 0, len(music) - 2)
    i0 = idx.astype(int)
    fr = (idx - i0)[:, None]
    music = music[i0] * (1 - fr) + music[i0 + 1] * fr

    env = np.full(N, 0.30, np.float32)  # quieter under normal-speed gameplay
    for p in tl.pieces:
        if p["speed"] > 1:
            a, b = int(p["edit0"] / FPS * SR), int((p["edit0"] + p["frames"]) / FPS * SR)
            env[a:b] = 0.62
    env[:int(info["t0_edit"] * SR)] = 0.55
    env[int(info["base_end"] * SR):] = 0.85
    k = int(0.15 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    mix += music * env[:, None]

    def add(sig, at, gain=1.0):
        i = int(at * SR)
        if i >= N or i < 0:
            return
        j = min(N, i + len(sig))
        mix[i:j] += (sig[:j - i] * gain)[:, None]

    ding, whoosh, impact = _sfx_ding(), _sfx_whoosh(), _sfx_impact()
    for te in info["ev_edit"]:
        add(ding, te, 0.9)
    prev = None
    for p in tl.pieces:  # whoosh on every speed change
        if prev is not None and p["speed"] != prev:
            add(whoosh, p["edit0"] / FPS - 0.17, 0.7)
        prev = p["speed"]
    for te in info["texts"]:
        add(whoosh, te - 0.05, 0.45)
    add(impact, info["t0_edit"], 0.8)
    if info.get("limit_edit") is not None:
        add(impact, info["limit_edit"], 1.0)
    add(impact, info["base_end"], 0.9)
    add(ding, info["base_end"] + 0.4, 0.8)

    fi = int(0.4 * SR)
    mix[-fi:] *= np.linspace(1, 0, fi)[:, None]
    peak = np.max(np.abs(mix)) + 1e-9
    mix = np.tanh(mix / peak * 1.25) / math.tanh(1.25) * 0.93
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ----------------------------------------------------------------- driver
def build_spot(spec, out_path, work_root="renders/work"):
    work = os.path.join(work_root, spec["key"])
    os.makedirs(work, exist_ok=True)
    tl = Timeline(spec)
    print(f"[{spec['key']}] {len(tl.pieces)} pieces, {tl.duration:.1f}s edited")
    base, game_wav = render_base(spec, tl, work)
    vid = os.path.join(work, "video.mp4")
    info = render_overlays(spec, tl, base, vid, work)
    wav = os.path.join(work, "mix.wav")
    mix_audio(spec, tl, info, game_wav, wav, work)
    run(["ffmpeg", "-y", "-i", vid, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out_path])
    print(f"[{spec['key']}] -> {out_path}  ({info['total']:.1f}s, {info['final_count']} coffres, "
          f"run {fmt_mmss(info['run_end'])})")
    for (g, *_), te in zip(sorted(spec["events"]), info["ev_edit"]):
        print(f"   coffre @ source {g:7.2f}s  -> montage {te:6.2f}s  (run {fmt_mmss(g - spec['t0'])})")
    return info
