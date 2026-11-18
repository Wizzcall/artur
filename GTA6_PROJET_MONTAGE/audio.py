"""
AUDIO : effets sonores + musiques originales (synthwave / Vice City) + mixage.
Tout est synthétisé ici : aucune musique commerciale, aucun échantillon tiers.

    python audio.py              → build/audio/*.wav  et  build/audio/MIX.wav
    python audio.py --no-voice   → build/audio/MIX_SANS_VOIX.wav (sans voix ni ducking)
"""
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build" / "audio"
SR = 48000
rng = np.random.default_rng(7)


# ═════════════════════════════════════════════════════════ DSP DE BASE
def mtof(m): return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)
def db(x): return 10 ** (x / 20)
def T(d): return np.arange(int(d * SR)) / SR


def polyblep(ph, dt):
    out = np.zeros_like(ph); dt = np.broadcast_to(dt, ph.shape)
    m = ph < dt; x = ph[m] / dt[m]; out[m] = x + x - x * x - 1
    m = ph > 1 - dt; x = (ph[m] - 1) / dt[m]; out[m] = x * x + x + x + 1
    return out


def osc(freq, n, kind="saw", phase0=0.0):
    f = np.full(n, float(freq)) if np.ndim(freq) == 0 else np.asarray(freq, float)[:n]
    dt = f / SR
    ph = (phase0 + np.cumsum(dt)) % 1.0
    if kind == "sine": return np.sin(2 * np.pi * ph)
    if kind == "tri": return 2 * np.abs(2 * ph - 1) - 1
    saw = 2 * ph - 1 - polyblep(ph, dt)
    if kind == "saw": return saw
    if kind == "square":
        ph2 = (ph + 0.5) % 1.0
        return (2 * ph2 - 1 - polyblep(ph2, dt)) - saw
    raise ValueError(kind)


def lp(x, fc, order=2):
    sos = signal.butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos"); return signal.sosfilt(sos, x, axis=0)
def hp(x, fc, order=2):
    sos = signal.butter(order, fc, "high", fs=SR, output="sos"); return signal.sosfilt(sos, x, axis=0)
def bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos"); return signal.sosfilt(sos, x, axis=0)


def lp_sweep(x, fcs, block=1024):
    """Passe-bas à fréquence variable (fcs : courbe par échantillon)."""
    y = np.zeros_like(x); zi = None
    for i in range(0, len(x), block):
        fc = float(np.clip(fcs[min(i, len(fcs) - 1)], 40, SR * 0.45))
        sos = signal.butter(2, fc, "low", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        y[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return y


def bp_sweep(x, fcs, q=1.2, block=512):
    y = np.zeros_like(x); zi = None
    for i in range(0, len(x), block):
        fc = float(np.clip(fcs[min(i, len(fcs) - 1)], 60, SR * 0.4))
        b, a = signal.iirpeak(fc, q, fs=SR)
        if zi is None: zi = np.zeros(2)
        y[i:i + block], zi = signal.lfilter(b, a, x[i:i + block], zi=zi)
    return y


def adsr(n, a=0.01, d=0.1, s=0.7, r=0.2, hold=None):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    hold = n - r if hold is None else int(hold * SR)
    env = np.zeros(n)
    i = np.arange(n)
    env = np.where(i < a, i / max(1, a), np.where(i < a + d, 1 - (1 - s) * (i - a) / max(1, d), s))
    rel = i >= hold
    if rel.any():
        lvl = env[min(hold, n - 1)]
        env[rel] = lvl * np.clip(1 - (i[rel] - hold) / max(1, r), 0, 1)
    return env


def expdec(n, tau): return np.exp(-np.arange(n) / (tau * SR))


def stereo(x, pan=0.0, width=0.0):
    l = x * np.sqrt(0.5 * (1 - pan)); r = x * np.sqrt(0.5 * (1 + pan))
    if width:
        d = int(width * SR); r = np.concatenate([np.zeros(d), r[:-d]]) if d else r
    return np.stack([l, r], 1)


def make_ir(dur=2.4, damp=5000, pre=0.012, seed=3):
    g = np.random.default_rng(seed)
    n = int(dur * SR)
    ir = g.standard_normal((n, 2)) * np.exp(-np.arange(n) / (dur / 6.9 * SR))[:, None]
    ir = lp(ir, damp)
    ir = np.concatenate([np.zeros((int(pre * SR), 2)), ir])
    return ir / np.sqrt((ir ** 2).sum() / 2)


IRS = {}
def reverb(x, wet=0.25, dur=2.4, damp=5000):
    key = (dur, damp)
    if key not in IRS: IRS[key] = make_ir(dur, damp)
    ir = IRS[key]
    if x.ndim == 1: x = stereo(x)
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)
    return x * (1 - wet) + y * wet * 0.35


def delay(x, t, fb=0.35, mix=0.3, pingpong=True):
    if x.ndim == 1: x = stereo(x)
    d = int(t * SR); y = x.copy(); tap = x.copy(); side = 0
    for k in range(6):
        tap = np.concatenate([np.zeros((d, 2)), tap[:-d]]) * fb
        if pingpong:
            tap = tap[:, ::-1] if k == 0 else tap
        y += tap * mix / fb if k == 0 else tap * mix
    return y


def sat(x, drive=1.5): return np.tanh(x * drive) / np.tanh(drive)
def norm(x, peak=0.9): m = np.max(np.abs(x)) + 1e-9; return x * (peak / m)


def place(buf, x, t, gain=1.0):
    if x.ndim == 1: x = stereo(x)
    i = int(round(t * SR))
    if i < 0: x = x[-i:]; i = 0
    j = min(len(buf), i + len(x))
    if j > i: buf[i:j] += x[:j - i] * gain


# ═════════════════════════════════════════════════════════ EFFETS SONORES
def sfx_whoosh(d=0.75, lo=300, hi=5000, rev=False, pan=True):
    n = int(d * SR); x = rng.standard_normal(n)
    u = np.linspace(0, 1, n)
    curve = np.sin(np.pi * u) ** 1.6 if not rev else np.sin(np.pi * u ** 0.6) ** 2
    fc = lo * (hi / lo) ** (np.sin(np.pi * u) if not rev else 1 - u)
    y = bp_sweep(x, fc, q=0.9) * curve
    y = norm(hp(y, 120)) * 0.8
    pan_c = np.linspace(-0.7, 0.7, n) if pan else np.zeros(n)
    return reverb(np.stack([y * np.sqrt(0.5 * (1 - pan_c)), y * np.sqrt(0.5 * (1 + pan_c))], 1), 0.25, 1.2)


def sfx_boom(d=2.2, f0=62, f1=32, noise=0.5):
    n = int(d * SR); t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 6)
    body = osc(f, n, "sine") * expdec(n, 0.55)
    click = lp(rng.standard_normal(n), 2200) * expdec(n, 0.018) * noise
    sub = sat(body * 1.4 + click, 1.8)
    return reverb(norm(sub, 0.95), 0.3, 2.8, 2500)


