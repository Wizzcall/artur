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
        (38.13, 770, 465, "chest"),
        (40.73, 1075, 430, "chest"),
        (75.30, 865, 330, "chest"),
        (80.10, 920, 430, "loot"),
        (90.03, 1055, 485, "chest"),
        (99.83, 1000, 510, "chest"),
        (119.63, 885, 380, "loot"),
        (122.13, 1055, 520, "chest"),
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
        (39.9, 1000, 580, "chest"),
        (53.9, 1020, 540, "chest"),
        (62.7, 1000, 540, "chest"),
        (78.2, 920, 490, "chest"),
        (86.9, 1150, 520, "chest"),
        (114.5, 1055, 490, "chest"),
        (128.7, 1000, 455, "chest"),
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

SPOTS = {s["key"]: s for s in (SPOT1, SPOT2)}

if __name__ == "__main__":
    import sys
    from spot_edit import build_spot
    os.makedirs("renders", exist_ok=True)
    keys = sys.argv[1:] or list(SPOTS)
    for k in keys:
        build_spot(SPOTS[k], os.path.join("renders", f"{k}.mp4"))
