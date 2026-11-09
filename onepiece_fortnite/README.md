# ONE PIECE x FORTNITE — "Treasure Hunters" (vertical 3D short)

A 37-second motivational 3D animation (1080x1920, 30 fps, YouTube Shorts) generated
**100 % from code**: Blender Python in background mode for the scene, animation and render,
numpy for the soundtrack, FFmpeg for the final MP4. No assets, no Blender UI.

## Storyboard

| Time | Section | What happens |
|------|---------|--------------|
| 0–6 s | `token` | Dark night ocean; the glowing **Pirate Shop Token** rises out of the water, spinning, with motes and god rays. A blinding flash turns night into sunrise. |
| 6–14 s | `reveal` | Crane-up reveal of the pirate ship (sheep figurehead, straw-hat sail) at sunrise, then a swoop to **Luffy** at the bow. Title: **THE CREW IS ASSEMBLING** |
| 14–22 s | `crew` | **Zoro** (green slashes, 3 swords), **Nami** (lightning, Clima-Tact + tangerine), **Sanji** (flame kick), **Chopper** (sparkles, hop) appear one by one. Title: **ONE BY ONE** + names |
| 22–30 s | `climax` | Luffy winds up, **Gum-Gum** stretches his arm into the sky and punches a giant treasure chest, which explodes into a rain of V-Bucks, tokens and glowing straw-hat symbols. The camera circles the crew. |
| 30–37 s | `finale` | The crew faces the camera: **THE TREASURE IS HERE / USE YOUR TOKEN / CLAIM YOUR CREW**, then **ONE PIECE x FORTNITE** with Luffy's fist raised. |

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
| Section lengths / total duration | `config.py → SECTIONS` (seconds; keep contiguous) |
| Colors (straw-hat yellow, Luffy red, ocean, gold, Zoro green…) | `config.py → COLORS` |
| Crew order, positions on deck, effect type & color | `config.py → CREW` |
| Character looks | `op_lib/characters.py → build_luffy / build_zoro / …` |
| Character poses | `op_lib/characters.py → POSES` (degrees per joint) |
| Camera moves, timing of actions | `build_scene.py → direct_token / direct_reveal / direct_crew / direct_climax / direct_finale` |
| Music (BPM, chords, melody) | `make_music.py → BPM, CHORDS, MELODY` |
| Final encode (CRF, sharpen, vignette) | `assemble.sh` |

## Project structure

```
onepiece_fortnite/
├── config.py            # ALL editable settings (text, timing, colors, crew, quality)
├── build_scene.py       # MAIN Blender script: builds scene + storyboard + render
├── op_lib/
│   ├── utils.py         # keyframe helpers, primitives, materials
│   ├── textures.py      # procedural emblem / token / V-Buck / flag textures (Pillow)
│   ├── world.py         # night→sunrise sky, stars, animated ocean, lights
│   ├── ship.py          # stylized pirate ship (sheep figurehead, sails, flag)
│   ├── characters.py    # puppet rig + Luffy, Zoro, Nami, Sanji, Chopper + poses
│   ├── props.py         # Pirate Shop Token, treasure chest, rain templates
│   ├── effects.py       # motes, light rays, rings, bursts, slashes, lightning, fire, rain
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
