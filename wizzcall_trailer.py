#!/usr/bin/env python3
"""Wizzcall Fortnite trailer: speaker subtitles (ASS) + Apple-style emoji overlays.

libass cannot draw colour emoji, so:
  * dialogue.ass       -> full subtitle file WITH emojis (portable, for editors/players)
  * dialogue_burn.ass  -> same events without emoji glyphs, burned with ffmpeg's ass=
  * Apple emoji PNGs   -> overlaid left/right of each line, positioned from the real
                          libass bounding box of every event (measured by rendering it).

Usage: python3 wizzcall_trailer.py SRC.mov OUT.mp4 FONTS_DIR EMOJI_DIR WORK_DIR [CLIP1 CLIP2]

With CLIP1/CLIP2 the middle gameplay band is rebuilt from those clips, cut to the
dialogue (EDIT below). The voices/audio always come from SRC, untouched.
"""
import subprocess, sys, os
from PIL import Image, ImageChops

SRC, OUT, FONTS, EMOJI, WORK = sys.argv[1:6]
CLIPS = sys.argv[6:8]

# Gameplay edit for the middle band: (clip index, in, out) in clip timestamps,
# laid end to end from t=0 (sum = 30.70 s). Aligned on the dialogue:
EDIT = [
    (0, 2.0, 7.2),    # 0.0-5.2   intro "ça va / t'as eu le jeton ?" -> chest on the boat + run
    (1, 7.0, 13.6),   # 5.2-11.8  "j'arrive pas à voir les meilleurs spots" -> searching a dark hut
    (1, 2.0, 4.4),    # 11.8-14.2 "ouvrir un maximum de coffres" -> chest opening
    (0, 7.0, 10.8),   # 14.2-18.0 "vidéo de Wizzcall... incroyable" -> walks in, chest
    (0, 17.0, 19.2),  # 18.0-24.1 "les cinq meilleurs endroits... coffres" -> chest montage
    (0, 22.6, 24.6),
    (0, 27.9, 29.8),
    (1, 17.0, 20.4),  # 24.1-27.5 "Non / Jure ? / Je te jure / Allez viens"
    (1, 22.0, 25.2),  # 27.5-30.7 "Vas-y, carré, on y va !" + CTA -> sprint
]
W, H = 720, 1280
EMO_SIZE = 64
EMO_GAP = 10

E_GAME, E_TALK, E_FIRE, E_UP = "🎮", "🗣️", "🔥", "👆"
EMO_FILE = {E_GAME: "1f3ae.png", E_TALK: "1f5e3-fe0f.png",
            E_FIRE: "1f525.png", E_UP: "1f446.png"}

# (start, end, style, text, left emojis, right emojis, marginV override)
# Ends are trimmed to the next line's start when they would overlap, so lines never
# stack/jump; the only intentional overlap (both speakers at 1.10-2.20) gets its own row.
EVENTS = [
    (1.00, 2.20, "Speaker0", "Ouais,", [E_GAME], [E_GAME], 375),
    (1.10, 2.50, "Speaker1", "mon gars, ça va, continue mon con.", [E_TALK], [E_TALK], None),
    (2.50, 3.20, "Speaker1", "Ouais, ça va, hein.", [E_TALK], [E_TALK], None),
    (3.20, 5.20, "Speaker1", "T'as eu le truc des jetons ?\\NEst-ce que t'as eu le jeton au moins ?", [E_TALK], [E_TALK], None),
    (5.20, 11.80, "Speaker0", "J'arrive vraiment pas à voir les meilleurs spots\\Navec les meilleurs endroits...", [E_GAME], [E_GAME], None),
    (11.80, 14.20, "Speaker1", "...pour ouvrir un maximum de coffres.\\NC'est ça qui m'empêche vraiment d'avoir le jeton.", [E_TALK], [E_TALK], None),
    (14.20, 18.00, "Speaker1", "Hé, tu sais que j'ai vu une vidéo de Wizzcall\\Npassé là, et j'ai juré, il a l'air vraiment incroyable.", [E_TALK], [E_TALK], None),
    (18.00, 24.10, "Speaker1", "Ça dit les cinq meilleurs endroits\\Npour avoir le maximum de coffres à ouvrir\\Nen une seule partie.", [E_TALK], [E_TALK], None),
    (24.10, 24.90, "Speaker1", "Non...", [E_TALK], [E_TALK], None),
    (24.90, 25.20, "Speaker0", "Jure ?", [E_GAME], [E_GAME], None),
    (25.20, 26.20, "Speaker1", "Je te jure, c'est vrai.", [E_TALK], [E_TALK], None),
    (26.20, 27.50, "Speaker1", "Allez, viens voir les vidéos !", [E_TALK], [E_TALK], None),
    (27.80, 29.50, "Speaker0", "Vas-y, carré, on y va !", [E_GAME], [E_FIRE, E_GAME], None),
    (28.50, 30.70, "CTA", "REGARDE LA VIDÉO COMPLÈTE\\N{\\c&H0000E5FF&}CHAÎNE WIZZCALL • JETON PIRATE", [E_UP], [E_UP], None),
]

# Pop-in: quick fade + scale 85% -> 100% in 120 ms (overrides prepended per event)
POP = r"{\fad(80,60)\fscx85\fscy85\t(0,120,\fscx100\fscy100)}"
CTA_POP = r"{\fad(120,0)\fscx70\fscy70\t(0,180,\fscx108\fscy108)\t(180,320,\fscx100\fscy100)}"

