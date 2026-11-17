"""
Construit la timeline complète (EDL) à partir de narration.py + durées voix.
Sortie : build/edl.json  — plans, transitions, sous-titres, SFX, musique.
"""
import json, re
from pathlib import Path
from narration import SECTIONS

ROOT = Path(__file__).resolve().parent
FPS = 30
CHAPTER_LEN = 3.2
TEMPO = dict(intro=80, download=100, hype=90, world=104, mine=78, community=96, outro=96)

# transitions : « douces » par défaut, « fortes » ponctuelles (jamais deux fortes d'affilée)
SOFT = ["xfade", "cutmove", "xfade", "fade_soft", "cutmove", "dezoom_soft"]
STRONG = ["whip", "zoom", "dirblur", "light", "dezoom", "glitch"]
TR_LEN = dict(cut=0.0, cutmove=0.0, xfade=0.5, fade_soft=0.7, dezoom_soft=0.6, whip=0.36, zoom=0.42,
              dirblur=0.4, light=0.6, dezoom=0.45, glitch=0.3, fade=1.0, flash=0.5)
TR_SFX = dict(whip="whoosh", zoom="whoosh_zoom", dirblur="swish", light="shimmer", dezoom="whoosh_rev",
              glitch="glitch_s", flash="impact_s")


def word_time(line_meta, start, word, text):
    """Temps approx. d'un mot : recherche dans la phrase, prorata des caractères."""
    if isinstance(word, (int, float)):
        return start + word
    if not word:
        return start
    for s in line_meta["sents"]:
        i = s["text"].find(word)
        if i >= 0:
            return start + s["start"] + s["dur"] * (i / max(1, len(s["text"])))
    i = text.find(word)
    return start + line_meta["dur"] * (max(0, i) / max(1, len(text)))


def build():
    vm = json.loads((ROOT / "build" / "voice" / "voice.json").read_text())
    t = 0.0; n = 0
    shots, caps, sfx, voice, sections, chapters = [], [], [], [], [], []
    strong_count = 0
    for si, sec in enumerate(SECTIONS):
        s0 = t
        if sec["title"]:
            shots.append(dict(kind="chapter", t0=t, t1=t + CHAPTER_LEN, p=dict(num=sec["title"][0], name=sec["title"][1]),
                              tr="flash", sec=sec["key"]))
            chapters.append(dict(t=t, num=sec["title"][0], name=sec["title"][1]))
            sfx.append(dict(t=t, name="impact")); sfx.append(dict(t=t - 1.6, name="riser_s"))
            t += CHAPTER_LEN
        for li, ln in enumerate(sec["lines"]):
            t += ln.get("pre", 0.0)
            ls = t
            if ln["text"]:
                n += 1
                m = vm[str(n)]
                d = m["dur"]
                voice.append(dict(n=n, t=ls, dur=d, text=ln["text"]))
                sent_starts = [ls + s["start"] for s in m["sents"]]
            else:
                m = None; d = ln.get("hold", 3.0); sent_starts = []
            le = ls + d + ln.get("post", 0.0)
            # répartition des plans
            W = sum(w for _, _, w in ln["shots"]); acc = ls
            bounds = [ls - ln.get("pre", 0.0)]
            for k, (_, _, w) in enumerate(ln["shots"][:-1]):
                acc += (le - ls) * w / W
                # aligner sur un début de phrase proche (coupe sur la respiration)
                near = [s for s in sent_starts if abs(s - acc) < 1.0 and s - 0.12 > bounds[-1] + 1.2]
                bounds.append((min(near, key=lambda s: abs(s - acc)) - 0.12) if near else acc)
            bounds.append(le)
            for k, (kind, p, _) in enumerate(ln["shots"]):
                shots.append(dict(kind=kind, t0=bounds[k], t1=bounds[k + 1], p=p, sec=sec["key"]))
            for (w, txt, style) in ln.get("caps", []):
                if style == "none":
                    continue
                ct = word_time(m, ls, w, ln["text"]) if (m or isinstance(w, (int, float))) else ls
                caps.append(dict(t0=ct - 0.05, t1=min(ct + (2.6 if style in ("big", "stat", "logo") else 3.0), le + 0.3), text=txt, style=style))
            for (w, name) in ln.get("sfx", []):
                st = word_time(m, ls, w, ln["text"]) if (m or isinstance(w, (int, float))) else ls
                if name == "riser":
                    sfx.append(dict(t=le - 2.6, name="riser"))
                elif name == "riser_long":
                    sfx.append(dict(t=le - 5.0, name="riser_long"))
                else:
                    sfx.append(dict(t=st - (0.2 if name.startswith(("whoosh", "swish")) else 0.0), name=name))
            t = le
        sections.append(dict(key=sec["key"], t0=s0, t1=t, music=sec["music"], title=sec["title"], tempo=TEMPO[sec["music"]]))

    # transitions : choix déterministe, varié, synchronisé sur la grille rythmique
    # Les plans « capture » (ajouts ultérieurs) sont exclus du calcul : les transitions du montage
    # d'origine restent strictement identiques ; seules les jonctions avec une capture sont surchargées.
    base = [s for s in shots if s["kind"] != "capture"]
    rot_s = 0; rot_h = 0; prev_strong = False
    for i in range(1, len(base)):
        a, b = base[i - 1], base[i]
        if "tr" in b:
            tr = b["tr"]
        elif b["kind"] == "reveal" or a["kind"] == "reveal":
            tr = "fade"
        elif b["kind"] in ("title", "countdown", "num", "hero") and not prev_strong:
            tr = ["zoom", "light", "dezoom", "flash"][rot_h % 4]; rot_h += 1
        elif not prev_strong and (i % 3 == 0):
            tr = STRONG[rot_h % len(STRONG)]; rot_h += 1
        else:
            tr = SOFT[rot_s % len(SOFT)]; rot_s += 1
        b["tr"] = tr
        prev_strong = tr in STRONG or tr == "flash"
    for i in range(1, len(shots)):
        a, b = shots[i - 1], shots[i]
        if b["kind"] == "capture":
            b["tr"] = b["p"].get("tr_in", "xfade")
        elif a["kind"] == "capture":
            b["tr"] = a["p"].get("tr_out", "xfade")
        if b["tr"] in TR_SFX:
            sfx.append(dict(t=b["t0"] - TR_LEN[b["tr"]] * 0.5, name=TR_SFX[b["tr"]], tr=True))
    shots[0].pop("tr", None)
    total = t
    edl = dict(fps=FPS, total=total, shots=shots, caps=caps, sfx=sorted(sfx, key=lambda x: x["t"]), voice=voice,
               sections=sections, chapters=chapters, tr_len=TR_LEN)
    (ROOT / "build" / "edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=1))
    return edl


def fmt(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


if __name__ == "__main__":
    e = build()
    for s in e["sections"]:
        print(f"{s['key']:10s} {fmt(s['t0'])} → {fmt(s['t1'])}  ({s['t1'] - s['t0']:.1f}s)")
    print("TOTAL", fmt(e["total"]), "plans:", len(e["shots"]), "sous-titres:", len(e["caps"]), "sfx:", len(e["sfx"]))
    from collections import Counter
    print(Counter(s["tr"] for s in e["shots"] if "tr" in s))
    durs = [s["t1"] - s["t0"] for s in e["shots"]]
    print("durée plan min/moy/max", round(min(durs), 2), round(sum(durs) / len(durs), 2), round(max(durs), 2))
