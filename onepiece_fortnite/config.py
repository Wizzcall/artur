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
#    Total length = SECTIONS["finale"][1]  (36 s by default)
# ---------------------------------------------------------------------
SECTIONS = {
    "storm":    (0.0, 8.0),    # stormy night, rain, the token rises from the depths
    "reveal":   (8.0, 16.0),   # sunrise, Going Merry, Luffy looks up, crew appears
    "climax":   (16.0, 26.0),  # Gum-Gum grab, golden explosion, treasure rain
    "finale":   (26.0, 36.0),  # crew + floating token, final titles
}
DURATION = SECTIONS["finale"][1]


def sec(t):
    """Seconds -> frame number (frame 1 == t=0)."""
    return int(round(t * FPS)) + 1


FRAME_START = 1
FRAME_END = sec(DURATION) - 1          # 36 s -> frames 1..1080

# Key story moments (seconds).  Used by BOTH the animation and the music,
# so picture and sound always stay in sync.
EVENTS = {
    "lightning":   [1.7, 4.4, 6.6],          # storm lightning strikes
    "dawn_flash":  7.85,                     # token flares -> sunrise
    "crew_appear": [11.9, 12.8, 13.7, 14.6],  # Zoro, Nami, Sanji, Chopper
    "windup":      16.5,
    "launch":      17.1,                     # Gum-Gum arm shoots out
    "grab":        17.6,                     # fist closes on the token
    "explosion":   17.75,                    # golden explosion
    "logo":        33.4,
}

# ---------------------------------------------------------------------
# 3. ON-SCREEN TEXT   (change freely - the layout auto-fits the width)
# ---------------------------------------------------------------------
TEXT = {
    "rarest": "THE RAREST\nTREASURE",
    "one_drop": "ONE DROP CAN\nCHANGE EVERYTHING",
    "days_free": "14 DAYS\nFREE",
    "two_times": "TWO TIMES",
    "two_times_sub": "2026  +  2027",
    "final_lines": [
        "KEEP OPENING",
        "THE TOKEN IS\nOUT THERE",
        "CLAIM YOUR\nCREW",
    ],
    "logo_top": "ONE PIECE",
    "logo_x": "x",
    "logo_bottom": "FORTNITE",
    "logo_sub": "PIRATE SHOP ACCESS",
}

# Text timing (seconds, absolute)  -  (appear, disappear)
TEXT_TIMING = {
    "rarest": (3.9, 7.7),
    "one_drop": (8.9, 15.7),
    "days_free": (19.3, 22.3),
    "two_times": (22.5, 25.8),
    "final_lines": [(26.5, 28.8), (29.0, 31.2), (31.4, 33.2)],
    "logo": (EVENTS["logo"], DURATION),
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
    "night_sky_top":     (0.004, 0.006, 0.014),
    "night_sky_horizon": (0.020, 0.032, 0.060),
    "dawn_sky_top":      (0.03, 0.16, 0.70),
    "dawn_sky_horizon":  (1.00, 0.42, 0.12),
    "text_top":     (1.00, 0.92, 0.35),    # gradient top of title text
    "text_bottom":  (1.00, 0.45, 0.02),    # gradient bottom of title text
    "text_outline": (0.05, 0.01, 0.0),
}

# ---------------------------------------------------------------------
# 5. CREW   (order = order of appearance behind Luffy)
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
TOKEN_START = (0.0, 22.0)    # where the token rises out of the sea (x, y)

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
DEFAULT_QUALITY = "hd"
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
