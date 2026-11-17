"""Génère GTA6_VOIX_OFF.txt et GTA6_TIMELINE.txt à partir de l'EDL réelle."""
import json
from pathlib import Path
from narration import SECTIONS
ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT.parent
e = json.loads((ROOT / "build" / "edl.json").read_text())
fmt = lambda t: f"{int(t // 60)}:{int(t % 60):02d}.{int((t * 10) % 10)}"
NAMES = dict(intro="INTRODUCTION SPECTACULAIRE", download="LE TÉLÉCHARGEMENT SUR PS5", hype="L'ATTENTE AUTOUR DU JEU",
             world="L'UNIVERS : JASON, LUCIA, VICE CITY", mine="MES ATTENTES PERSONNELLES",
             community="GTA 6 ET LES ATTENTES DE LA COMMUNAUTÉ", outro="CONCLUSION ET PROCHAINES VIDÉOS")
TARGET = dict(intro="0:00–0:40", download="0:40–1:40", hype="1:40–2:50", world="2:50–4:30", mine="4:30–6:20",
              community="6:20–7:50", outro="7:50–9:00")
MUSIC = dict(intro="cinématique et mystérieuse (drone, pulsations, arpège en écho)",
             download="montée de tension progressive (basse pulsée, filtre qui s'ouvre, résolution au 100 %)",
             hype="documentaire tendu (ostinato, toms sur les dates clés)",
             world="synthwave estivale Vice City (batterie gated, basse octaviée, mélodie)",
             mine="discrète et intime (piano électrique, batterie feutrée, vinyle)",
             community="énergie moyenne et chaleureuse, accélère vers le compte à rebours",
             outro="épique (toms, chœurs synthétiques, mélodie principale, final sur le logo)")

# ── VOIX OFF
L = ["GTA 6 — SCRIPT DE VOIX OFF", "=" * 60,
     "Une prise par ligne. Pour enregistrer votre voix : un fichier par numéro",
     "(voice_user/LINE_01.wav, LINE_02.wav, …), puis `python build.py --user-voice voice_user`.",
     "Le montage se recale automatiquement sur la durée de vos prises.", ""]
n = 0; vi = {v["n"]: v for v in e["voice"]}
for s in SECTIONS:
    sec = next(x for x in e["sections"] if x["key"] == s["key"])
    L += ["", f"[{fmt(sec['t0'])}] {NAMES[s['key']]}" + (f" — chapitre {s['title'][0]} « {s['title'][1]} »" if s["title"] else ""), "-" * 60]
    for ln in s["lines"]:
        if not ln["text"]:
            continue
        n += 1
        L.append(f"LINE_{n:02d}  [{fmt(vi[n]['t'])}]  {ln['text']}")
words = sum(len(v["text"].split()) for v in e["voice"])
L += ["", f"{n} lignes · {words} mots · {sum(v['dur'] for v in e['voice']) / 60:.1f} min de parole"]
(OUTDIR / "GTA6_VOIX_OFF.txt").write_text("\n".join(L) + "\n")

# ── TIMELINE
T = ["GTA 6 — TIMELINE DE MONTAGE", "=" * 78, f"Durée totale : {fmt(e['total'])}  ·  1920×1080  ·  30 i/s  ·  H.264 + AAC",
     f"{len(e['shots'])} plans · {len(e['caps'])} sous-titres dynamiques · {len(e['sfx'])} effets sonores", ""]
DESC = dict(kb="Ken Burns", para="Parallaxe 2.5D (sujet détouré)", stack="Composition multi-cartes", loc="Lieu + étiquette 3D",
            hero="Héros détouré, nom 3D derrière le sujet", split="Écran partagé diagonal", reveal="Clip officiel reveal logo/cover",
            clip="Clip officiel ralenti ×3 (interpolé)", char="Personnage : artwork + clip + nom 3D", title="Titre 3D animé",
            chapter="Carte chapitre synthwave", year="Date clé 3D", counter="Compteur animé", glitchwall="Mur d'images glitch",
            dates="Frise des reports", num="Attente numérotée", list="Liste animée", platform="Plateformes", meme="Mème animé",
            mapgrid="Planche « carte » des lieux", countdown="Compte à rebours", ps5="Habillage préchargement (illustration)",
            dl_teaser="Teaser préchargement (illustration)", next="Prochaine vidéo", subscribe="Abonnement + cloche",
            endcard="Écran de fin YouTube")
for s in e["sections"]:
    T += ["", f"■ {fmt(s['t0'])} → {fmt(s['t1'])}   {NAMES[s['key']]}   (cible du brief : {TARGET[s['key']]})",
          f"  Musique : {MUSIC[s['music']]} — {s['tempo']} BPM", ""]
    for sh in e["shots"]:
        if sh["sec"] != s["key"]: continue
        p = sh["p"]; what = p.get("img") or p.get("clip") or ",".join(p.get("imgs", [])) or p.get("name") or p.get("phase") or p.get("t1") or ""
        T.append(f"  {fmt(sh['t0']):>8} → {fmt(sh['t1']):>8}  [{sh.get('tr', 'cut'):11s}] {DESC.get(sh['kind'], sh['kind'])} · {what}")
    caps = [c for c in e["caps"] if s["t0"] <= c["t0"] < s["t1"]]
    if caps:
        T.append("  Sous-titres : " + " | ".join(f"{fmt(c['t0'])} « {c['text']} »" for c in caps))
    sfx = [x for x in e["sfx"] if s["t0"] <= x["t"] < s["t1"] and not x.get("tr")]
    if sfx:
        T.append("  SFX narration : " + ", ".join(f"{fmt(x['t'])} {x['name']}" for x in sfx))
T += ["", "Mixage : voix -0 dB (référence) · musique -21 dB sous la voix / -7 dB dans les respirations (ducking auto)",
      "· SFX atténués de 4 dB sous la voix · ambiances urbaines/plage -12 dB sous la voix · master normalisé -14 LUFS, crête -1 dBTP.",
      "", "Transitions (sons de transition synchronisés) : " + ", ".join(sorted({sh.get('tr', '') for sh in e['shots'] if sh.get('tr')}))]
(OUTDIR / "GTA6_TIMELINE.txt").write_text("\n".join(T) + "\n")
print("ok")
