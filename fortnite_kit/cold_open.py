"""Cold open: 10-15 s rapid-fire teaser of rage moments + best moments.

Each moment is a very short cut (0.6-1.8 s) with a punchy effect:
  - "rage": camera shake + zoom punch + red flash + big caption (e.g. "NOOON !!")
  - "best": zoom punch + white flash + golden caption (e.g. "+5 COFFRES")
  - "slowmo": short 0.5x slow motion for the very best moment
Original game audio is kept (rage needs the voice!) and an impact/whoosh SFX
is added on each cut. The intro music runs underneath, ducked.

Usage (from Python):
    from cold_open import build_cold_open
    build_cold_open([
        dict(src="clips/loguetown.mp4", start=83.2, dur=1.2, kind="rage", caption="NOOON !!"),
        dict(src="clips/arlong_park.mp4", start=40.0, dur=1.0, kind="best", caption="+3 COFFRES"),
        ...
    ], music="fortnite_kit/music/0_intro.mp3", out="cold_open.mp4")
"""
import os
import subprocess
import tempfile
import wave
import numpy as np
from PIL import Image

import overlays as O

W, H, FPS = 1920, 1080, 60
SR = 48000


def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _caption_png(text, kind, path):
    if kind == "rage":
        img = O.text_3d(text, 150, (255, 90, 80), (190, 0, 30), tilt=-4, glow_color=O.RED)
    else:
        img = O.text_3d(text, 130, O.YELLOW, O.GOLD, tilt=3, glow_color=O.GOLD)
    img.save(path)
    return img.size


