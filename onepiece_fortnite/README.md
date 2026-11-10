# ONE PIECE x FORTNITE — "Pirate Shop Access" (vertical 3D short)

A 36-second cinematic, motivational 3D animation (1080x1920, 30 fps, YouTube Shorts) about the
legendary **Pirate Shop Token**, generated **100 % from code**: Blender Python in background mode
for the scene, animation and render, numpy for the soundtrack, FFmpeg for the final MP4.

## Storyboard

| Time | Section | What happens |
|------|---------|--------------|
| 0–8 s | `storm` | Stormy night, rain, lightning. Opened **empty chests** drift in the waves (the grind). The golden **Pirate Shop Token** rises from the depths, spinning and glowing; the camera orbits and rises with it. **THE RAREST TREASURE**. The token flares → sunrise. |
| 8–16 s | `reveal` | The token floats higher; the camera pulls back to reveal the pirate ship at sunrise. Luffy at the bow looks up at it with determination. Zoro, Nami, Sanji and Chopper appear behind him one by one with energy effects. **ONE DROP CAN CHANGE EVERYTHING** |
| 16–26 s | `climax` | Luffy winds up, **Gum-Gum** stretches his arm and grabs the token → massive golden explosion: V-Bucks, FREE skin cards, Going Merry gliders and the token multiplying fill the sky. The crew celebrates; the camera circles them. **14 DAYS FREE** → **TWO TIMES (2026 + 2027)** |
| 26–36 s | `finale` | The crew faces the camera, the token floating above them. **KEEP OPENING / THE TOKEN IS OUT THERE / CLAIM YOUR CREW**, then **ONE PIECE x FORTNITE — PIRATE SHOP ACCESS**. |

## Quick start

```bash
pip install bpy            # Blender as a Python module (or use a normal Blender install)
./render.sh hd             # render all frames (resumable) -> build/frames/
python3 make_music.py      # soundtrack -> build/soundtrack.wav
./assemble.sh              # -> onepiece_fortnite_short.mp4
```

With a regular Blender install, `render.sh` uses it automatically
(`blender -b -P build_scene.py -- --render ...`).

Useful commands:

```bash
# build the scene and save build/onepiece_fortnite.blend (no render)
python3 build_scene.py
# preview a few frames as JPGs in build/stills/
python3 build_scene.py --quality preview --no-save --stills 60,330,445,740,1080
# render a range only
./render.sh hd 661 900
```

Quality presets (`config.py → QUALITY_PRESETS`, or `--quality`, or `OPF_QUALITY`):

| preset | render size | samples | approx. time / frame (4-core CPU) |
|--------|-------------|---------|------------------|
| preview | 270x480 | 6 | ~4 s |
| draft | 540x960 | 12 | ~11 s |
| hd (default for render.sh) | 720x1280 → upscaled to 1080x1920 | 6 + denoise | ~11 s |
| final | 1080x1920 native, motion blur | 24 | ~60 s+ (use a GPU) |

On a machine with a GPU, set `cy.device = "GPU"` in `build_scene.py → setup_render()` and
use `final`.

## Where to change things

| I want to change… | Edit |
|---|---|
| Any on-screen text, text timing | `config.py → TEXT`, `TEXT_TIMING` |
| Story beats (lightning, crew entrances, grab, explosion, logo) — shared by picture AND music | `config.py → EVENTS` |
| Section lengths / total duration | `config.py → SECTIONS` (seconds; keep contiguous) |
| Colors (straw-hat yellow, Luffy red, ocean, gold, Zoro green…) | `config.py → COLORS` |
| Crew order, positions on deck, effect type & color | `config.py → CREW` |
| Character looks | `op_lib/characters.py → build_luffy / build_zoro / …` |
| Character poses | `op_lib/characters.py → POSES` (degrees per joint) |
| Camera moves, timing of actions | `build_scene.py → direct_storm / direct_reveal / direct_climax / direct_finale` |
| Music (BPM, chords, melody) | `make_music.py → BPM, CHORDS, MELODY` |
| Final encode (CRF, sharpen, vignette) | `assemble.sh` |

## Project structure

```
onepiece_fortnite/
├── config.py            # ALL editable settings (text, timing, colors, crew, quality)
├── build_scene.py       # MAIN Blender script: builds scene + storyboard + render
├── op_lib/
│   ├── utils.py         # keyframe helpers, primitives, materials
│   ├── textures.py      # procedural emblem / token / V-Buck / FREE skin cards / flag (Pillow)
│   ├── world.py         # storm sky (clouds, lightning) → sunrise, stormy→calm ocean, lights
│   ├── ship.py          # stylized pirate ship (sheep figurehead, sails, flag)
│   ├── characters.py    # puppet rig + Luffy, Zoro, Nami, Sanji, Chopper + poses
│   ├── props.py         # Pirate Shop Token, glider, empty chests, treasure-rain templates
│   ├── effects.py       # storm rain, motes, light rays, rings, bursts, slashes, lightning, fire, treasure rain
│   ├── hud.py           # 3D titles locked to the camera, flashes, fades
│   └── camera.py        # camera rig: dolly, cuts, orbit, shake, punch zoom
├── make_music.py        # procedural epic soundtrack (numpy)
├── render.sh            # resumable renderer with auto-retry
├── assemble.sh          # FFmpeg: frames + music -> MP4
└── tools/               # debug helpers (character lineup, contact sheets)
```

## Notes

- Everything is keyframed (no particle caches), so any frame range can be rendered
  independently, in parallel, or resumed after a crash (`render.sh` skips finished frames
  and retries automatically).
- Characters, logos and emblems are original stylized fan-art built from primitives; the
  title texts are plain typography, not the official logos.
