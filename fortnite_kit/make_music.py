"""Original, royalty-free, Fortnite-lobby-style music — one track per section.

Each preset has its own tempo, key, groove, instruments and melody so every
part of the video sounds different while staying in the same "Fortnite" family.

Usage:
    python3 make_music.py all [out_dir]          # render every preset
    python3 make_music.py <preset> out.wav [sec] # render one preset
Presets: intro, rubber_resort, lantern_landing, loguetown, arlong_park,
         the_chest, classement
"""
import os
import sys
import wave
import numpy as np
from scipy.signal import lfilter, butter

SR = 44100
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
HARM_MINOR = [0, 2, 3, 5, 7, 8, 11]
DORIAN = [0, 2, 3, 5, 7, 9, 10]

_ = None  # rest in melodies

PRESETS = {
    # Hype opener: big electro build -> drop, bright major.
    "intro": dict(
        bpm=140, root=50, scale=MAJOR, groove="four", bass="saw",
        prog=[0, 4, 5, 3], chord="supersaw", arp="square", lead="supersaw",
        melody=[4, 4, 5, 4, 2, _, 0, 1, 2, 2, 4, 2, 1, _, 0, _],
        form=[("intro", 4), ("build", 8), ("drop", 16), ("drop2", 16)],
        duration=45,
    ),
    # Tropical / bouncy house, marimba + plucks (sunny resort).
    "rubber_resort": dict(
        bpm=112, root=55, scale=MAJOR, groove="tropical", bass="sub",
        prog=[0, 5, 3, 4], chord="pluck", arp="marimba", lead="marimba",
        melody=[4, _, 2, 4, 5, 4, 2, _, 0, _, 2, 1, 0, _, -2, _],
        form=[("intro", 8), ("build", 8), ("drop", 16), ("break", 8), ("drop2", 16)],
        duration=150,
    ),
    # Asian-inspired pentatonic, koto-like plucks & bells (lanterns).
    "lantern_landing": dict(
        bpm=118, root=52, scale=MINOR, groove="four", bass="sub",
        prog=[0, 5, 6, 4], chord="pad", arp="pluck", lead="bell",
        melody=[7, 6, 4, _, 3, 4, _, 0, 3, _, 4, 6, 7, _, 9, 7],
        form=[("intro", 8), ("build", 8), ("drop", 16), ("break", 8), ("drop2", 16)],
        duration=150,
    ),
    # Pirate-town shanty electro: harmonic minor, accordion-ish lead.
    "loguetown": dict(
        bpm=126, root=50, scale=HARM_MINOR, groove="shanty", bass="saw",
        prog=[0, 3, 4, 0], chord="supersaw", arp="pluck", lead="accordion",
        melody=[0, 2, 4, 4, 4, 3, 2, 3, 4, _, 6, 5, 4, 3, 2, _],
        form=[("intro", 8), ("build", 8), ("drop", 16), ("break", 8), ("drop2", 16)],
        duration=150,
    ),
    # Aggressive half-time bass track with reese bass (boss lair).
    "arlong_park": dict(
        bpm=140, root=45, scale=MINOR, groove="halftime", bass="reese",
        prog=[0, 5, 2, 6], chord="pad", arp="square", lead="square",
        melody=[0, _, 0, 3, _, 2, 0, _, 5, _, 4, 3, _, 2, 3, _],
        form=[("intro", 8), ("build", 8), ("drop", 16), ("break", 8), ("drop2", 16)],
        duration=150,
    ),
    # Treasure-hunt adventure: heroic major, bells + brass stabs.
    "the_chest": dict(
        bpm=128, root=53, scale=MAJOR, groove="four", bass="saw",
        prog=[0, 3, 5, 4], chord="brass", arp="bell", lead="supersaw",
        melody=[0, 2, 4, 7, _, 6, 4, 5, 4, _, 2, 4, 1, _, 0, _],
        form=[("intro", 8), ("build", 8), ("drop", 16), ("break", 8), ("drop2", 16)],
        duration=150,
    ),
    # Victory anthem for the final ranking.
    "classement": dict(
        bpm=124, root=48, scale=MAJOR, groove="four", bass="saw",
        prog=[3, 4, 0, 5], chord="supersaw", arp="bell", lead="brass",
        melody=[4, _, 4, 5, 7, _, 5, 4, 2, _, 4, 2, 0, _, _, _],
        form=[("intro", 4), ("build", 8), ("drop", 16), ("break", 4), ("drop2", 16)],
        duration=90,
    ),
}


