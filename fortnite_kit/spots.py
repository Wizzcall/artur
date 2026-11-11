"""Edit specs for each spot. All times are GLOBAL source seconds for that spot
(clips are contiguous; offsets below). Events = exact frame where a chest
opens / loot pops out, with the on-screen position of the chest (1920x1080)."""
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "clips")


def _p(*a):
    return os.path.join(ROOT, *a)


SPOT1 = dict(
    key="spot1_rubber_resort", number=1, name="RUBBER RESORT", music="rubber_resort", hdr=True,
    clips=[(_p("spot1_rubber_resort", "clip1.mov"), 0.0, 30.2333),
           (_p("spot1_rubber_resort", "clip2.mov"), 30.2333, 29.5667),
           (_p("spot1_rubber_resort", "clip3.mov"), 59.8, 29.5333),
           (_p("spot1_rubber_resort", "clip4.mov"), 89.3333, 33.4)],
    t0=3.5,                       # touch-down -> chrono starts
    target=(960, 780),            # ring/arrow while in the air
    segments=[
        (0.0, 3.5, 1),            # skydive over the island, landing
        (3.5, 36.7, 3),           # G-Wagon drive (C1 -> C2 6.5)
        (36.7, 42.2, 1),          # chests 1 + 2 on the deck
        (42.2, 73.3, 3),          # drive (C2 12 -> C3 13.5)
        (73.3, 81.3, 1),          # chest on the rock + ammo box loot
        (81.3, 88.3, 2),
        (88.3, 91.33, 1),         # anchor chest
        (91.33, 96.33, 2),
        (96.33, 100.83, 1),       # house chest
        (100.83, 118.33, 3),
        (118.33, 122.73, 1),      # loot pop + last chest
    ],
    events=[  # (global t, x, y, kind)
        (38.13, 1300, 560, "chest"),
        (40.73, 1400, 700, "chest"),
        (75.30, 960, 440, "chest"),
        (80.10, 880, 460, "loot"),
        (90.03, 1225, 560, "chest"),
        (99.83, 1180, 580, "chest"),
        (119.63, 500, 650, "loot"),
        (122.13, 1040, 560, "chest"),
    ],
    texts=[  # (global t, title, subtitle, rarity, edit duration)
        (12.0, "EN VOITURE = PLUS RAPIDE", "LE G-WAGON EN OR", "legendary", 2.6),
        (41.2, "2 COFFRES EN 3 SECONDES !", None, "legendary", 2.0),
        (50.0, "DIRECTION LE PROCHAIN COFFRE", None, "rare", 2.2),
        (73.5, "COFFRE SUR LE ROCHER", "ON ESCALADE !", "epic", 1.7),
        (80.6, "CAISSE DE MUNITIONS", "ÇA COMPTE AUSSI !", "rare", 1.8),
        (92.0, "5 COFFRES EN 1:27", None, "epic", 2.0),
        (106.0, "6 COFFRES EN 1:36", "ON ACCÉLÈRE", "legendary", 2.2),
    ],
)

SPOT2 = dict(
    key="spot2_lantern_landing", number=2, name="LANTERN LANDING", music="lantern_landing", hdr=False,
    clips=[(_p("spot2_lantern_landing", f"part{k + 1}.mp4"), 30.0 * k, 29.88 if k == 5 else 30.0)
           for k in range(6)],
    t0=29.4,
    target=(960, 700),
    segments=[
        (8.6, 10.6, 1),           # map screen + jump from the bus
        (10.6, 26.6, 4),          # skydive
        (26.6, 30.0, 1),          # glider + landing
        (30.0, 35.0, 2),
        (35.0, 41.0, 1),          # elimination + chest 1
        (41.0, 49.5, 3),
        (49.5, 52.5, 2),
        (52.5, 55.0, 1),          # chest 2
        (55.0, 60.0, 3),
        (60.0, 64.0, 1),          # chest 3
        (64.0, 75.5, 3),
        (75.5, 79.5, 1),          # chest 4
        (79.5, 85.0, 2),
        (85.0, 88.5, 1),          # chest 5
        (88.5, 111.5, 4),         # long dig
        (111.5, 116.0, 1),        # chest 6
        (116.0, 126.5, 3),
        (126.5, 130.5, 1),        # chest 7
        (130.5, 134.5, 6),
        (134.5, 137.5, 1),        # reaction on the stuck chest
        (137.5, 164.0, 6),
        (164.0, 166.0, 1),        # jump off the cliff
        (166.0, 179.8, 4),
    ],
    events=[
        (39.9, 920, 560, "chest"),
        (53.9, 680, 520, "chest"),
        (62.7, 480, 780, "chest"),
        (78.2, 880, 500, "chest"),
        (86.9, 1060, 560, "chest"),
        (114.5, 960, 420, "chest"),
        (128.7, 1000, 420, "chest"),
    ],
    texts=[
        (37.6, "ÉLIMINATION !", "PILE SUR LE COFFRE", "legendary", 1.8),
        (50.0, "COFFRES ENTERRÉS", "ÇA SE CREUSE !", "epic", 2.4),
        (87.3, "5 COFFRES EN 57 S !", "MEILLEUR RYTHME", "legendary", 2.4),
        (92.0, "LE COFFRE EST PROFOND...", None, "rare", 2.2),
        (129.3, "7 COFFRES EN 1:39", None, "epic", 2.0),
        (131.0, "CE COFFRE NE VEUT PAS SORTIR", None, "rare", 2.2),
        (164.2, "ON CHANGE DE COIN", None, "rare", 1.6),
    ],
    rages=[(135.0, "SORS DE LÀ !!", 2.2)],
)