def sfx_impact():
    n = int(3.5 * SR)
    b = sfx_boom(3.5, 70, 30, 0.8)
    parts = sum(np.sin(2 * np.pi * f * T(3.5)) * expdec(n, 0.25 + i * 0.1) / (i + 1)
                for i, f in enumerate([183, 297, 431, 612, 845]))
    metal = reverb(norm(hp(parts, 150)) * 0.35, 0.5, 3.2, 6000)
    return norm(b + metal, 0.95)


def sfx_impact_s():
    b = sfx_boom(1.4, 85, 45, 0.6)
    return norm(b, 0.8)


def sfx_riser(d=2.8, small=False):
    n = int(d * SR); u = np.linspace(0, 1, n)
    x = rng.standard_normal(n)
    y = bp_sweep(x, 400 * (12 ** u), q=1.4) * u ** 2.2
    tone = osc(110 * 2 ** (u * 2.5), n, "saw") * u ** 3 * 0.25
    tone = lp(tone, 3000)
    out = norm(y + tone, 0.7 if small else 0.85)
    out[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
    return reverb(out, 0.25, 1.5)


def sfx_ui():
    out = np.zeros(int(0.35 * SR))
    for i, f in enumerate([1046, 1568]):
        s = osc(f, int(0.08 * SR), "sine") * expdec(int(0.08 * SR), 0.03)
        place_m(out, s, i * 0.07)
    return reverb(out * 0.5, 0.3, 0.9, 8000)


def place_m(buf, x, t):
    i = int(t * SR); j = min(len(buf), i + len(x)); buf[i:j] += x[:j - i]


def sfx_click():
    n = int(0.12 * SR)
    c = hp(rng.standard_normal(n), 2000) * expdec(n, 0.004) * 0.6 + osc(2200, n, "sine") * expdec(n, 0.01) * 0.3
    return reverb(c, 0.15, 0.6, 9000)


def sfx_ding():
    n = int(2.6 * SR); t = np.arange(n) / SR
    out = np.zeros(n)
    for f, a in [(880, 1), (1318.5, 0.7), (1760, 0.35)]:
        mod = np.sin(2 * np.pi * f * 1.4 * t) * 1.2 * expdec(n, 0.3)
        out += np.sin(2 * np.pi * f * t + mod) * expdec(n, 0.7) * a
    out[:int(0.25 * SR)] *= 1  # (accord en deux temps)
    return reverb(norm(out, 0.5), 0.35, 2.5, 7000)


def sfx_glitch(d=0.45):
    n = int(d * SR); out = np.zeros(n)
    pos = 0
    while pos < n:
        L = int(rng.uniform(0.015, 0.06) * SR)
        kind = rng.integers(3)
        if kind == 0: seg = np.sign(np.sin(2 * np.pi * rng.uniform(200, 1800) * np.arange(L) / SR)) * 0.4
        elif kind == 1: seg = np.round(rng.standard_normal(L) * 3) / 6
        else: seg = np.zeros(L)
        m_ = max(0, min(L, n - pos)); out[pos:pos + m_] = seg[:m_]
        pos += L
    out = bp(out, 300, 7000) * np.linspace(1, 0.6, n)
    return stereo(norm(out, 0.45), width=0.004)


def sfx_rewind(d=1.1):
    n = int(d * SR); u = np.linspace(0, 1, n)
    f = 300 + 2500 * u ** 1.5
    s = osc(f * (1 + 0.3 * np.sin(2 * np.pi * 28 * u * d)), n, "saw")
    s = bp(s, 400, 6000) * np.sin(np.pi * u) * 0.5
    return reverb(s + hp(rng.standard_normal(n), 3000) * 0.05 * np.sin(np.pi * u), 0.2, 1.0)


def sfx_tick(d=1.6):
    n = int(d * SR); out = np.zeros(n)
    t = 0.0; gap = 0.16
    while t < d - 0.05:
        c = osc(3000, int(0.02 * SR), "sine") * expdec(int(0.02 * SR), 0.004)
        place_m(out, c * 0.35, t); t += gap; gap = max(0.035, gap * 0.85)
    return reverb(out, 0.2, 0.6, 9000)


def sfx_low():
    n = int(3.0 * SR)
    s = osc(41, n, "saw"); s = lp(s, 160) * adsr(n, 0.3, 0.5, 0.6, 1.6)
    return reverb(norm(s + sfx_boom(3.0, 50, 35, 0.2)[:, 0], 0.7), 0.4, 3)


def sfx_shimmer(d=1.4):
    n = int(d * SR); t = np.arange(n) / SR
    out = sum(np.sin(2 * np.pi * f * t) * expdec(n, 0.35) for f in (2093, 2637, 3136, 4186)) / 4
    nz = hp(rng.standard_normal(n), 6000) * np.sin(np.pi * np.linspace(0, 1, n)) * 0.25
    return reverb(norm(out + nz, 0.4), 0.5, 2.0, 10000)


def build_sfx():
    lib = dict(
        whoosh=sfx_whoosh(), swish=sfx_whoosh(0.4, 900, 8000), whoosh_zoom=sfx_whoosh(0.6, 200, 3000),
        whoosh_rev=sfx_whoosh(0.7, 300, 6000, rev=True), boom=sfx_boom(), impact=sfx_impact(),
        impact_s=sfx_impact_s(), riser=sfx_riser(), riser_s=sfx_riser(1.6, small=True), riser_long=sfx_riser(5.0), ui=sfx_ui(),
        click=sfx_click(), ding=sfx_ding(), glitch=sfx_glitch(), glitch_s=sfx_glitch(0.25),
        rewind=sfx_rewind(), tick=sfx_tick(), low=sfx_low(), shimmer=sfx_shimmer(),
    )
    for k, v in lib.items():
        if v.ndim == 1: lib[k] = stereo(v)
    return lib


def ambience(d, kind="city"):
    """Ambiance urbaine : rumeur de trafic, passages de voitures, vagues lointaines."""
    n = int(d * SR)
    brown = np.cumsum(rng.standard_normal(n)); brown = hp(brown - np.convolve(brown, np.ones(4801) / 4801, "same"), 30)
    rumble = norm(lp(brown, 400), 0.25)
    out = stereo(rumble, width=0.011)
    t = 1.0
    while t < d - 4:  # voitures qui passent
        L = rng.uniform(2.5, 4.5); m = int(L * SR); u = np.linspace(0, 1, m)
        car = bp_sweep(rng.standard_normal(m), 250 + 500 * np.sin(np.pi * u), q=0.7) * np.sin(np.pi * u) ** 3
        p = np.linspace(-0.8, 0.8, m) * rng.choice([-1, 1])
        place(out, np.stack([car * np.sqrt(0.5 * (1 - p)), car * np.sqrt(0.5 * (1 + p))], 1), t, 0.12)
        t += rng.uniform(2.0, 6.0)
    if kind == "beach":
        tt = np.arange(n) / SR
        wave = lp(rng.standard_normal(n), 1200) * (0.5 + 0.5 * np.sin(2 * np.pi * tt / 7.5)) ** 3
        out += stereo(norm(wave, 0.18), width=0.007)
    return lp(out, 6000)


# ═════════════════════════════════════════════════════════ MUSIQUE
class Track:
    def __init__(self, d, bpm):
        self.n = int(d * SR) + SR * 4; self.bpm = bpm; self.beat = 60 / bpm
        self.bus = {k: np.zeros((self.n, 2)) for k in ("drums", "bass", "pad", "arp", "lead", "fx")}

    def b(self, beats): return beats * self.beat

    def add(self, bus, x, t, g=1.0): place(self.bus[bus], x, t, g)


def kick(punch=1.0):
    n = int(0.5 * SR); t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 35)
    k = osc(f, n, "sine") * expdec(n, 0.18 * punch) + lp(rng.standard_normal(n), 3000) * expdec(n, 0.004) * 0.3
    return sat(k, 1.6)