HEADER = f"""[Script Info]
Title: Wizzcall - Jeton Pirate trailer
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Speaker0,Anton,50,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,4.5,3,2,95,95,290,1
Style: Speaker1,Anton,50,&H0000E5FF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,4.5,3,2,95,95,290,1
Style: CTA,Anton,44,&H00FFFFFF,&H000000FF,&H001A1AE6,&H64000000,0,0,0,0,100,100,1.5,0,3,10,0,2,95,95,95,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def dialogue(ev, with_emoji):
    s, e, style, text, left, right, mv = ev
    pop = CTA_POP if style == "CTA" else POP
    if with_emoji:
        text = f"{''.join(left)} {text} {''.join(right)}"
    name = {"Speaker0": "Gamer", "Speaker1": "Pote", "CTA": "CTA"}[style]
    layer = 1 if style == "CTA" else 0
    return f"Dialogue: {layer},{ts(s)},{ts(e)},{style},{name},0,0,{mv or 0},,{pop}{text}\n"


def write_ass(path, events, with_emoji):
    with open(path, "w", encoding="utf-8") as f:
        f.write(HEADER + "".join(dialogue(ev, with_emoji) for ev in events))


def measure(ev, idx):
    """Render one event alone over magenta and return its pixel bbox (libass truth)."""
    p = os.path.join(WORK, f"m{idx}.ass")
    write_ass(p, [ev], False)
    png = os.path.join(WORK, f"m{idx}.png")
    t = min(ev[0] + 0.4, ev[1] - 0.05)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"color=0xFF00FF:s={W}x{H}:d=31:r=30",
                    "-vf", f"ass={p}:fontsdir={FONTS}", "-ss", f"{t:.2f}",
                    "-frames:v", "1", png], check=True)
    im = Image.open(png).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 0, 255))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 40 else 0)
    return diff.getbbox()


def main():
    os.makedirs(WORK, exist_ok=True)
    out_dir = os.path.dirname(os.path.abspath(OUT))
    write_ass(os.path.join(out_dir, "dialogue.ass"), EVENTS, True)
    burn = os.path.join(WORK, "dialogue_burn.ass")
    write_ass(burn, EVENTS, False)

    # Emoji placements from measured boxes
    placements = []  # (emoji, x, y, start, end)
    for i, ev in enumerate(EVENTS):
        x0, y0, x1, y1 = measure(ev, i)
        cy = (y0 + y1) // 2 - EMO_SIZE // 2
        for k, em in enumerate(reversed(ev[4])):
            placements.append((em, x0 - EMO_GAP - EMO_SIZE * (k + 1) - 4 * k, cy, ev[0], ev[1]))
        for k, em in enumerate(ev[5]):
            placements.append((em, x1 + EMO_GAP + (EMO_SIZE + 4) * k, cy, ev[0], ev[1]))
        print(f"event {i:2d} bbox=({x0},{y0},{x1},{y1})")

    used = sorted({p[0] for p in placements}, key=list(EMO_FILE).index)
    inputs = ["-i", SRC]
    for em in used:
        inputs += ["-i", os.path.join(EMOJI, EMO_FILE[em])]

    # Grade: 3% punch-in zoom, light contrast/saturation, gentle sharpen, then subs.
    grade = "eq=contrast=1.07:saturation=1.15:brightness=0.01,unsharp=5:5:0.45:5:5:0,"
    if CLIPS:
        clip_in = len(inputs) // 2
        for c in CLIPS:
            inputs += ["-i", c]
        fc = []
        for n, (ci, a, b) in enumerate(EDIT):
            fc.append(f"[{clip_in + ci}:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=30,"
                      f"scale=1280:720:flags=lanczos,setsar=1[g{n}]")
        fc.append("".join(f"[g{n}]" for n in range(len(EDIT))) +
                  f"concat=n={len(EDIT)}:v=1:a=0,split[gb][gf]")
        # Vertical layout: blurred/darkened gameplay as background, sharp 16:9 band centred
        band_h = W * 9 // 16
        fc.append(f"[gb]scale=-2:{H},crop={W}:{H},boxblur=24:2,eq=brightness=-0.12:saturation=1.2[bg]")
        fc.append(f"[gf]scale={int(W * 1.03)}:-2:flags=lanczos,crop={W}:{band_h}[fg]")
        fc.append(f"[bg][fg]overlay=0:(H-h)/2,{grade}ass={burn}:fontsdir={FONTS},format=yuv420p[v0]")
    else:
        fc = [f"[0:v]scale=742:1320:flags=lanczos,crop={W}:{H},{grade}"
              f"ass={burn}:fontsdir={FONTS},format=yuv420p[v0]"]
    counts = {em: sum(1 for p in placements if p[0] == em) for em in used}
    for j, em in enumerate(used, start=1):
        outs = "".join(f"[e{j}_{k}]" for k in range(counts[em]))
        fc.append(f"[{j}:v]scale={EMO_SIZE}:{EMO_SIZE}:flags=lanczos,format=rgba,split={counts[em]}{outs}")
    seen = {em: 0 for em in used}
    cur = "v0"
    for n, (em, x, y, s, e) in enumerate(placements):
        j = used.index(em) + 1
        lab = f"e{j}_{seen[em]}"
        seen[em] += 1
        nxt = f"v{n + 1}"
        fc.append(f"[{cur}][{lab}]overlay=x={x}:y={y}:enable='between(t,{s:.2f},{e:.2f})'[{nxt}]")
        cur = nxt

    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning", "-stats"] + inputs +
           ["-filter_complex", ";".join(fc), "-map", f"[{cur}]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-t", "30.70", "-movflags", "+faststart", OUT])
    with open(os.path.join(out_dir, "wizzcall_ffmpeg_cmd.txt"), "w") as f:
        f.write(" ".join(f"'{c}'" if any(ch in c for ch in " ;[]'(),") else c for c in cmd) + "\n")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
