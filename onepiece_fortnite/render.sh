#!/usr/bin/env bash
# =====================================================================
#  Render all frames (resumable: already-rendered frames are skipped,
#  so you can stop / restart at any time).
#
#  usage:  ./render.sh [quality] [start] [end]
#          quality = preview | draft | hd | final   (default: hd)
#
#  Uses the `blender` executable if it exists, otherwise the `bpy`
#  Python module (pip install bpy).  If Blender crashes on a frame the
#  script automatically retries (up to 5 times), resuming where it
#  stopped.
# =====================================================================
set -u
cd "$(dirname "$0")"
QUALITY="${1:-hd}"
START="${2:-1}"
END="${3:-$(python3 -c 'import config; print(config.FRAME_END)')}"

if command -v blender >/dev/null 2>&1; then
  RUN=(blender -b --factory-startup -P build_scene.py --)
else
  RUN=(python3 build_scene.py)
fi

mkdir -p build/frames
for attempt in 1 2 3 4 5; do
  echo "=== render attempt $attempt  quality=$QUALITY  frames $START-$END ==="
  # remove empty placeholder files left by a crash so they get re-rendered
  find build/frames -name 'f_*.png' -size 0 -delete
  OPF_QUALITY="$QUALITY" "${RUN[@]}" --quality "$QUALITY" --render --frames "$START-$END" --no-save \
    && break
  echo "!!! render process failed - retrying in 5 s"
  sleep 5
done

missing=0
for f in $(seq "$START" "$END"); do
  p=$(printf "build/frames/f_%04d.png" "$f")
  [ -s "$p" ] || missing=$((missing + 1))
done
echo "=== done. missing frames: $missing ==="