_S3 = "spot3_loguetown"
SPOT3 = dict(
    key=_S3, number=3, name="LOGUETOWN", music="loguetown", hdr=False,
    # One continuous match: clipA (0-3:00 after landing), then clipB (~27 s of
    # game time later, read from the storm timer).
    clips=[(_p(_S3, "map.jpg"), -3.5, 3.5)]
    + [(_p(_S3, f"clipA_part{k + 1}_{30 * k}-{30 * k + 30}s.mp4"), 30.0 * k, 29.76 if k == 5 else 30.0)
       for k in range(6)]
    + [(_p(_S3, "clipB_part1_0-30s.mp4"), 206.8, 30.0),
       (_p(_S3, "clipB_part2_30-60s.mp4"), 236.8, 29.6)],
    t0=1.9,                       # first gameplay frame, just after touch-down
    target=(1061, 588),           # map marker on the screenshot
    segments=[
        (-3.5, 0.0, 1),           # map: aiming at the spot
        (1.9, 4.5, 1),            # chest 1 on the beach
        (4.5, 15.6, 3),
        (15.6, 17.6, 1),          # chest 2 (house)
        (17.6, 20.4, 2),
        (20.4, 22.4, 1),          # chest 3 (rare, purple)
        (22.4, 26.0, 2),
        (26.0, 28.0, 1),          # chest 4
        (28.0, 65.5, 6),          # run + swim to the boat
        (65.5, 68.0, 1),          # chest 5 on the boat
        (68.0, 93.6, 5),          # buried chests: dig
        (93.6, 98.4, 1),          # chests 6 + 7 (big pop)
        (98.4, 140.3, 6),
        (140.3, 142.3, 1),        # chest 8 on the pier
        (142.3, 146.6, 2),
        (146.6, 148.6, 1),        # chest 9
        (148.6, 152.8, 2),
        (152.8, 154.8, 1),        # chest 10 (shack)
        (154.8, 171.0, 4),
        (171.0, 173.0, 1),        # chest 11 (bamboo)
        (173.0, 176.2, 2),
        (176.2, 179.7, 1),        # chest 12
        (208.7, 212.5, 2),        # 27 s later: chrono runs out
        (212.5, 225.4, 6),
        (225.4, 227.4, 1),        # bonus chests (after 3:30)
        (227.4, 234.8, 4),
        (234.8, 236.6, 1),
        (237.05, 244.6, 4),
        (244.6, 246.6, 1),
    ],
    events=[
        (3.0, 1190, 300, "chest"),
        (16.6, 1000, 575, "chest"),
        (21.4, 1000, 690, "chest"),
        (27.0, 1035, 540, "chest"),
        (67.1, 1110, 615, "chest"),
        (94.8, 960, 300, "chest"),
        (97.4, 760, 430, "chest"),
        (141.3, 760, 560, "chest"),
        (147.6, 1000, 575, "chest"),
        (153.8, 690, 385, "chest"),
        (172.0, 1075, 615, "chest"),
        (177.2, 690, 575, "chest"),
        # after 3:30 -> shown as bonus, not counted
        (226.4, 1000, 385, "chest"),
        (235.7, 960, 615, "chest"),
        (245.6, 1110, 650, "chest"),
    ],
    texts=[
        (17.0, "4 COFFRES EN 25 S !", "DÉPART ULTRA RAPIDE", "legendary", 2.0),
        (21.0, "COFFRE RARE", None, "epic", 1.6),
        (40.0, "CAP SUR LE BATEAU", "À LA NAGE", "rare", 2.2),
        (75.0, "COFFRES ENTERRÉS", "ÇA SE CREUSE !", "epic", 2.2),
        (98.0, "DOUBLE COFFRE !", None, "legendary", 1.8),
        (120.0, "7 COFFRES EN 1:36", None, "epic", 2.0),
        (160.0, "10 COFFRES EN 2:32", "LE RYTHME EST FOU", "legendary", 2.2),
        (178.0, "12 COFFRES EN 2:55 !", None, "legendary", 1.8),
        (214.0, "BONUS : LA SUITE DE LA GAME", "NE COMPTE PAS AU CLASSEMENT", "rare", 2.4),
    ],
)

