"""Find rage / hype candidates in raw clips from the audio track.

A "rage" moment = the voice band (250-3500 Hz) gets much louder than the
clip's usual level for a short burst (shouting). We score each burst by how far
above the rolling median it goes and how long it lasts, then return the top N
as cut suggestions (start, dur) ready for cold_open.build_cold_open().

Usage: python3 detect_moments.py clip1.mp4 [clip2.mp4 ...]
"""
import subprocess
import sys
import numpy as np

SR = 16000
HOP = 0.05  # 50 ms frames


def voice_rms(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR),
         "-af", "highpass=f=250,lowpass=f=3500", "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop = int(HOP * SR)
    n = len(x) // hop
    frames = x[: n * hop].reshape(n, hop)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(1)) + 1e-6)


def rage_candidates(path, top=6, min_gap=4.0):
    db = voice_rms(path)
    win = int(10 / HOP)  # 10 s rolling median = "normal" level
    pad = np.pad(db, win // 2, mode="edge")
    base = np.array([np.median(pad[i:i + win]) for i in range(0, len(db))])
    excess = db - base
    loud = excess > 12  # dB above usual level
    events, i = [], 0
    while i < len(loud):
        if loud[i]:
            j = i
            while j < len(loud) and (loud[j] or (j + 4 < len(loud) and loud[j:j + 4].any())):
                j += 1
            dur = (j - i) * HOP
            if dur >= 0.25:
                score = float(excess[i:j].max() * np.sqrt(dur))
                events.append((score, i * HOP, dur))
            i = j
        i += 1
    events.sort(reverse=True)
    picked = []
    for score, t, dur in events:
        if all(abs(t - p[1]) > min_gap for p in picked):
            picked.append((score, t, dur))
        if len(picked) >= top:
            break
    # cut: start 0.4 s before the shout (show the cause), keep 1-1.8 s
    return [dict(src=path, start=max(0, round(t - 0.4, 2)), dur=round(min(1.8, max(1.0, d + 0.6)), 2),
                 kind="rage", score=round(s, 1)) for s, t, d in sorted(picked, key=lambda p: p[1])]


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p)
        for c in rage_candidates(p):
            print(f"  {c['start']:8.2f}s  dur {c['dur']:.2f}s  score {c['score']}")
