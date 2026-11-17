"""
Voix off de travail (TTS neuronal Kokoro, voix française « ff_siwis »).

    python tts.py --models <dossier kokoro> [--speed 0.97]

Produit build/voice/LINE_xx.wav (24 kHz mono) + build/voice/voice.json
(durées et découpage par phrase, utilisés pour synchroniser images,
sous-titres et effets sonores).

POUR UTILISER VOTRE PROPRE VOIX : enregistrez une prise par ligne
(même numérotation, voir GTA6_VOIX_OFF.txt) dans voice_user/LINE_xx.wav.
Lancez `python tts.py --user voice_user` : les durées seront mesurées sur
vos fichiers et tout le montage se recale automatiquement.
"""
import argparse, json, re
from pathlib import Path
import numpy as np
import soundfile as sf

from narration import SECTIONS, SAY

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build" / "voice"


def respell(t):
    for a, b in SAY:
        t = re.sub(r"(?<![\w'])" + re.escape(a) + r"(?![\w])", b, t)
    return t


def sentences(text):
    parts = re.split(r"(?<=[.!?…:])\s+", text.strip())
    return [p for p in parts if p]


def trim(a, sr, thr=0.008):
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] - int(0.02 * sr)); e = min(len(a), idx[-1] + int(0.06 * sr))
    return a[s:e]


def all_lines():
    n = 0
    for s in SECTIONS:
        for ln in s["lines"]:
            if ln["text"]:
                n += 1
                yield n, s, ln


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=None)
    ap.add_argument("--speed", type=float, default=0.97)
    ap.add_argument("--user", default=None, help="dossier de prises voix réelles LINE_xx.wav")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    if a.user:
        for n, s, ln in all_lines():
            f = Path(a.user) / f"LINE_{n:02d}.wav"
            y, sr = sf.read(f, always_2d=False)
            if y.ndim > 1: y = y.mean(1)
            sf.write(OUT / f"LINE_{n:02d}.wav", y, sr)
            sents = sentences(ln["text"])
            tot = sum(len(x) for x in sents)
            d = len(y) / sr; acc = 0; parts = []
            for x in sents:  # répartition au prorata des caractères
                parts.append(dict(text=x, start=acc, dur=d * len(x) / tot)); acc += d * len(x) / tot
            meta[n] = dict(dur=d, sents=parts, sr=sr)
    else:
        from kokoro_onnx import Kokoro
        k = Kokoro(f"{a.models}/kokoro-v1.0.onnx", f"{a.models}/voices-v1.0.bin")
        for n, s, ln in all_lines():
            sents = sentences(ln["text"])
            chunks, parts, t = [], [], 0.0
            for i, x in enumerate(sents):
                y, sr = k.create(respell(x), voice="ff_siwis", speed=a.speed, lang="fr-fr")
                y = trim(np.asarray(y, np.float32), sr)
                gap = 0.0 if i == len(sents) - 1 else (0.42 if x.endswith(("…", ":")) else 0.30)
                parts.append(dict(text=x, start=t, dur=len(y) / sr))
                chunks += [y, np.zeros(int(gap * sr), np.float32)]
                t += len(y) / sr + gap
            y = np.concatenate(chunks)
            sf.write(OUT / f"LINE_{n:02d}.wav", y, sr)
            meta[n] = dict(dur=len(y) / sr, sents=parts, sr=sr)
            print(f"LINE_{n:02d} {len(y)/sr:6.2f}s  {ln['text'][:60]}")
    (OUT / "voice.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print("total voix", sum(m["dur"] for m in meta.values()))


if __name__ == "__main__":
    main()
