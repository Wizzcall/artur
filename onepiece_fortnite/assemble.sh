#!/usr/bin/env bash
# =====================================================================
#  Assemble rendered PNG frames + soundtrack into the final MP4.
#    - upscales to 1080x1920 (lanczos) if frames were rendered smaller
#    - light sharpen + subtle vignette for a cinematic finish
#    - H.264 High, CRF 16, yuv420p, AAC 320k, +faststart (YouTube Shorts ready)
#  usage: ./assemble.sh            (reads paths from config.py)
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"

eval "$(python3 - <<'EOF'
import config as C
print(f'FPS={C.FPS}; W={C.WIDTH}; H={C.HEIGHT}; DUR={C.DURATION}')
print(f'FRAMES="{C.FRAMES_DIR}"; MUSIC="{C.MUSIC_FILE}"; OUT="{C.OUTPUT_MP4}"')
EOF
)"

# make sure the soundtrack exists
[ -f "$MUSIC" ] || python3 make_music.py

# fill any missing frame with the previous one (never break the timeline)
python3 - <<EOF
import os, shutil
d = "$FRAMES"
frames = sorted(f for f in os.listdir(d) if f.startswith("f_") and f.endswith(".png"))
nums = [int(f[2:6]) for f in frames]
last = None
for n in range(1, max(nums) + 1):
    p = os.path.join(d, f"f_{n:04d}.png")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        last = p
    elif last:
        print("filling missing frame", n)
        shutil.copy(last, p)
EOF

ffmpeg -hide_banner -y \
  -framerate "$FPS" -start_number 1 -i "$FRAMES/f_%04d.png" \
  -i "$MUSIC" \
  -filter_complex "[0:v]scale=${W}:${H}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,vignette=angle=PI/5:mode=forward,format=yuv420p[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf 16 -profile:v high -pix_fmt yuv420p \
  -r "$FPS" -g $((FPS * 2)) -movflags +faststart \
  -c:a aac -b:a 320k -ar 48000 \
  -t "$DUR" \
  "$OUT"

echo "Wrote $OUT"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of compact "$OUT"