# ----------------------------------------------------------------- DSP utils
def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def lp(x, cutoff, order=2):
    b, a = butter(order, min(cutoff, SR / 2 - 100) / (SR / 2))
    return lfilter(b, a, x)


def hp(x, cutoff, order=2):
    b, a = butter(order, cutoff / (SR / 2), "high")
    return lfilter(b, a, x)


def adsr(n, a=0.005, d=0.1, s=0.6, r=0.04):
    t = np.arange(n) / SR
    L = n / SR
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    return e * np.clip((L - t) / max(r, 1e-4), 0, 1)


def saw(f, t):
    p = f * t
    return 2 * (p - np.floor(p + 0.5))


class Synth:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.cache = {}

    def note(self, inst, n, dur):
        key = (inst, n, round(dur, 3))
        if key not in self.cache:
            self.cache[key] = getattr(self, "_" + inst)(midi(n), int(dur * SR))
        return self.cache[key]

    # instruments --------------------------------------------------------
    def _supersaw(self, f, n):
        t = np.arange(n) / SR
        w = sum(saw(f * (1 + d), t + self.rng.random() * .01) for d in (-.012, -.006, 0, .006, .012)) / 5
        return lp(w, 5500) * adsr(n, .005, .18, .35, .05) * .32

    def _square(self, f, n):
        t = np.arange(n) / SR
        w = np.sign(np.sin(2 * np.pi * f * t)) * .6 + saw(f * 2, t) * .2
        return lp(w, 3800) * adsr(n, .003, .07, .25, .03) * .22

    def _pluck(self, f, n):  # Karplus-Strong
        N = max(2, int(SR / f))
        x = np.zeros(n)
        x[:N] = self.rng.uniform(-1, 1, N)
        a = np.zeros(N + 2)
        a[0], a[N], a[N + 1] = 1, -.497, -.497
        return lp(lfilter([1], a, x), 6000) * adsr(n, .001, .5, .0, .03) * .5

    def _marimba(self, f, n):
        t = np.arange(n) / SR
        w = np.sin(2 * np.pi * f * t) + .25 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 40)
        return w * np.exp(-t * 9) * adsr(n, .002, 1, 1, .02) * .45

    def _bell(self, f, n):  # simple FM bell
        t = np.arange(n) / SR
        mod = 2.2 * np.exp(-t * 6) * np.sin(2 * np.pi * f * 3.5 * t)
        return np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 4) * adsr(n, .002, 1, 1, .03) * .3

    def _pad(self, f, n):
        t = np.arange(n) / SR
        w = sum(saw(f * (1 + d), t) for d in (-.008, 0, .008)) / 3
        return lp(w, 2200) * adsr(n, .08, .5, .8, .15) * .16

    def _brass(self, f, n):
        t = np.arange(n) / SR
        w = saw(f, t) + .5 * saw(f * 1.004, t)
        cut = 800 + 4000 * (1 - np.exp(-t * 18))
        y = lp(w * .5, 4000) * .4 + lp(w * .5, 1200) * .6 * (cut / 4800)
        return y * adsr(n, .02, .2, .7, .05) * .38

    def _accordion(self, f, n):
        t = np.arange(n) / SR
        vib = 1 + .004 * np.sin(2 * np.pi * 5.5 * t)
        ph = np.cumsum(f * vib) / SR
        w = (np.sign(np.sin(2 * np.pi * ph)) + np.sign(np.sin(2 * np.pi * ph * 1.006))) * .5
        return lp(w, 3000) * adsr(n, .02, .2, .8, .05) * .2

    # bass
    def _sub(self, f, n):
        t = np.arange(n) / SR
        return (np.sin(2 * np.pi * f * t) + .25 * lp(saw(f, t), 600)) * adsr(n, .004, .12, .8, .03) * .55

    def _saw_bass(self, f, n):
        t = np.arange(n) / SR
        return (lp(saw(f, t) + saw(f * 1.005, t), 1100) * .4 + np.sin(2 * np.pi * f * t) * .5) * adsr(n, .003, .1, .75, .03) * .55

    def _reese(self, f, n):
        t = np.arange(n) / SR
        w = saw(f * .995, t) + saw(f * 1.007, t)
        lfo = 700 + 600 * np.sin(2 * np.pi * 2 * t)
        y = lp(w, 1500) * (lfo / 1300) + np.sin(2 * np.pi * f * t) * .8
        return np.tanh(y * 1.5) * adsr(n, .005, .3, .9, .05) * .45

    # drums
    def kick(self, punch=1.0):
        n = int(.35 * SR); t = np.arange(n) / SR
        fr = 48 + 130 * np.exp(-t * 32)
        return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 6.5) * punch

    def clap(self):
        n = int(.25 * SR); t = np.arange(n) / SR
        x = hp(self.rng.uniform(-1, 1, n), 900)
        return x * (np.exp(-t * 16) + .5 * (t < .03) * np.exp(-((t % .01)) * 300)) * .45

    def snare(self):
        n = int(.25 * SR); t = np.arange(n) / SR
        return (hp(self.rng.uniform(-1, 1, n), 1500) * np.exp(-t * 18) * .5
                + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * .5)

    def hat(self, open_=False):
        n = int((.2 if open_ else .05) * SR); t = np.arange(n) / SR
        return hp(self.rng.uniform(-1, 1, n), 7000) * np.exp(-t * (13 if open_ else 75)) * .25

    def shaker(self):
        n = int(.08 * SR); t = np.arange(n) / SR
        return hp(self.rng.uniform(-1, 1, n), 5000) * np.sin(np.pi * t / t[-1]) * .12