def _sfx(path, kind, dur):
    """Synth whoosh + impact (rage gets a deeper, distorted boom)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(1)
    whoosh_len = int(.18 * SR)
    w = rng.uniform(-1, 1, whoosh_len) * np.linspace(0, 1, whoosh_len) ** 2 * .35
    boom_f = 45 if kind == "rage" else 60
    boom = np.sin(2 * np.pi * np.cumsum(boom_f + 120 * np.exp(-t * 25)) / SR) * np.exp(-t * 5)
    if kind == "rage":
        boom = np.tanh(boom * 3) * .8
    y = np.zeros(n + whoosh_len)
    y[:whoosh_len] += w
    y[whoosh_len:] += boom * .9
    y = y[whoosh_len // 2: whoosh_len // 2 + n]  # impact lands ~90 ms after the cut
    y = (np.clip(y, -1, 1) * 32000).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes(y.tobytes())


def _render_cut(m, i, tmp):
    kind, dur = m.get("kind", "best"), float(m["dur"])
    speed = .5 if kind == "slowmo" else 1.0
    src_dur = dur * speed
    out = os.path.join(tmp, f"cut_{i:02d}.mp4")
    sfx = os.path.join(tmp, f"sfx_{i:02d}.wav")
    _sfx(sfx, "rage" if kind == "rage" else "best", dur)

    # zoom punch: starts at 1.18x and settles to 1.04x in 0.25 s
    z = "(1.04+0.14*exp(-t*12))"
    shake = "(18*sin(t*70)*exp(-t*3))" if kind == "rage" else "0"
    flash_col = "red" if kind == "rage" else "white"
    v = (
        f"[0:v]trim=start={m['start']}:duration={src_dur},setpts=(PTS-STARTPTS)/{speed},"
        f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame,"
        f"crop={W}:{H}:x='(in_w-{W})/2+{shake}':y='(in_h-{H})/2+{shake}*0.6',"
        f"eq=saturation={1.35 if kind != 'slowmo' else 1.2}:contrast=1.08,"
        f"drawbox=c={flash_col}@0.85:t=fill:enable='lt(t,0.06)',"
        f"drawbox=c={flash_col}@0.4:t=fill:enable='between(t,0.06,0.12)',"
        + ("vignette=PI/4," if kind == "rage" else "")
        + "format=yuv420p[v0]"
    )
    inputs = ["-i", m["src"], "-i", sfx]
    if m.get("caption"):
        png = os.path.join(tmp, f"cap_{i:02d}.png")
        cw, ch = _caption_png(m["caption"], kind, png)
        inputs += ["-loop", "1", "-i", png]
        # caption pops in (scale 1.6 -> 1) at 0.08 s, positioned lower third
        v += (f";[2:v]format=rgba,scale=w='{cw}*(1+0.6*exp(-max(t-0.08,0)*14))':h=-1:eval=frame[cap];"
              f"[v0][cap]overlay=x='(W-w)/2':y='H*0.66-h/2':enable='gte(t,0.08)':shortest=1,format=yuv420p[v]")
    else:
        v += ";[v0]null[v]"
    atempo = f"atempo={speed}," if speed != 1 else ""
    a = (f"[0:a]atrim=start={m['start']}:duration={src_dur},asetpts=PTS-STARTPTS,{atempo}"
         f"aresample={SR},volume={1.6 if kind == 'rage' else 1.1}[ga];"
         f"[1:a]aresample={SR}[fx];[ga][fx]amix=inputs=2:normalize=0,atrim=duration={dur},"
         f"apad=whole_dur={dur}[a]")
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", v + ";" + a, "-map", "[v]", "-map", "[a]",
          "-t", str(dur), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), out])
    return out


def build_cold_open(moments, music=None, out="cold_open.mp4", music_gain=0.35):
    total = sum(float(m["dur"]) for m in moments)
    if not 9.5 <= total <= 15.5:
        print(f"warning: cold open is {total:.1f}s (target 10-15 s)")
    with tempfile.TemporaryDirectory() as tmp:
        cuts = [_render_cut(m, i, tmp) for i, m in enumerate(moments)]
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            f.writelines(f"file '{c}'\n" for c in cuts)
        joined = os.path.join(tmp, "joined.mp4")
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
        if music:
            # game audio leads; music sits underneath and swells in the last 0.5 s
            _run(["ffmpeg", "-y", "-i", joined, "-i", music, "-filter_complex",
                  f"[1:a]atrim=duration={total},volume={music_gain},afade=t=in:d=0.2,"
                  f"volume='if(gt(t,{total - 0.5}),2.2,1)':eval=frame[m];"
                  f"[0:a][m]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]",
                  "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out])
        else:
            os.replace(joined, out)
    print(f"cold open written: {out} ({total:.1f}s, {len(moments)} cuts)")
    return out


if __name__ == "__main__":
    # Demo with synthetic footage so the effects can be checked without real clips.
    demo_dir = tempfile.mkdtemp()
    srcs = []
    for k, pat in enumerate(["testsrc2", "mandelbrot", "life"]):
        p = os.path.join(demo_dir, f"src{k}.mp4")
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"{pat}=s=1280x720:r=30", "-f", "lavfi",
              "-i", f"sine=f={300 + 200 * k}:sample_rate=48000", "-t", "8", "-c:v", "libx264",
              "-preset", "ultrafast", "-c:a", "aac", "-shortest", p])
        srcs.append(p)
    here = os.path.dirname(os.path.abspath(__file__))
    build_cold_open([
        dict(src=srcs[0], start=1, dur=1.2, kind="rage", caption="NOOON !!"),
        dict(src=srcs[1], start=2, dur=1.0, kind="best", caption="+3 COFFRES"),
        dict(src=srcs[2], start=0.5, dur=0.8, kind="rage", caption="C'EST PAS POSSIBLE"),
        dict(src=srcs[0], start=4, dur=1.0, kind="best"),
        dict(src=srcs[1], start=5, dur=0.9, kind="rage", caption="JE RAGE"),
        dict(src=srcs[2], start=3, dur=1.1, kind="best", caption="TROP RAPIDE"),
        dict(src=srcs[0], start=6, dur=0.8, kind="best", caption="+2"),
        dict(src=srcs[1], start=3.5, dur=1.0, kind="rage", caption="MAIS NON !"),
        dict(src=srcs[2], start=5, dur=1.0, kind="best", caption="LEGENDAIRE"),
        dict(src=srcs[0], start=2, dur=2.2, kind="slowmo", caption="7 COFFRES"),
    ], music=os.path.join(here, "music", "0_intro.mp3"), out=os.path.join(demo_dir, "cold_open_demo.mp4"))
    print(demo_dir)
