#!/usr/bin/env python3
"""
GTA 6 – Analyse complète des rushs (PHASE 1)
============================================
Lecture seule : aucun fichier source n'est modifié, déplacé ou supprimé.

Pour chaque vidéo du dossier (et de tous ses sous-dossiers) :
  * durée exacte, poids, résolution, FPS, codecs, pistes audio (ffprobe)
  * planches-contact couvrant TOUTE la durée (1 image toutes les N s, horodatée)
  * détection des changements de plan (scènes)
  * pics sonores (explosions, crashs, cris…) via la loudness EBU R128
Résultat : inventaire.md + inventaire.csv + inventaire.json + dossier planches/

Usage (Windows) :
  python gta6_analyse_rushs.py "C:\\Users\\arthu\\Videos\\PS5"
  python gta6_analyse_rushs.py "C:\\Users\\arthu\\Videos\\PS5" --interval 3 --out analyse_gta6
Prérequis : Python 3.8+ et ffmpeg/ffprobe dans le PATH (winget install Gyan.FFmpeg).
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".m2ts", ".wmv"}
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
COLS, ROWS = 5, 6  # 30 vignettes par planche


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def hms(t):
    t = float(t)
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def human_size(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} To"


def probe(path):
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)])
    if r.returncode:
        return {"erreur": r.stderr.strip()[:300]}
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    a = [s for s in d["streams"] if s["codec_type"] == "audio"]
    num, _, den = v.get("avg_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den) if den and float(den) else 0.0
    return {
        "duree_s": float(d["format"].get("duration", 0)),
        "largeur": v.get("width"), "hauteur": v.get("height"),
        "fps": round(fps, 3), "codec_video": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "hdr": v.get("color_transfer") in ("smpte2084", "arib-std-b67"),
        "pistes_audio": len(a),
        "codec_audio": ",".join(s.get("codec_name", "?") for s in a),
        "debit_kbps": int(int(d["format"].get("bit_rate", 0)) / 1000),
        "date_creation": d["format"].get("tags", {}).get("creation_time", ""),
    }


def contact_sheets(path, outdir, interval, font_rel):
    """Planches couvrant 100 % de la durée, une vignette toutes les `interval` s."""
    outdir.mkdir(parents=True, exist_ok=True)
    txt = ("drawtext=fontfile=" + font_rel +
           ":text='%{pts\\:hms}':x=6:y=6:fontsize=22:fontcolor=white"
           ":box=1:boxcolor=black@0.6:boxborderw=4,") if font_rel else ""
    vf = (f"fps=1/{interval},scale=384:-2,{txt}"
          f"tile={COLS}x{ROWS}:padding=4:margin=4:color=0x1a0b2e")
    # cwd = dossier de sortie : le chemin de police reste relatif, pas d'échappement Windows
    r = run(["ffmpeg", "-v", "error", "-y", "-i", str(path.resolve()), "-an", "-sn",
             "-vf", vf, "-fps_mode", "vfr", "-q:v", "4", "planche_%03d.jpg"],
            cwd=outdir)
    if r.returncode and font_rel:  # repli sans texte si drawtext indisponible
        return contact_sheets(path, outdir, interval, None)
    return sorted(p.name for p in outdir.glob("planche_*.jpg"))


def scene_changes(path, seuil=0.35):
    r = run(["ffmpeg", "-hide_banner", "-i", str(path), "-an", "-sn", "-vf",
             f"scale=320:-2,select='gt(scene\\,{seuil})',showinfo",
             "-f", "null", "-"])
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def audio_peaks(path, top=12, ecart=8.0):
    r = run(["ffmpeg", "-hide_banner", "-v", "verbose", "-i", str(path), "-vn", "-sn",
             "-af", "ebur128=framelog=verbose", "-f", "null", "-"])
    pts = [(float(t), float(m)) for t, m in
           re.findall(r"t:\s*([\d.]+)\s+TARGET.*?M:\s*(-?[\d.]+)", r.stderr)]
    if not pts:
        return [], None
    moy = sum(m for _, m in pts) / len(pts)
    choisis = []
    for t, m in sorted(pts, key=lambda x: -x[1]):
        if m < moy + 6:  # on ne garde que ce qui dépasse nettement le niveau moyen
            break
        if all(abs(t - c[0]) >= ecart for c in choisis):
            choisis.append((round(t, 1), round(m, 1)))
        if len(choisis) >= top:
            break
    return sorted(choisis), round(moy, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="dossier des rushs (ex. C:\\Users\\arthu\\Videos\\PS5)")
    ap.add_argument("--out", default="analyse_gta6", help="dossier de sortie")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="secondes entre deux vignettes (défaut 5)")
    ap.add_argument("--rapide", action="store_true",
                    help="saute détection de scènes et pics sonores")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} introuvable. Installe-le : winget install Gyan.FFmpeg")

    src = Path(args.source)
    out = Path(args.out).resolve()
    if out == src.resolve() or src.resolve() in out.parents:
        sys.exit("Le dossier de sortie doit être HORS du dossier source.")
    out.mkdir(parents=True, exist_ok=True)

    tous = sorted(p for p in src.rglob("*") if p.is_file())
    videos = [p for p in tous if p.suffix.lower() in VIDEO_EXT]
    autres = [p for p in tous if p.suffix.lower() not in VIDEO_EXT]
    print(f"{len(tous)} fichiers trouvés, dont {len(videos)} vidéos.\n")

    font_rel = None
    font = next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)

    rows = []
    for i, p in enumerate(videos, 1):
        rel = p.relative_to(src)
        print(f"[{i}/{len(videos)}] {rel}")
        info = {"n": i, "fichier": str(rel), "poids_octets": p.stat().st_size,
                "poids": human_size(p.stat().st_size)}
        info.update(probe(p))
        if "erreur" in info:
            print("   ! illisible :", info["erreur"])
            rows.append(info)
            continue
        print(f"   durée {hms(info['duree_s'])} · {info['largeur']}x{info['hauteur']}"
              f" · {info['fps']} fps · {info['poids']}")

        dossier = out / "planches" / f"{i:02d}_{p.stem}"
        if font:
            dossier.mkdir(parents=True, exist_ok=True)
            shutil.copy(font, dossier / "font.ttf")
            font_rel = "font.ttf"
        info["planches"] = contact_sheets(p, dossier, args.interval, font_rel)
        info["planche_couvre_s"] = COLS * ROWS * args.interval
        print(f"   {len(info['planches'])} planche(s)")

        if not args.rapide:
            info["changements_de_plan"] = scene_changes(p)
            info["pics_sonores"], info["loudness_moy_lufs"] = audio_peaks(p)
            print(f"   {len(info['changements_de_plan'])} changements de plan, "
                  f"{len(info['pics_sonores'])} pics sonores")
        rows.append(info)

    # ---------- exports ----------
    (out / "inventaire.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    champs = ["n", "fichier", "duree_s", "poids", "poids_octets", "largeur", "hauteur",
              "fps", "codec_video", "hdr", "pistes_audio", "codec_audio", "debit_kbps",
              "date_creation"]
    with open(out / "inventaire.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, champs, extrasaction="ignore", delimiter=";")
        w.writeheader()
        w.writerows(rows)

    ok = [r for r in rows if "duree_s" in r]
    total = sum(r["duree_s"] for r in ok)
    md = ["# Inventaire des rushs GTA 6", "",
          f"Source : `{src}`  ", f"Vidéos : **{len(videos)}** · "
          f"Durée totale : **{hms(total)}** · "
          f"Poids total : **{human_size(sum(r['poids_octets'] for r in rows))}**", "",
          "| # | Fichier | Durée | Poids | Résolution | FPS | HDR | Audio |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "duree_s" not in r:
            md.append(f"| {r['n']} | {r['fichier']} | ILLISIBLE | {r['poids']} | | | | |")
            continue
        md.append(f"| {r['n']} | {r['fichier']} | {hms(r['duree_s'])} | {r['poids']} | "
                  f"{r['largeur']}x{r['hauteur']} | {r['fps']} | "
                  f"{'oui' if r['hdr'] else 'non'} | {r['codec_audio']} |")
    if ok:
        cible = min(ok, key=lambda r: abs(r["duree_s"] - 660))
        md += ["", f"**Clip le plus proche de 11 min :** `{cible['fichier']}` "
                   f"({hms(cible['duree_s'])})"]
    for r in ok:
        md += ["", f"## {r['n']}. {r['fichier']}",
               f"Planches : {len(r.get('planches', []))} "
               f"(chacune couvre {r['planche_couvre_s']:.0f} s, lecture gauche→droite)"]
        if r.get("pics_sonores"):
            md.append("Pics sonores (moments potentiellement forts) : " + ", ".join(
                f"{hms(t)} ({m} LUFS)" for t, m in r["pics_sonores"]))
        if r.get("changements_de_plan") is not None:
            md.append(f"Changements de plan détectés : {len(r['changements_de_plan'])}")
    if autres:
        md += ["", "## Fichiers non vidéo (ignorés)"] + [f"- {a.relative_to(src)}"
                                                         for a in autres]
    (out / "inventaire.md").write_text("\n".join(md), encoding="utf-8")

    print(f"\nTerminé. Résultats dans : {out}")
    print("Envoie-moi inventaire.md, inventaire.json et le dossier planches/.")


if __name__ == "__main__":
    main()