def place(buf, sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= len(buf):
        return
    j = min(i + len(sig), len(buf))
    buf[i:j, 0] += sig[:j - i] * gain * np.cos((pan + 1) * np.pi / 4)
    buf[i:j, 1] += sig[:j - i] * gain * np.sin((pan + 1) * np.pi / 4)


def deg_to_midi(p, d, octave=0):
    sc = p["scale"]
    o, i = divmod(d, 7)
    return p["root"] + 12 * (o + octave) + sc[i]


def chord_notes(p, d, octave=1):
    return [deg_to_midi(p, d + k, octave) for k in (0, 2, 4)] + [deg_to_midi(p, d, octave + 1)]


def render(name, duration=None, seed=None):
    p = PRESETS[name]
    duration = duration or p["duration"]
    S = Synth(seed if seed is not None else abs(hash(name)) % 1000)
    beat = 60 / p["bpm"]
    bar = 4 * beat
    n_bars = int(np.ceil(duration / bar))

    form = []
    while len(form) < n_bars:  # loop the form (skipping the intro after 1st pass)
        for sec, nb in (p["form"] if not form else p["form"][1:]):
            form += [sec] * nb
    form = form[:n_bars]

    drums = np.zeros((int((n_bars + 1) * bar * SR), 2))
    music = np.zeros_like(drums)
    side = np.ones(len(drums))
    K, C, SN, H, OH, SH = S.kick(), S.clap(), S.snare(), S.hat(), S.hat(True), S.shaker()
    groove = p["groove"]

    for b, sec in enumerate(form):
        t0 = b * bar
        nxt = form[b + 1] if b + 1 < len(form) else None
        full = sec in ("drop", "drop2")
        prog_deg = p["prog"][b % len(p["prog"])]
        root_note = deg_to_midi(p, prog_deg, -1)
        if root_note > p["root"] - 5:
            root_note -= 12
        chord = chord_notes(p, prog_deg)

        # ------------------------------------------------------- drums
        def kick_at(tb, g=1.0):
            place(drums, K, tb, g)
            i, L = int(tb * SR), int(beat * SR * .85)
            if i + L < len(side):
                side[i:i + L] = np.minimum(side[i:i + L], .3 + .7 * np.linspace(0, 1, L) ** .7)

        if sec != "break":
            for k in range(4):
                tb = t0 + k * beat
                if groove == "halftime":
                    if k == 0 or (k == 2 and full and b % 2):
                        kick_at(tb + (beat * .75 if k == 2 else 0))
                    if k == 2 and sec != "intro":
                        place(drums, SN, tb, 1.1); place(drums, C, tb, .7)
                    for s in range(4 if full else 2):
                        place(drums, H, tb + s * beat / (4 if full else 2), .8 if s % 2 else 1, .3)
                elif groove == "tropical":
                    if sec != "intro" or k % 2 == 0:
                        kick_at(tb)
                    if sec != "intro" and k in (1, 3):
                        place(drums, C, tb + (beat * .5 if k == 3 and full else 0), .9)
                    place(drums, SH, tb + beat * .5, 1, -.3)
                    place(drums, SH, tb + beat * .75, .6, .3)
                elif groove == "shanty":
                    if sec != "intro" or k == 0:
                        kick_at(tb)
                    if k in (1, 3) and sec != "intro":
                        place(drums, SN, tb, .9)
                    place(drums, OH if full else H, tb + beat * .5, .9, .25)
                    if full:
                        place(drums, SH, tb + beat * .25, .8, -.3); place(drums, SH, tb + beat * .75, .8, -.3)
                else:  # four on the floor
                    if sec != "intro" or k % 2 == 0:
                        kick_at(tb)
                    if k in (1, 3) and sec != "intro":
                        place(drums, C, tb)
                    place(drums, OH if full else H, tb + beat * .5, .9, .25)
                    if full:
                        place(drums, H, tb + beat * .25, .5, -.35); place(drums, H, tb + beat * .75, .5, -.35)
        # snare roll on last bar of a build
        if sec == "build" and nxt != "build":
            for s in range(16):
                place(drums, SN, t0 + s * bar / 16, .2 + .7 * s / 16)

        # ------------------------------------------------------- bass
        if sec not in ("intro",):
            binst = {"saw": "saw_bass"}.get(p["bass"], p["bass"])
            if p["bass"] == "reese":
                place(music, S.note("reese", root_note, bar * (.95 if full else .5)), t0, .9)
            else:
                pattern = [0, 1, 1.5, 2, 3, 3.5] if groove == "tropical" else [.5, 1.5, 2.5, 3.5] if not full else [k / 2 for k in range(8)]
                for x in pattern:
                    place(music, S.note(binst, root_note, beat * .45), t0 + x * beat, .9 if x % 1 else .7)

        # ------------------------------------------------------- chords
        ci = p["chord"]
        if ci == "pad":
            for nn in chord[:3]:
                place(music, S.note("pad", nn, bar * 1.02), t0, .9 if full else .7)
        else:
            stabs = [0, .75, 1.5, 2.5, 3.25] if full else [0, 1.5, 2.5] if sec != "intro" else [0, 2]
            for x in stabs:
                for nn in chord:
                    place(music, S.note(ci, nn, beat * .45), t0 + x * beat, .45, S.rng.uniform(-.25, .25))

        # ------------------------------------------------------- arpeggio
        if sec in ("build", "drop", "break", "drop2"):
            order = [0, 2, 1, 3, 2, 1, 3, 2]
            step = 4 if sec != "break" else 2
            for s in range(4 * step):
                nn = chord[order[s % 8]] + 12
                place(music, S.note(p["arp"], nn, beat / step * .95), t0 + s * beat / step, .6, .5 if s % 2 else -.5)

        # ------------------------------------------------------- lead
        if sec in ("drop2",) or (sec == "drop" and name in ("intro", "classement")):
            half = (b % 2) * 8
            for s in range(8):
                d = p["melody"][half + s]
                if d is None:
                    continue
                place(music, S.note(p["lead"], deg_to_midi(p, d, 1), beat * .5 * .95), t0 + s * beat / 2, .9)
        if sec == "break":  # melody teased softly on bells/plucks
            half = (b % 2) * 8
            for s in range(8):
                d = p["melody"][half + s]
                if d is not None:
                    place(music, S.note("bell", deg_to_midi(p, d, 1), beat * .5), t0 + s * beat / 2, .5)

        # ------------------------------------------------------- FX
        if sec in ("build", "break") and nxt in ("drop", "drop2"):
            n = int(bar * SR); t = np.arange(n) / SR
            noise = hp(S.rng.uniform(-1, 1, n), 1500 + 6000 * 0)
            place(music, noise * (t / bar) ** 2 * .25, t0)
        if sec in ("drop", "drop2") and form[b - 1] not in ("drop", "drop2"):
            n = int(1.5 * SR); t = np.arange(n) / SR
            place(music, lp(S.rng.uniform(-1, 1, n), 3000) * np.exp(-t * 3) * .35, t0)  # impact
            place(drums, S.kick(1.3), t0)

    mix = drums + music * (.45 + .55 * side[:, None])
    mix = mix[:int(duration * SR)]
    fi, fo = int(.3 * SR), int(2.5 * SR)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    mix = np.tanh(mix * 1.3)
    mix /= np.max(np.abs(mix)) + 1e-9
    return (mix * .89 * 32767).astype(np.int16)


def write(path, data):
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        out = sys.argv[2] if len(sys.argv) > 2 else "music"
        os.makedirs(out, exist_ok=True)
        for i, name in enumerate(PRESETS):
            path = os.path.join(out, f"{i}_{name}.wav")
            write(path, render(name, seed=i * 11 + 3))
            print("wrote", path)
    else:
        name = sys.argv[1] if len(sys.argv) > 1 else "intro"
        out = sys.argv[2] if len(sys.argv) > 2 else f"{name}.wav"
        dur = float(sys.argv[3]) if len(sys.argv) > 3 else None
        write(out, render(name, dur, seed=list(PRESETS).index(name) * 11 + 3))
        print("wrote", out)