def snare(gated=True):
    n = int(0.6 * SR)
    tone = osc(185, n, "sine") * expdec(n, 0.06) * 0.6
    nz = bp(rng.standard_normal(n), 900, 9000) * expdec(n, 0.12)
    s = norm(tone + nz, 0.8)
    if gated:  # « gated reverb » années 80
        r = reverb(s, 0.9, 1.2, 7000)
        g = np.ones(n); g[int(0.22 * SR):] = np.linspace(1, 0, n - int(0.22 * SR)) ** 4
        return r * g[:, None]
    return stereo(s)


def hat(open_=False):
    n = int((0.3 if open_ else 0.06) * SR)
    return hp(rng.standard_normal(n), 7500) * expdec(n, 0.08 if open_ else 0.015) * 0.35


def clap():
    n = int(0.4 * SR); out = np.zeros(n)
    for k in range(3): place_m(out, bp(rng.standard_normal(int(0.01 * SR)), 1000, 5000), k * 0.011)
    out += bp(rng.standard_normal(n), 1000, 5000) * expdec(n, 0.08) * 0.6
    return reverb(out * 0.6, 0.4, 0.9)


def tom(m=45):
    n = int(0.9 * SR); t = np.arange(n) / SR
    f = mtof(m) * (1 + 0.6 * np.exp(-t * 20))
    return reverb(osc(f, n, "sine") * expdec(n, 0.28) * 0.9, 0.35, 2.0)