_S4 = "spot4_arlong_park"
SPOT4 = dict(
    key=_S4, number=4, name="BIVOUAC DES BOUCANIERS", music="arlong_park", hdr=False,
    # clipA = the first minute after landing; clip2 = later in the same game
    # (small island, 32 -> 27 players). The unfilmed time between is a "gap":
    # the chrono only counts filmed farm time.
    clips=[(_p(_S4, "map.jpg"), -3.5, 3.5),
           (_p(_S4, "clipA_part1_0-30s.mp4"), 0.0, 30.0),
           (_p(_S4, "clipA_part2_30-60s.mp4"), 30.0, 29.66),
           (_p(_S4, "clip2_part1_0-30s.mp4"), 70.0, 30.2),
           (_p(_S4, "clip2_part2_30-60s.mp4"), 100.2, 29.5)],
    gaps=[(59.66, 71.87)],
    t0=1.9,
    target=(1158, 359),           # map marker (Bivouac des Boucaniers)
    segments=[
        (-3.5, 0.0, 1),
        (1.9, 5.4, 2),
        (5.4, 7.4, 1),            # chest 1 (tent shelf)
        (7.4, 22.8, 3),
        (22.8, 25.0, 1),          # ammo box pops
        (25.0, 34.5, 3),
        (34.5, 36.8, 1),          # chest 3 (tent)
        (36.8, 59.6, 4),
        (71.87, 75.0, 1),         # later in the game: chest on the lookout
        (75.0, 79.8, 3),
        (79.8, 81.6, 1),          # chest (tent)
        (81.6, 93.4, 3),
        (93.4, 95.0, 1),          # chest (tent)
        (95.0, 98.6, 2),
        (98.6, 100.2, 1),         # chest (stall)
        (102.1, 107.4, 3),
        (107.4, 109.6, 1),        # chest in the storm
        (109.6, 129.6, 6),
    ],
    events=[
        (6.3, 960, 420, "chest"),
        (24.4, 500, 470, "loot"),
        (35.8, 900, 300, "chest"),
        (74.0, 700, 700, "chest"),
        (80.6, 1000, 615, "chest"),
        (94.2, 1000, 540, "chest"),
        (99.5, 920, 540, "chest"),
        (108.8, 960, 600, "chest"),
    ],
    texts=[
        (12.0, "CAMPEMENT PIRATE", "COFFRES SOUS LES TENTES", "epic", 2.2),
        (24.6, "CAISSE DE MUNITIONS", "ÇA COMPTE AUSSI !", "rare", 1.8),
        (45.0, "3 COFFRES EN 34 S", None, "epic", 2.0),
        (72.2, "PLUS TARD DANS LA GAME...", "CHRONO EN PAUSE PENDANT LE TRAJET", "rare", 2.4),
        (95.5, "3 COFFRES EN 19 S !", "SOUS LES TENTES", "legendary", 2.0),
        (107.6, "DANS LA TEMPÊTE !", "ON OUVRE QUAND MÊME", "legendary", 2.0),
    ],
)

_S5 = "spot5_the_chest"
SPOT5 = dict(
    key=_S5, number=5, name="FORTERESSE DE LIL' UZI", music="the_chest", hdr=False,
    clips=[(_p(_S5, "map.jpg"), -3.5, 3.5),
           (_p(_S5, "clip3_part1_0-30s.mp4"), 0.0, 30.0),
           (_p(_S5, "clip3_part2_30-60s.mp4"), 30.0, 29.72)],
    t0=2.5,                       # splash into the cave pool
    target=(950, 355),            # marker 2 on the zoomed map
    segments=[
        (-3.5, 0.0, 1),
        (1.9, 3.6, 1),            # dive into the water
        (3.6, 15.4, 4),
        (15.4, 17.6, 1),          # chest 1 (gold pile)
        (17.6, 31.8, 4),
        (31.8, 34.0, 1),          # chest 2 (rare)
        (34.0, 41.6, 3),
        (41.6, 43.6, 1),          # chest 3
        (43.6, 45.8, 2),
        (45.8, 47.4, 1),          # chest 4 (blue)
        (47.4, 48.8, 2),
        (48.8, 51.0, 1),          # chest 5
        (51.0, 59.7, 4),
    ],
    events=[
        (46.3 - 30.0, 1000, 560, "chest"),
        (32.4, 720, 560, "chest"),
        (42.4, 1000, 620, "chest"),
        (46.7, 1150, 600, "chest"),
        (49.7, 1150, 560, "chest"),
    ],
    texts=[
        (5.0, "LA GROTTE AU TRÉSOR", "SOUS LA FORTERESSE", "legendary", 2.4),
        (16.8, "PREMIER COFFRE !", None, "epic", 1.6),
        (32.8, "COFFRE RARE", None, "epic", 1.6),
        (50.0, "3 COFFRES EN 7 S !", "LA GROTTE EST BLINDÉE", "legendary", 2.0),
        (54.0, "5 COFFRES EN 47 S", None, "epic", 2.0),
    ],
)

SPOTS = {s["key"]: s for s in (SPOT1, SPOT2, SPOT3, SPOT4, SPOT5)}

if __name__ == "__main__":
    import sys
    from spot_edit import build_spot
    os.makedirs("renders", exist_ok=True)
    keys = sys.argv[1:] or list(SPOTS)
    for k in keys:
        build_spot(SPOTS[k], os.path.join("renders", f"{k}.mp4"))
