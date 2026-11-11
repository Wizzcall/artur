"""Generate an original, royalty-free, Fortnite-lobby-style electro track.

128 BPM, upbeat synth-pop/electro: kick, clap, hats, sidechained bass,
supersaw chord stabs and a bright arpeggiated lead. Output: WAV (stereo, 44.1k).
Usage: python3 make_music.py out.wav [duration_seconds]
"""
import sys
import wave
import numpy as np

SR = 44100
BPM = 128
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a=0.005, d=0.1, s=0.6, r=0.05, length=None):
    length = length or n / SR
    t = np.arange(n) / SR
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / d))
    rel_start = max(length - r, 0)
    e = e * np.clip((length - t) / r, 0, 1) if r > 0 else e
    return e


def saw(f, t, detune=0.0):
    ph = (f * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))


def supersaw(f, t, voices=5, spread=0.012):
    out = np.zeros_like(t)
    for i in range(voices):
        d = spread * (i - (voices - 1) / 2) / ((voices - 1) / 2)
        out += saw(f, t + rng.random() * 0.01, d)
    return out / voices


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 120 * np.exp(-t * 35)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7) * 1.0


def clap():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    noise = noise - lowpass(noise, 900)
    e = np.exp(-t * 18) + 0.6 * np.exp(-((t - 0.012) % 0.011) * 300) * (t < 0.035)
    return noise * e * 0.55


def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    noise = noise - lowpass(noise, 6000)
    return noise * np.exp(-t * (14 if open_ else 70)) * 0.22


def tone(f, dur, kind="saw", cutoff=4000, amp=0.3, a=0.005, d=0.12, s=0.5, r=0.04):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "supersaw":
        w = supersaw(f, t)
    elif kind == "square":
        w = np.sign(np.sin(2 * np.pi * f * t)) * 0.7 + saw(f * 2, t) * 0.2
    elif kind == "sub":
        w = np.sin(2 * np.pi * f * t) + 0.35 * saw(f, t)
    else:
        w = saw(f, t)
    w = lowpass(w, cutoff)
    return w * env(n, a, d, s, r) * amp


def place(buf, sig, t0, pan=0.0):
    i = int(t0 * SR)
    j = min(i + len(sig), buf.shape[0])
    if i >= buf.shape[0]:
        return
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    buf[i:j, 0] += sig[: j - i] * l
    buf[i:j, 1] += sig[: j - i] * r


# Chord progression (C major-ish, bright/heroic): C - G - Am - F, root MIDI
PROG = [
    (48, [60, 64, 67, 72]),
    (43, [59, 62, 67, 71]),
    (45, [60, 64, 69, 72]),
    (41, [60, 65, 69, 72]),
]
ARP = [0, 2, 1, 3, 2, 1, 3, 2]  # indices into chord notes
LEAD_MOTIF = [76, 79, 81, 79, 76, 74, 76, None, 72, 74, 76, 79, 81, None, 79, 76]


def build(duration):
    n_bars = int(np.ceil(duration / BAR))
    buf = np.zeros((int(n_bars * BAR * SR) + SR, 2))
    side = np.ones(buf.shape[0])  # sidechain envelope
    K, C, H, OH = kick(), clap(), hat(), hat(True)

    # pre-render one-shot chord/bass/arp per chord to save time
    cache = {}

    for b in range(n_bars):
        section = (b // 8) % 6  # 0 intro,1 build,2 drop,3 drop2,4 break,5 drop
        root, chord = PROG[b % 4]
        t_bar = b * BAR
        drums_on = section != 4
        full = section in (2, 3, 5)

        for beat in range(4):
            tb = t_bar + beat * BEAT
            if drums_on and (section != 0 or beat % 2 == 0):
                place(buf, K, tb)
                i = int(tb * SR)
                L = int(BEAT * SR * 0.9)
                if i + L < len(side):
                    side[i:i + L] = np.minimum(side[i:i + L], 0.25 + 0.75 * np.linspace(0, 1, L) ** 0.6)
            if drums_on and section >= 1 and beat in (1, 3):
                place(buf, C, tb, 0.05)
            for e in range(2):
                if section >= 1 or e == 1:
                    place(buf, OH if (e == 1 and full) else H, tb + e * BEAT / 2, 0.3 if e else -0.3)
            if full:
                place(buf, H * 0.6, tb + BEAT * 0.25, -0.4)
                place(buf, H * 0.6, tb + BEAT * 0.75, 0.4)

        # bass: offbeat 8ths, sidechained
        key = ("bass", root)
        if key not in cache:
            cache[key] = tone(midi(root), BEAT / 2 * 0.95, "sub", cutoff=900, amp=0.45, d=0.08, s=0.7)
        if section != 0:
            for e in range(8):
                place(buf, cache[key] * (1.0 if e % 2 else 0.75), t_bar + e * BEAT / 2)

        # chord stabs (supersaw), every bar on syncopated rhythm
        key = ("chord", tuple(chord), full)
        if key not in cache:
            dur = BEAT * 0.45
            cache[key] = sum(tone(midi(n), dur, "supersaw", cutoff=5000 if full else 1800,
                                  amp=0.11, d=0.15, s=0.3) for n in chord)
        stab_times = [0, 0.75, 1.5, 2.5, 3.25] if full else [0, 1.5, 2.5]
        for st in stab_times:
            place(buf, cache[key], t_bar + st * BEAT, rng.uniform(-0.2, 0.2))

        # arpeggio 16ths (build, drops, break)
        if section in (1, 2, 4, 5):
            for s in range(16):
                note = chord[ARP[s % 8]] + 12
                key = ("arp", note)
                if key not in cache:
                    cache[key] = tone(midi(note), BEAT / 4 * 0.9, "square", cutoff=3500, amp=0.07, d=0.05, s=0.2)
                place(buf, cache[key], t_bar + s * BEAT / 4, 0.5 if s % 2 else -0.5)

        # lead motif on main drops (2 bars long)
        if section in (3, 5):
            half = (b % 2) * 8
            for s in range(8):
                note = LEAD_MOTIF[half + s]
                if note is None:
                    continue
                key = ("lead", note)
                if key not in cache:
                    cache[key] = tone(midi(note), BEAT / 2 * 0.95, "supersaw", cutoff=6000, amp=0.14, a=0.01, d=0.2, s=0.6)
                place(buf, cache[key], t_bar + s * BEAT / 2)

        # riser into drops
        if section in (1, 4) and b % 8 == 7:
            n = int(BAR * SR)
            t = np.arange(n) / SR
            noise = rng.uniform(-1, 1, n)
            noise = noise - lowpass(noise, 2000)
            place(buf, noise * (t / BAR) ** 2 * 0.25, t_bar)

    # apply sidechain to everything except drums is approximated on whole mix lightly
    buf *= (0.55 + 0.45 * side[: buf.shape[0], None])
    buf = buf[: int(duration * SR)]
    # fade in/out
    fi, fo = int(0.5 * SR), int(3 * SR)
    buf[:fi] *= np.linspace(0, 1, fi)[:, None]
    buf[-fo:] *= np.linspace(1, 0, fo)[:, None]
    # soft clip + normalize
    buf = np.tanh(buf * 1.4)
    buf /= np.max(np.abs(buf)) + 1e-9
    return (buf * 0.89 * 32767).astype(np.int16)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "music.wav"
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 120
    data = build(dur)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print("wrote", out, dur, "s")