def pad_chord(notes, d, cutoff=1800, det=0.12, voices=5, att=0.6, rel=1.0, kind="saw"):
    n = int(d * SR); L = np.zeros(n); R = np.zeros(n)
    for m in notes:
        for v in range(voices):
            cents = (v - (voices - 1) / 2) * det / max(1, voices - 1) * 2
            s = osc(mtof(m + cents), n, kind, phase0=rng.random())
            pan = (v / max(1, voices - 1)) * 2 - 1
            L += s * (1 - pan) / 2; R += s * (1 + pan) / 2
    env = adsr(n, att, 0.3, 0.85, rel)
    x = np.stack([L, R], 1) * env[:, None] / (len(notes) * voices) * 2.2
    return lp(x, cutoff)


def pluck(m, d=0.4, cutoff=3500, kind="saw"):
    n = int(d * SR)
    s = osc(mtof(m), n, kind) * 0.6 + osc(mtof(m + 12.04), n, "square") * 0.2
    fc = cutoff * (0.25 + 0.75 * expdec(n, 0.08))
    return lp_sweep(s, fc) * expdec(n, d / 3)


def bass_note(m, d, cutoff=600, kind="saw"):
    n = int(d * SR)
    s = osc(mtof(m), n, kind) * 0.7 + osc(mtof(m - 12), n, "sine") * 0.6
    fc = cutoff * (0.5 + 0.5 * expdec(n, 0.1))
    return lp_sweep(s, fc) * adsr(n, 0.005, 0.1, 0.8, 0.05)


def epiano(m, d=1.2):
    n = int(d * SR); t = np.arange(n) / SR; f = mtof(m)
    mod = np.sin(2 * np.pi * f * t) * 1.8 * expdec(n, 0.25)
    return np.sin(2 * np.pi * f * t + mod) * expdec(n, 0.9) * 0.4 + np.sin(2 * np.pi * f * 2 * t) * expdec(n, 0.2) * 0.08


def lead_note(m, d, vib=True):
    n = int(d * SR); t = np.arange(n) / SR
    v = 1 + (0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.4, 0, 1) if vib else 0)
    s = osc(mtof(m) * v, n, "saw") * 0.5 + osc(mtof(m) * v * 1.005, n, "square") * 0.3
    return lp(s, 2600) * adsr(n, 0.03, 0.2, 0.75, 0.25)


def sidechain(x, beat, n_beats, depth=0.55, t0=0.0):
    n = len(x); t = np.arange(n) / SR - t0
    ph = (t % beat) / beat
    g = 1 - depth * np.exp(-ph * 9) * (t >= 0)
    return x * g[:, None]


def finish(tr, mix, pump=0.0):
    out = np.zeros((tr.n, 2))
    for k, g in mix.items():
        x = tr.bus[k]
        if pump and k in ("pad", "bass", "arp"):
            x = sidechain(x, tr.beat, 0, pump)
        out += x * g
    # égalisation du bus : -4 dB sous 90 Hz, +3 dB de brillance au-dessus de 5 kHz
    out = hp(out, 28)
    out = out - lp(out, 90) * 0.37 + hp(out, 5000) * 0.4
    return out


PROG = {  # (racine midi, intervalles)
    "Am": [57, 60, 64], "F": [53, 57, 60], "C": [48, 52, 55], "G": [55, 59, 62], "Dm": [50, 53, 57],
    "Em": [52, 55, 59], "Fmaj7": [53, 57, 60, 64], "Em7": [52, 55, 59, 62], "Dm7": [50, 53, 57, 60],
    "Cmaj7": [48, 52, 55, 59], "Bb": [46, 50, 53], "Gm": [55, 58, 62], "Eb": [51, 55, 58], "Cm": [48, 51, 55],
    "Ab": [44, 48, 51], "Fm": [53, 56, 60], "Db": [49, 53, 56],
}


def chord_loop(tr, chords, start, end, beats_per=8, cutoff=1800, gain=1.0, voices=5, oct=0, att=0.6):
    t = start; i = 0; L = tr.b(beats_per)
    while t < end - 0.1:
        notes = [x + 12 * oct for x in PROG[chords[i % len(chords)]]]
        tr.add("pad", pad_chord(notes, min(L, end - t) + 0.8, cutoff, att=att, voices=voices), t, gain)
        t += L; i += 1


def bass_line(tr, chords, start, end, pattern, beats_per=8, cutoff=600, gain=1.0):
    """pattern : liste (pos_en_temps, durée_en_temps, décalage_octave)"""
    t = start; i = 0; L = tr.b(beats_per)
    while t < end - 0.1:
        root = PROG[chords[i % len(chords)]][0] - 24
        for (p, d, o) in pattern:
            if p < beats_per and t + tr.b(p) < end:
                tr.add("bass", stereo(bass_note(root + 12 * o, tr.b(d), cutoff)), t + tr.b(p), gain)
        t += L; i += 1


def arp_line(tr, chords, start, end, step=0.5, beats_per=8, cutoff=3500, gain=1.0, oct=1, pattern=(0, 1, 2, 1), dly=True):
    t = start; i = 0; L = tr.b(beats_per)
    while t < end - 0.1:
        notes = PROG[chords[i % len(chords)]]
        k = 0; s = 0.0
        while s < beats_per and t + tr.b(s) < end:
            m = notes[pattern[k % len(pattern)] % len(notes)] + 12 * oct + (12 if pattern[k % len(pattern)] >= len(notes) else 0)
            x = pluck(m, tr.b(step) * 1.6, cutoff)
            tr.add("arp", stereo(x, pan=0.25 * np.sin(k)), t + tr.b(s), gain)
            s += step; k += 1
        t += L; i += 1
    if dly: tr.bus["arp"] = delay(tr.bus["arp"], tr.b(0.75), 0.4, 0.35)


