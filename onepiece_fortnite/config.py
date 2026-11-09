"""
=====================================================================
  ONE PIECE x FORTNITE  -  "Treasure Hunters"  motivational short
  CENTRAL CONFIG  -  edit THIS file to change text, timing, colors,
  characters and render quality.  Every other script reads from here.
=====================================================================

All timings are expressed in SECONDS and converted to frames with
`sec()`, so you can stretch / shrink any section without touching
the animation code.  Keep the sections contiguous (each one starts
where the previous one ends).
"""

import os

# ---------------------------------------------------------------------
# 1. VIDEO FORMAT
# ---------------------------------------------------------------------
FPS = 30
WIDTH = 1080            # final video width  (vertical 9:16)
HEIGHT = 1920           # final video height

# ---------------------------------------------------------------------
# 2. STORY SECTIONS  (seconds)  -  start, end
#    Total length = SECTIONS["finale"][1]  (37 s by default)
# ---------------------------------------------------------------------
SECTIONS = {
    "token":    (0.0, 6.0),    # night ocean, Pirate Shop Token rises
    "reveal":   (6.0, 14.0),   # sunrise, ship + Luffy reveal
    "crew":     (14.0, 22.0),  # crew members appear one by one
    "climax":   (22.0, 30.0),  # Gum-Gum punch, treasure chest explosion
    "finale":   (30.0, 37.0),  # final texts + logo
}
DURATION = SECTIONS["finale"][1]


def sec(t):
    """Seconds -> frame number (frame 1 == t=0)."""
    return int(round(t * FPS)) + 1


FRAME_START = 1
FRAME_END = sec(DURATION) - 1          # 37 s -> frames 1..1110

# ---------------------------------------------------------------------
# 3. ON-SCREEN TEXT   (change freely - the layout auto-fits the width)
# ---------------------------------------------------------------------
TEXT = {
    "assembling": "THE CREW IS\nASSEMBLING",
    "one_by_one": "ONE BY ONE",
    "final_lines": [
        "THE TREASURE\nIS HERE",
        "USE YOUR\nTOKEN",
        "CLAIM YOUR\nCREW",
    ],
    "logo_top": "ONE PIECE",
    "logo_x": "x",
    "logo_bottom": "FORTNITE",
    "logo_sub": "TREASURE HUNTERS",
    "token_face": "PIRATE\nSHOP",      # engraved on the token texture
}

# Show the character name under each crew member in the "crew" section
SHOW_CREW_NAMES = True

# Text timing (seconds, absolute)
TEXT_TIMING = {
    "assembling": (9.6, 13.7),
    "one_by_one": (14.15, 21.8),
    "final_lines": [(30.35, 34.4), (31.55, 34.4), (32.75, 34.4)],
    "logo": (34.55, DURATION),
}

# Fonts (first existing file wins, otherwise Blender's built-in font)
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_ITALIC_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/InterDisplay-BlackItalic.otf",
    "/usr/share/fonts/opentype/inter/Inter-BlackItalic.otf",
] + FONT_CANDIDATES

# ---------------------------------------------------------------------
# 4. COLOR PALETTE  (linear-ish RGB 0..1)
# ---------------------------------------------------------------------
COLORS = {
    "straw_yellow": (1.00, 0.78, 0.18),
    "luffy_red":    (0.85, 0.05, 0.05),
    "ocean_blue":   (0.02, 0.18, 0.42),
    "gold":         (1.00, 0.66, 0.12),
    "zoro_green":   (0.10, 0.62, 0.20),
    "nami_orange":  (1.00, 0.42, 0.05),
    "sanji_blonde": (1.00, 0.85, 0.35),
    "chopper_pink": (1.00, 0.35, 0.60),
    "vbuck_blue":   (0.10, 0.45, 1.00),
    "white":        (1.0, 1.0, 1.0),
    "black":        (0.01, 0.01, 0.012),
    "skin":         (0.93, 0.66, 0.50),
    "night_sky_top":     (0.002, 0.004, 0.018),
    "night_sky_horizon": (0.010, 0.030, 0.090),
    "dawn_sky_top":      (0.03, 0.16, 0.70),
    "dawn_sky_horizon":  (1.00, 0.42, 0.12),
    "text_top":     (1.00, 0.92, 0.35),    # gradient top of title text
    "text_bottom":  (1.00, 0.45, 0.02),    # gradient bottom of title text
    "text_outline": (0.05, 0.01, 0.0),
}

# ---------------------------------------------------------------------
# 5. CREW   (order = order of appearance in the "crew" section)
#    builder : function name in op_lib/characters.py
#    pos     : (x, y) position on the ship deck  (+Y = bow / camera side)
#    fx      : appearance effect  ("slash", "lightning", "fire", "sparkle")
#    color   : effect color
# ---------------------------------------------------------------------
CREW = [
    {"name": "ZORO",    "builder": "build_zoro",    "pos": (-1.85, 3.6),
     "fx": "slash",     "color": COLORS["zoro_green"]},
    {"name": "NAMI",    "builder": "build_nami",    "pos": (1.85, 3.6),
     "fx": "lightning", "color": (0.25, 0.65, 1.0)},
    {"name": "SANJI",   "builder": "build_sanji",   "pos": (-3.2, 2.4),
     "fx": "fire",      "color": (1.0, 0.35, 0.05)},
    {"name": "CHOPPER", "builder": "build_chopper", "pos": (1.6, 4.9),
     "fx": "sparkle",   "color": COLORS["chopper_pink"]},
]
LUFFY_POS = (0.0, 6.4)       # Luffy stands at the bow

# ---------------------------------------------------------------------
# 6. RENDER QUALITY
#    Pick a preset with the env var  OPF_QUALITY=preview|draft|final
#    (or edit DEFAULT_QUALITY).  'scale' is the % of 1080x1920 rendered;
#    FFmpeg upscales to full 1080x1920 at assembly time.
# ---------------------------------------------------------------------
QUALITY_PRESETS = {
    #            scale  samples  motion_blur
    "preview": dict(scale=25, samples=6,  motion_blur=False),
    "draft":   dict(scale=50, samples=12, motion_blur=False),
    "hd":      dict(scale=67, samples=6, motion_blur=False),    # 720x1280 -> upscaled
    "final":   dict(scale=100, samples=24, motion_blur=True),
}
DEFAULT_QUALITY = "final"
QUALITY = os.environ.get("OPF_QUALITY", DEFAULT_QUALITY)

# Ocean detail (higher = nicer waves, slower)
OCEAN_RESOLUTION = 10

# ---------------------------------------------------------------------
# 7. PATHS
# ---------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ROOT, "build")
TEXTURE_DIR = os.path.join(BUILD_DIR, "textures")
FRAMES_DIR = os.path.join(BUILD_DIR, "frames")
BLEND_FILE = os.path.join(BUILD_DIR, "onepiece_fortnite.blend")
MUSIC_FILE = os.path.join(BUILD_DIR, "soundtrack.wav")
OUTPUT_MP4 = os.path.join(ROOT, "onepiece_fortnite_short.mp4")

SEED = 7    # random seed for particles - change for a different "shuffle"
