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
    # game time later, read from the storm timer), then clip2_part2 (after B).
    clips=[(_p(_S3, "map.jpg"), -3.5, 3.5)]
    + [(_p(_S3, f"clipA_part{k + 1}_{30 * k}-{30 * k + 30}s.mp4"), 30.0 * k, 29.76 if k == 5 else 30.0)
       for k in range(6)]
    + [(_p(_S3, "clipB_part1_0-30s.mp4"), 206.8, 30.0),
       (_p(_S3, "clipB_part2_30-60s.mp4"), 236.8, 29.6),
       (_p(_S3, "clip2_part2_30-60s.mp4"), 300.0, 29.5)],
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
        (301.9, 307.8, 3),
        (307.8, 310.0, 1),
    ],
    events=[
        (3.0, 1190, 300, "chest"),
        (16.6, 1000, 575, "chest"),
        (21.4, 1000, 690, "chest"),
        (27.0, 1035, 540, "chest"),
        (67.1, 1110, 615, "chest"),
        (94.8, 960, 300, "chest"),
        (97.4, 1350, 230, "chest"),
        (141.3, 760, 560, "chest"),
        (147.6, 1000, 575, "chest"),
        (153.8, 690, 385, "chest"),
        (172.0, 1075, 615, "chest"),
        (177.2, 690, 575, "chest"),
        # after 3:30 -> shown as bonus, not counted
        (226.4, 1000, 385, "chest"),
        (235.7, 960, 615, "chest"),
        (245.6, 1110, 650, "chest"),
        (308.8, 690, 770, "chest"),
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

SPOTS = {s["key"]: s for s in (SPOT1, SPOT2, SPOT3)}

if __name__ == "__main__":
    import sys
    from spot_edit import build_spot
    os.makedirs("renders", exist_ok=True)
    keys = sys.argv[1:] or list(SPOTS)
    for k in keys:
        build_spot(SPOTS[k], os.path.join("renders", f"{k}.mp4"))