def drum_pattern(tr, start, end, kick_at=(0, 2), snare_at=(1, 3), hats=0.5, gated=True, gain=1.0, open_hat=False, clapz=False):
    t = start; K = kick(); S = snare(gated); H = hat(); HO = hat(True); CL = clap()
    while t < end - 0.05:
        for p in kick_at: tr.add("drums", stereo(K), t + tr.b(p), 0.9 * gain)
        for p in snare_at: tr.add("drums", S, t + tr.b(p), 0.55 * gain)
        if clapz:
            for p in snare_at: tr.add("drums", CL, t + tr.b(p), 0.3 * gain)
        if hats:
            s = 0.0
            while s < 4:
                tr.add("drums", stereo(H, pan=0.3), t + tr.b(s), (0.5 if (s * 2) % 2 else 0.3) * gain)
                s += hats
        if open_hat:
            for p in (0.5, 1.5, 2.5, 3.5): tr.add("drums", stereo(HO, pan=-0.2), t + tr.b(p), 0.25 * gain)
        t += tr.b(4)


def drone(d, m, cutoff=500):
    n = int(d * SR)
    s = (osc(mtof(m), n, "saw") + osc(mtof(m + 0.08), n, "saw") + osc(mtof(m - 12), n, "sine") * 1.5)
    tt = np.arange(n) / SR
    return stereo(lp_sweep(s, cutoff * (1 + 0.5 * np.sin(2 * np.pi * tt / 9))) * 0.3, width=0.01)


# — les 7 ambiances ———————————————————————————————————————————————
def cue_intro(d, marks):
    """Cinématique et mystérieuse : drone, battements sourds, arpège en écho, montée vers le titre."""
    tr = Track(d, 80)
    tr.add("pad", drone(d + 2, 38, 380), 0, 0.9)
    title = marks.get("title", 12.0)
    # pulsations « cœur » avant le titre
    t = 1.2
    while t < title - 0.5:
        tr.add("drums", stereo(kick(1.6)), t, 0.45); tr.add("drums", stereo(kick(1.2)), t + 0.32, 0.25); t += tr.b(2)
    arp_line(tr, ["Dm", "Bb", "F", "C"], 2.4, title, step=1, cutoff=1800, gain=0.35, oct=1, pattern=(0, 2, 1, 2))
    chord_loop(tr, ["Dm", "Bb", "F", "C"], title, d, beats_per=8, cutoff=1500, gain=0.9, oct=0)
    bass_line(tr, ["Dm", "Bb", "F", "C"], title, d, [(0, 1.5, 0), (2, 1, 0), (3.5, 0.5, 1), (4, 1.5, 0), (6, 2, 0)], cutoff=500, gain=0.7)
    drum_pattern(tr, title, d, kick_at=(0, 2.5), snare_at=(1, 3), hats=0.5, gain=0.6)
    arp_line(tr, ["Dm", "Bb", "F", "C"], title, d, step=0.5, cutoff=2600, gain=0.25, oct=1)
    return finish(tr, dict(drums=0.8, bass=0.8, pad=0.8, arp=0.8, lead=0, fx=1), pump=0.4)


def cue_download(d, marks):
    """Montée de tension progressive : pulsation de basse, couches ajoutées, filtre qui s'ouvre."""
    tr = Track(d, 100)
    ch = ["Am", "F", "C", "G"]
    done = marks.get("done", d - 6)
    n = int(done * SR)
    # basse en double-croches avec filtre qui s'ouvre
    t = 0.0; k = 0; step = tr.b(0.25)
    root_seq = [PROG[c][0] - 24 for c in ch]
    while t < done - 0.05:
        bar = int(t / tr.b(8)) % 4
        u = t / done
        x = bass_note(root_seq[bar] + (12 if k % 4 == 2 else 0), step * 0.9, 250 + 2200 * u ** 1.5)
        tr.add("bass", stereo(x), t, 0.55 + 0.25 * u); t += step; k += 1
    chord_loop(tr, ch, 0, done, cutoff=1200, gain=0.6)
    drum_pattern(tr, done * 0.25, done, kick_at=(0, 1, 2, 3), snare_at=(), hats=0.25, gain=0.5)
    drum_pattern(tr, done * 0.55, done, kick_at=(), snare_at=(1, 3), hats=0, gain=0.7)
    arp_line(tr, ch, done * 0.4, done, step=0.25, cutoff=3000, gain=0.25, oct=2)
    # résolution lumineuse au « téléchargement terminé »
    tr.add("pad", pad_chord([57, 60, 64, 69, 72], d - done + 2, 2600, att=0.05, rel=2.5), done, 1.0)
    tr.add("drums", sfx_boom(2.5), done, 0.6)
    return finish(tr, dict(drums=0.8, bass=0.8, pad=0.8, arp=0.8, lead=0, fx=1), pump=0.35)


