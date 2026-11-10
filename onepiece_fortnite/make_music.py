"""
=====================================================================
  Procedural epic soundtrack  (numpy only, no samples / no internet)
=====================================================================
Writes build/soundtrack.wav, synced to config.EVENTS / TEXT_TIMING:

  0-8 s    storm: rain, thunder on each lightning strike, dark pad,
           accelerating heartbeat + bells as the token rises, riser -> flash
  8-16 s   sunrise: epic chords (Dm-Bb-F-C), taiko, one hit per crew member
  16-18 s  snare roll on the wind-up, whoosh on the Gum-Gum stretch,
           BIG impact on the golden explosion
  18-26 s  anthem drop with heroic lead, hits on "14 DAYS FREE" / "TWO TIMES"
  26-29 s  emotional breakdown (pads + bells) for "KEEP OPENING"
  29-36 s  anthem returns, title hits, logo impact, ring-out

Edit BPM / KEY / CHORDS / MELODY below to change the music.
Run:  python3 make_music.py
"""
import os
import sys
import wave
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

SR = 44100
BPM = 120
BEAT = 60.0 / BPM
DUR = C.DURATION
N = int(DUR * SR)
rng = np.random.default_rng(C.SEED)

# MIDI note numbers
D2, F2, A2, Bb1, C2 = 38, 41, 45, 34, 36
CHORDS = [  # (root for bass, chord notes)  - one chord per bar (4 beats)
    (38, [62, 65, 69]),      # Dm
    (34, [58, 62, 65]),      # Bb
    (41, [60, 65, 69]),      # F
    (36, [60, 64, 67]),      # C
]
# heroic lead melody for the drop (note, beats) - None = rest
MELODY = [(69, 1.5), (72, 0.5), (74, 2), (72, 1), (70, 1), (69, 2),
          (65, 1), (67, 1), (69, 1.5), (65, 0.5), (67, 2), (64, 2),
          (69, 1.5), (72, 0.5), (74, 2), (77, 1), (76, 1), (74, 2),
          (72, 1), (70, 1), (69, 4)]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def lowpass(x, cutoff):
    """FFT brick-ish low-pass with a soft knee."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def highpass(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 - 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def saw(freq, t, detune=(0.0,)):
    out = np.zeros_like(t)
    for d in detune:
        ph = (t * freq * (1 + d)) % 1.0
        out += 2 * ph - 1
    return out / len(detune)


def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n); e[:na] = np.linspace(0, 1, na)
    nd = min(nd, n - na); e[na:na + nd] = np.linspace(1, s, nd)
    nr = min(nr, n); e[n - nr:] *= np.linspace(1, 0, nr)
    return e


class Track:
    def __init__(self):
        self.L = np.zeros(N)
        self.R = np.zeros(N)

    def add(self, sig, start, gain=1.0, pan=0.0):
        i = int(start * SR)
        if i >= N:
            return
        sig = sig[: N - i]
        self.L[i:i + len(sig)] += sig * gain * np.sqrt(0.5 * (1 - pan))
        self.R[i:i + len(sig)] += sig * gain * np.sqrt(0.5 * (1 + pan))


# ---------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------
def pad(notes, dur, cutoff=1800, attack=0.6):
    t = t_arr(dur)
    s = sum(saw(hz(m), t, (-0.006, 0.0, 0.007)) for m in notes) / len(notes)
    s = lowpass(s, cutoff)
    return s * env_adsr(len(t), attack, 0.3, 0.85, min(0.8, dur * 0.4))


def strings_stab(notes, dur=0.35):
    t = t_arr(dur)
    s = sum(saw(hz(m), t, (-0.004, 0.005)) for m in notes) / len(notes)
    return lowpass(s, 3500) * env_adsr(len(t), 0.005, 0.12, 0.4, 0.15)


def bass(m, dur):
    t = t_arr(dur)
    s = 0.7 * np.sin(2 * np.pi * hz(m) * t) + 0.3 * saw(hz(m), t)
    return lowpass(s, 400) * env_adsr(len(t), 0.005, 0.1, 0.8, 0.08)


def lead(m, dur):
    t = t_arr(dur)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t * 3, 0, 1)
    ph = np.cumsum(hz(m) * vib) / SR
    s = 2 * (ph % 1.0) - 1 + 0.5 * (2 * ((ph * 2.003) % 1.0) - 1)
    s = lowpass(s, 2600)
    return s * env_adsr(len(t), 0.03, 0.15, 0.75, 0.12)


def bell(m, dur=2.5):
    t = t_arr(dur)
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 3)
         + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 6))
    return s * np.exp(-t * 1.8) * env_adsr(len(t), 0.002, 0.05, 1.0, 0.1)


def kick(dur=0.45):
    t = t_arr(dur)
    f = 45 + 110 * np.exp(-t * 28)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = rng.standard_normal(len(t)) * np.exp(-t * 300) * 0.3
    return np.tanh(1.8 * (s + click))


def snare(dur=0.3):
    t = t_arr(dur)
    n = highpass(rng.standard_normal(len(t)), 1500) * np.exp(-t * 18)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    return 0.7 * n + 0.5 * tone


def hat(dur=0.07):
    t = t_arr(dur)
    return highpass(rng.standard_normal(len(t)), 7000) * np.exp(-t * 60)


def taiko(dur=1.4, pitch=70):
    t = t_arr(dur)
    f = pitch * (1 + 0.6 * np.exp(-t * 20))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    n = lowpass(rng.standard_normal(len(t)), 900) * np.exp(-t * 30) * 0.6
    return np.tanh(1.5 * (s + n))


def boom(dur=3.0):
    """Trailer impact: sub drop + noise crack + long tail."""
    t = t_arr(dur)
    sub = np.sin(2 * np.pi * np.cumsum(30 + 60 * np.exp(-t * 6)) / SR) * np.exp(-t * 1.6)
    crack = lowpass(rng.standard_normal(len(t)), 5000) * np.exp(-t * 12)
    return np.tanh(1.6 * (sub + 0.6 * crack))


def whoosh(dur=0.6, rising=True):
    t = t_arr(dur)
    n = rng.standard_normal(len(t))
    x = t / dur
    e = (x ** 2 if rising else (1 - x) ** 2) * np.sin(np.pi * x) ** 0.5
    return lowpass(highpass(n, 400), 4000) * e


def riser(dur=2.0):
    t = t_arr(dur)
    x = t / dur
    f = 200 + 1600 * x ** 2
    sweep = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35
    # band-limited noise whose brightness rises with the sweep
    n = lowpass(highpass(rng.standard_normal(len(t)), 600), 5000) * 0.3
    n = n * (0.3 + 0.7 * x)
    return (sweep + n) * x ** 2.2


def sparkle(dur=1.0):
    out = np.zeros(int(dur * SR))
    for k in range(6):
        b = bell(rng.choice([86, 89, 93, 98]), 0.8) * 0.4
        i = int(k * 0.06 * SR)
        out[i:i + len(b)] += b[: len(out) - i]
    return out


def reverb(x, seconds=1.8, mix=0.25):
    ir_n = int(seconds * SR)
    t = np.arange(ir_n) / SR
    ir = rng.standard_normal(ir_n) * np.exp(-t * 3.5 / seconds * 2)
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2))
    L = len(x) + ir_n
    nfft = 1 << (L - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[: len(x)]
    return x * (1 - mix) + wet * mix * 1.5


# ---------------------------------------------------------------------
# Arrangement  (all times come from config.EVENTS / SECTIONS / TEXT_TIMING)
# ---------------------------------------------------------------------
def rain_bed(dur):
    n = rng.standard_normal(int(dur * SR))
    return lowpass(highpass(n, 300), 6000) * 0.5


def thunder(dur=4.0):
    t = t_arr(dur)
    crack = highpass(rng.standard_normal(len(t)), 800) * np.exp(-t * 9)
    rumble = lowpass(rng.standard_normal(len(t)), 160) * np.exp(-t * 0.9) * 3.0
    return np.tanh(crack * 0.8 + rumble)


def heartbeat(dur=0.6):
    t = t_arr(dur)
    s = np.sin(2 * np.pi * np.cumsum(55 + 25 * np.exp(-t * 30)) / SR) * np.exp(-t * 12)
    return s


def build():
    music = Track()     # gets reverb
    fx = Track()        # impacts (less reverb)
    S, E, TT = C.SECTIONS, C.EVENTS, C.TEXT_TIMING
    flash = E["dawn_flash"]
    boom_t = E["explosion"]
    bar = 4 * BEAT

    # --- 0-8 : storm, mystery, hunger ----------------------------------
    fx.add(rain_bed(flash + 0.6), 0.0, 0.10)
    music.add(pad([50, 57, 62, 65], flash + 0.4, cutoff=800, attack=2.5), 0.0, 0.45)
    music.add(pad([38], flash + 0.4, cutoff=250, attack=2.0), 0.0, 0.5)
    for lt in E["lightning"]:
        fx.add(thunder(), lt + 0.08, 0.55, pan=rng.uniform(-0.5, 0.5))
    # a heartbeat that speeds up as the token rises (the hope)
    hb, step = 1.0, 1.0
    while hb < flash - 0.4:
        music.add(heartbeat(), hb, 0.6)
        music.add(heartbeat(), hb + 0.22, 0.4)
        hb += step
        step = max(0.5, step * 0.93)
    for i, m in enumerate([74, 77, 81, 79, 74, 77, 81, 84, 81, 77, 86, 89]):
        music.add(bell(m, 2.2), 1.2 + i * 0.52, 0.16, pan=(-0.5 if i % 2 else 0.5))
    fx.add(whoosh(1.0), TT["rarest"][0] - 0.9, 0.3)
    fx.add(boom(2.0), TT["rarest"][0], 0.35)
    fx.add(riser(2.4), flash - 2.4, 0.6)
    fx.add(boom(3.5), flash, 0.95)
    fx.add(sparkle(1.5), flash + 0.05, 0.5)

    # --- 8-16 : sunrise, the crew assembles ---------------------------
    t = S["reveal"][0]
    i = 0
    while t < S["reveal"][1] - 0.01:
        root, notes = CHORDS[i % 4]
        music.add(pad(notes + [notes[0] + 12], bar, cutoff=1400 + 400 * i, attack=0.3), t, 0.42)
        music.add(bass(root, bar), t, 0.45)
        music.add(taiko(), t, 0.7)
        music.add(taiko(pitch=90), t + 2 * BEAT, 0.5)
        if i >= 2:
            for b in range(4):
                music.add(kick(), t + b * BEAT, 0.55)
                music.add(hat(), t + b * BEAT + BEAT / 2, 0.15, pan=0.4)
        t += bar
        i += 1
    fx.add(boom(2.0), TT["one_drop"][0], 0.55)
    for k, a in enumerate(E["crew_appear"]):
        fx.add(whoosh(0.4), a - 0.4, 0.5, pan=(-0.4 if k % 2 else 0.4))
        fx.add(boom(1.4), a, 0.5)
        fx.add(sparkle(0.9), a + 0.05, 0.3)
    fx.add(riser(1.8), S["climax"][0] - 1.8, 0.45)

    # --- 16-17.75 : wind-up, Gum-Gum, grab ------------------------------
    t0 = S["climax"][0]
    music.add(pad([62, 65, 69, 74], boom_t - t0, cutoff=1200, attack=0.2), t0, 0.35)
    tr, step = t0 + 0.1, 0.18
    while tr < E["launch"] - 0.1:
        music.add(snare(0.15), tr, 0.2 + 0.4 * (tr - t0) / (E["launch"] - t0))
        tr += step
        step = max(0.06, step * 0.88)
    fx.add(whoosh(0.5, rising=False), E["launch"], 0.8)          # the stretch
    fx.add(taiko(1.0, 140), E["grab"], 0.6)                       # the catch
    fx.add(boom(4.5), boom_t, 1.0)                                # EXPLOSION
    fx.add(taiko(2.0, 55), boom_t, 0.8)
    fx.add(sparkle(2.0), boom_t + 0.1, 0.55)
    fx.add(sparkle(2.0), boom_t + 0.9, 0.4)

    # --- anthem drop, emotional breakdown, final rise --------------------
    breakdown = (S["finale"][0], TT["final_lines"][1][0])       # 26.0 -> 29.0: soft
    logo = E["logo"]
    end = DUR - 1.0
    t = boom_t + 0.2
    i = 0
    while t < end:
        root, notes = CHORDS[i % 4]
        length = min(bar, end - t)
        soft = breakdown[0] <= t < breakdown[1]
        music.add(pad(notes + [notes[0] + 12, notes[2] + 12], length, cutoff=2200 if soft else 3200,
                      attack=0.3 if soft else 0.05), t, 0.7 if soft else 0.35)
        for b in range(4):
            bt = t + b * BEAT
            if bt >= end:
                break
            if breakdown[0] <= bt < breakdown[1]:
                music.add(bell(notes[b % 3] + 12, 1.5), bt, 0.3)        # gentle, emotional
                continue
            music.add(kick(), bt, 0.85)
            music.add(bass(root, BEAT * 0.9), bt, 0.45)
            music.add(hat(), bt + BEAT / 2, 0.2, pan=0.4)
            if b in (1, 3):
                music.add(snare(), bt, 0.55)
                music.add(taiko(0.9, 100), bt, 0.25)
        t += bar
        i += 1
    # heroic lead over the drop, reprised after the breakdown
    for start, stop in ((boom_t + 0.2 + bar, breakdown[0] - 0.1), (breakdown[1], end)):
        tm = start
        for m, beats in MELODY:
            d = beats * BEAT
            if tm + d > stop:
                break
            music.add(lead(m, d * 0.95), tm, 0.22, pan=0.1)
            music.add(lead(m - 12, d * 0.95), tm, 0.1, pan=-0.1)
            tm += d
    for key in ("days_free", "two_times"):
        fx.add(whoosh(0.35), TT[key][0] - 0.35, 0.45)
        fx.add(boom(1.6), TT[key][0], 0.6)
    for (a, _b) in TT["final_lines"]:
        fx.add(whoosh(0.35), a - 0.35, 0.45)
        fx.add(boom(1.5), a, 0.55)
    fx.add(riser(1.0), logo - 1.0, 0.5)
    fx.add(boom(3.0), logo, 1.0)
    fx.add(taiko(2.5, 50), logo, 0.8)
    fx.add(sparkle(2.0), logo + 0.1, 0.5)
    music.add(pad([62, 69, 74, 77, 81], DUR - logo, cutoff=4000, attack=0.02), logo, 0.4)
    music.add(bass(26, DUR - logo), logo, 0.5)

    # --- mix ------------------------------------------------------------
    L = reverb(music.L, 2.0, 0.3) + reverb(fx.L, 1.2, 0.15)
    Rr = reverb(music.R, 2.1, 0.3) + reverb(fx.R, 1.3, 0.15)
    st = np.stack([L, Rr], axis=1)
    st = np.tanh(st * 1.2 / max(1e-6, np.percentile(np.abs(st), 99.9)))   # glue / limiter
    fi, fo = int(0.3 * SR), int(1.0 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]
    st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    st *= 0.89 / np.max(np.abs(st))
    return st


def write_wav(path, st):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (st * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    st = build()
    write_wav(C.MUSIC_FILE, st)
    print("wrote", C.MUSIC_FILE, f"{len(st) / SR:.2f}s")