def cue_hype(d, marks):
    """Documentaire / tension contenue : ostinato, toms sur les dates clés."""
    tr = Track(d, 90)
    ch = ["Dm", "Bb", "Gm", "Am"]
    chord_loop(tr, ch, 0, d, cutoff=1400, gain=0.7)
    arp_line(tr, ch, 0, d, step=0.5, cutoff=2400, gain=0.35, oct=1, pattern=(0, 1, 2, 3, 2, 1))
    bass_line(tr, ch, tr.b(8), d, [(0, 0.75, 0), (1, 0.5, 0), (1.5, 0.5, 1), (2, 0.75, 0), (3, 0.5, 0), (3.5, 0.5, 1),
                                    (4, 0.75, 0), (5, 0.5, 0), (5.5, 0.5, 1), (6, 0.75, 0), (7, 0.5, 0), (7.5, 0.5, 1)], cutoff=700, gain=0.55)
    drum_pattern(tr, tr.b(16), d, kick_at=(0, 2.75), snare_at=(2,), hats=0.5, gain=0.55, gated=True)
    for tm in marks.get("hits", []):
        tr.add("drums", tom(43), tm, 0.7); tr.add("drums", tom(38), tm + tr.b(0.5), 0.5)
    return finish(tr, dict(drums=0.8, bass=0.8, pad=0.8, arp=0.8, lead=0, fx=1), pump=0.3)


def cue_world(d, marks):
    """Vice City : synthwave estivale, batterie gated, basse octaviée, arpèges, mélodie."""
    tr = Track(d, 104)
    ch = ["Fmaj7", "Em7", "Dm7", "Cmaj7"]
    chord_loop(tr, ch, 0, d, cutoff=2400, gain=0.75)
    bass_line(tr, ch, 0, d, [(p * 0.5, 0.4, p % 2) for p in range(16)], cutoff=900, gain=0.55)
    drum_pattern(tr, tr.b(8), d, kick_at=(0, 1, 2, 3), snare_at=(1, 3), hats=0.5, gain=0.7, open_hat=True, clapz=True)
    arp_line(tr, ch, tr.b(16), d, step=0.25, cutoff=3800, gain=0.2, oct=1, pattern=(0, 1, 2, 3, 2, 1, 0, 2))
    mel = [(72, 1.5), (71, 0.5), (69, 2), (67, 1), (69, 3), (None, 0), (76, 1.5), (74, 0.5), (72, 2), (71, 1), (72, 3)]
    t = tr.b(32)
    while t < d - tr.b(16):
        s = t
        for m, L in mel:
            if m is None: continue
            tr.add("lead", stereo(lead_note(m, tr.b(L) * 0.95)), s, 0.22); s += tr.b(L)
        t += tr.b(32)
    tr.bus["lead"] = reverb(delay(tr.bus["lead"], tr.b(0.75), 0.35, 0.3), 0.3, 2.2)
    return finish(tr, dict(drums=0.75, bass=0.8, pad=0.8, arp=0.8, lead=0.9, fx=1), pump=0.45)


def cue_mine(d, marks):
    """Discrète, intime : piano électrique, batterie feutrée, crépitement vinyle."""
    tr = Track(d, 78)
    ch = ["Fmaj7", "Em7", "Dm7", "Cmaj7"]
    t = 0.0; i = 0
    while t < d - 0.1:
        notes = PROG[ch[i % 4]]
        for k, m in enumerate(notes):
            tr.add("pad", stereo(epiano(m + 12, 3.5), pan=-0.3 + 0.2 * k), t + k * 0.06, 0.55)
        tr.add("pad", stereo(epiano(notes[-1] + 24, 1.5), pan=0.3), t + tr.b(2.5), 0.25)
        tr.add("pad", stereo(epiano(notes[1] + 24, 1.5), pan=-0.3), t + tr.b(5.5), 0.2)
        t += tr.b(8); i += 1
    chord_loop(tr, ch, 0, d, cutoff=900, gain=0.35, voices=3)
    bass_line(tr, ch, tr.b(8), d, [(0, 2.5, 0), (3, 1, 0), (4, 2.5, 0), (6.5, 1, 1)], cutoff=350, gain=0.5)
    drum_pattern(tr, tr.b(16), d, kick_at=(0, 2.5), snare_at=(1, 3), hats=0.5, gated=False, gain=0.35)
    n = tr.n; crack = (rng.random(n) > 0.9993) * rng.standard_normal(n) * 0.4 + lp(rng.standard_normal(n), 3000) * 0.006
    tr.bus["fx"] += stereo(hp(crack, 1000), width=0.003)
    tr.bus["pad"] = reverb(tr.bus["pad"], 0.3, 2.0, 4000)
    return finish(tr, dict(drums=0.7, bass=0.8, pad=0.9, arp=0, lead=0, fx=0.8), pump=0.15)


def cue_community(d, marks):
    """Énergie moyenne, chaleureuse, se tend vers le compte à rebours."""
    tr = Track(d, 96)
    ch = ["Am", "F", "C", "G"]
    end = marks.get("zero", d - 3)
    chord_loop(tr, ch, 0, d, cutoff=2000, gain=0.7)
    bass_line(tr, ch, 0, end, [(0, 0.75, 0), (1.5, 0.5, 0), (2, 0.75, 1), (3, 0.5, 0), (4, 0.75, 0), (5.5, 0.5, 0), (6, 1, 1), (7, 0.5, 0)], cutoff=800, gain=0.55)
    drum_pattern(tr, tr.b(8), end - tr.b(8), kick_at=(0, 2), snare_at=(1, 3), hats=0.5, gain=0.6, clapz=True)
    drum_pattern(tr, end - tr.b(8), end, kick_at=(0, 1, 2, 3), snare_at=(0.5, 1.5, 2.5, 3.5), hats=0.25, gain=0.6)
    arp_line(tr, ch, tr.b(16), end, step=0.5, cutoff=3200, gain=0.25, oct=1)
    tr.add("drums", sfx_boom(3.0), end, 0.8)
    return finish(tr, dict(drums=0.8, bass=0.8, pad=0.8, arp=0.8, lead=0, fx=1), pump=0.4)


def cue_outro(d, marks):
    """Épique : toms, chœurs synthétiques, mélodie principale, final sur le logo."""
    tr = Track(d, 96)
    ch = ["Dm", "Bb", "F", "C"]
    big = marks.get("big", 20.0)
    chord_loop(tr, ch, 0, d, cutoff=1600, gain=0.7)
    chord_loop(tr, ch, big, d, cutoff=3200, gain=0.6, oct=1, voices=7, att=0.2)
    bass_line(tr, ch, tr.b(8), d, [(p * 0.5, 0.45, p % 2) for p in range(16)], cutoff=900, gain=0.6)
    drum_pattern(tr, tr.b(8), big, kick_at=(0, 2), snare_at=(), hats=0.5, gain=0.5)
    drum_pattern(tr, big, d - 4, kick_at=(0, 1, 2, 3), snare_at=(1, 3), hats=0.25, gain=0.75, clapz=True, open_hat=True)
    t = big
    while t < d - 4:
        for k, m in enumerate((45, 43, 40)):
            tr.add("drums", tom(m), t + tr.b(3) + k * tr.b(1 / 3), 0.5)
        t += tr.b(8)
    mel = [(74, 2), (72, 1), (69, 1), (70, 3), (69, 1), (65, 2), (67, 2), (72, 2), (69, 2)]
    t = big + tr.b(8)
    while t < d - tr.b(16):
        s = t
        for m, L in mel:
            tr.add("lead", stereo(lead_note(m, tr.b(L) * 0.95)), s, 0.25); s += tr.b(L)
        t += tr.b(16)
    tr.bus["lead"] = reverb(delay(tr.bus["lead"], tr.b(0.75), 0.35, 0.25), 0.35, 2.6)
    arp_line(tr, ch, tr.b(16), d - 4, step=0.25, cutoff=3800, gain=0.2, oct=1)
    final = marks.get("final", d - 8)
    tr.add("drums", sfx_impact(), final, 0.8)
    return finish(tr, dict(drums=0.8, bass=0.8, pad=0.8, arp=0.8, lead=0.9, fx=1), pump=0.35)


CUES = dict(intro=cue_intro, download=cue_download, hype=cue_hype, world=cue_world, mine=cue_mine,
            community=cue_community, outro=cue_outro)
CUE_GAIN = dict(intro=1.0, download=0.95, hype=0.9, world=1.0, mine=0.85, community=0.9, outro=1.0)


# ═════════════════════════════════════════════════════════ MIXAGE
def voice_chain(y, sr):
    """Voix : resample 48k, passe-haut 80 Hz, présence +2 dB, compression douce, de-click."""
    y = signal.resample_poly(y, SR, sr) if sr != SR else y
    y = hp(y, 80)
    b, a = signal.iirpeak(3000, 1.0, fs=SR); pres = signal.lfilter(b, a, y)
    y = y + pres * 0.25
    # compresseur RMS simple (ratio 3:1 au-dessus de -20 dBFS)
    env = np.sqrt(signal.lfilter([0.002], [1, -0.998], y ** 2) + 1e-9)
    lvl = 20 * np.log10(env); over = np.maximum(0, lvl + 20)
    y = y * db(-over * (1 - 1 / 3))
    return y


NO_VOICE = False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    edl = json.loads((ROOT / "build" / "edl.json").read_text())
    total = edl["total"] + 1.0
    N = int(total * SR)
    # ── voix
    vbus = np.zeros((N, 2)); vact = np.zeros(N)
    for v in edl["voice"]:
        y, sr = sf.read(ROOT / "build" / "voice" / f"LINE_{v['n']:02d}.wav")
        y = voice_chain(y, sr)
        place(vbus, stereo(y), v["t"])
        i = int(v["t"] * SR); vact[i:i + len(y)] = 1
    vbus = norm(vbus, 0.7)
    if NO_VOICE:  # version instrumentale : pas de voix, donc pas de ducking (musique/SFX/ambiances à niveau normal)
        vbus[:] = 0; vact[:] = 0
    # ── enveloppe de ducking (attaque 120 ms, relâche 450 ms)
    duck = np.convolve(vact, np.ones(int(0.25 * SR)) / int(0.25 * SR), "same")
    duck = np.clip(duck * 2.5, 0, 1)
    duck = signal.lfilter([0.0006], [1, -0.9994], duck) * 1.0
    duck = np.clip(duck / (duck.max() + 1e-9) * 1.3, 0, 1)
    music_gain = db(-7) * (1 - duck) + db(-21) * duck   # -7 dB en respiration, -21 dB sous la voix
    # ── musique : une ambiance par section, fondus enchaînés de 1,5 s
    mbus = np.zeros((N, 2))
    sfx_list = edl["sfx"]
    for s in edl["sections"]:
        d = s["t1"] - s["t0"] + 1.6
        marks = {}
        rel = lambda x: x - s["t0"]
        if s["key"] == "intro":
            tt = [sh for sh in edl["shots"] if sh["kind"] == "title" and sh["sec"] == "intro"]
            marks["title"] = rel(tt[0]["t0"]) if tt else 12
        if s["key"] == "download":
            dd = [x for x in sfx_list if x["name"] == "ding" and s["t0"] <= x["t"] < s["t1"]]
            marks["done"] = rel(dd[0]["t"]) if dd else d - 6
        if s["key"] == "hype":
            marks["hits"] = [rel(x["t"]) for x in sfx_list if x["name"] == "impact_s" and s["t0"] <= x["t"] < s["t1"]]
        if s["key"] == "community":
            zz = [sh for sh in edl["shots"] if sh["kind"] == "countdown"]
            marks["zero"] = rel(zz[0]["t1"]) - 1.2 if zz else d - 3
        if s["key"] == "outro":
            rv = [sh for sh in edl["shots"] if sh["kind"] == "reveal" and sh["sec"] == "outro"]
            marks["final"] = rel(rv[0]["t0"]) if rv else d - 18
            marks["big"] = rel(edl["voice"][-5]["t"]) if len(edl["voice"]) > 5 else 20
        x = CUES[s["music"]](d, marks)[: int(d * SR)]
        x = norm(x, 0.9) * CUE_GAIN[s["music"]]
        fade_in = int(0.05 * SR); fade_out = int(1.6 * SR)
        x[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
        x[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
        if s["key"] == "outro":
            tail = int(3 * SR); x[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 2
        sf.write(OUT / f"music_{s['key']}.wav", x.astype(np.float32), SR)
        place(mbus, x, s["t0"])
        print("musique", s["key"], round(d, 1), "s")
    mbus = mbus * music_gain[:, None]
    # creux de 2 dB autour de 2,5 kHz dans la musique pour laisser la place à la voix
    b, a = signal.iirpeak(2500, 0.8, fs=SR)
    mbus = mbus - signal.lfilter(b, a, mbus, axis=0) * 0.2
    # ── effets sonores (plus discrets quand la voix parle)
    lib = build_sfx()
    for k, v in lib.items(): sf.write(OUT / f"sfx_{k}.wav", v.astype(np.float32), SR)
    xbus = np.zeros((N, 2))
    base = dict(boom=0.55, impact=0.6, impact_s=0.4, riser=0.35, riser_long=0.42, riser_s=0.25, whoosh=0.35, swish=0.25, whoosh_zoom=0.32,
                whoosh_rev=0.3, ui=0.3, click=0.3, ding=0.35, glitch=0.22, glitch_s=0.18, rewind=0.3, tick=0.3, low=0.45, shimmer=0.25)
    for e in sfx_list:
        i = int(max(0, e["t"]) * SR)
        under_voice = vact[i:i + int(0.3 * SR)].mean() if i < N else 0
        g = base.get(e["name"], 0.3) * (0.6 if under_voice > 0.5 else 1.0)
        place(xbus, lib[e["name"]], e["t"], g)
    # ── ambiances urbaines (Vice City / plages) sous certaines sections
    abus = np.zeros((N, 2))
    for s in edl["sections"]:
        if s["key"] in ("intro", "world", "community"):
            d = s["t1"] - s["t0"]
            amb = ambience(d, "beach" if s["key"] == "world" else "city")
            f = int(2 * SR); amb[:f] *= np.linspace(0, 1, f)[:, None]; amb[-f:] *= np.linspace(1, 0, f)[:, None]
            place(abus, amb, s["t0"], 0.5 if s["key"] != "intro" else 0.7)
    abus *= (db(-4) * (1 - duck) + db(-12) * duck)[:, None]
    # son réel des captures PS5 (ambiance de pièce), calé image par image sur la vidéo
    for sh in edl["shots"]:
        if sh["kind"] == "capture":
            y, sr = sf.read(ROOT / "build" / "cache" / f"{sh['p']['clip']}.wav", always_2d=True)
            y = y[:, :2] if y.shape[1] > 1 else np.repeat(y, 2, 1)
            vis = sh["t1"] - sh["t0"] + sh["p"].get("lead", 0.0) + 0.3
            y = y[:int(vis * SR)]
            f = int(0.15 * SR); y[:f] *= np.linspace(0, 1, f)[:, None]; y[-int(0.4 * SR):] *= np.linspace(1, 0, int(0.4 * SR))[:, None]
            rms = np.sqrt((y ** 2).mean()) + 1e-9
            place(abus, y * (db(-34) / rms), sh["t0"] - sh["p"].get("lead", 0.0))
    sf.write(OUT / f"stem_voice{'_sans_voix' if NO_VOICE else ''}.wav", vbus.astype(np.float32), SR)
    sf.write(OUT / f"stem_music{'_sans_voix' if NO_VOICE else ''}.wav", mbus.astype(np.float32), SR)
    sf.write(OUT / f"stem_sfx{'_sans_voix' if NO_VOICE else ''}.wav", xbus.astype(np.float32), SR)
    sf.write(OUT / f"stem_ambience{'_sans_voix' if NO_VOICE else ''}.wav", abus.astype(np.float32), SR)
    mix = vbus * 1.0 + mbus * 1.0 + xbus * 0.8 + abus * 1.0
    # limiteur doux
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    sf.write(OUT / ("MIX_SANS_VOIX.wav" if NO_VOICE else "MIX.wav"), mix.astype(np.float32), SR)
    print("mix ok", round(len(mix) / SR, 2), "s")


if __name__ == "__main__":
    import sys
    NO_VOICE = "--no-voice" in sys.argv
    main()
