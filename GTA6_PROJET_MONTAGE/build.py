"""
Orchestrateur : vérification des médias → voix → timeline → audio → rendu parallèle → export final.

    python build.py --media <médias> --models <modèles>            # tout reconstruire
    python build.py --user-voice voice_user                         # avec VOTRE voix off
    python build.py --skip-assets --skip-voice                      # ré-export rapide
"""
import argparse, json, math, subprocess, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
PY = sys.executable
OUT = ROOT.parent / "GTA6_VIDEO_FINALE.mp4"


def run(*a): print("»", " ".join(map(str, a)), flush=True); subprocess.run(list(map(str, a)), check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media"); ap.add_argument("--models")
    ap.add_argument("--user-voice"); ap.add_argument("--skip-assets", action="store_true")
    ap.add_argument("--skip-voice", action="store_true"); ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    if not a.skip_assets: run(PY, "assets.py", "--media", a.media, "--models", a.models)
    rep = json.loads((ROOT / "build" / "media_report.json").read_text())
    bad = [k for k, v in rep.items() if not v["ok"]]
    if bad: sys.exit(f"Médias manquants/corrompus : {bad}")
    if a.user_voice: run(PY, "tts.py", "--user", a.user_voice)
    elif not a.skip_voice: run(PY, "tts.py", "--models", a.models, "--speed", "0.9")
    run(PY, "timeline.py"); run(PY, "audio.py"); run(PY, "deliverables.py")
    edl = json.loads((ROOT / "build" / "edl.json").read_text())
    N = math.ceil(edl["total"] * 30); k = a.workers; b = [round(N * i / k) for i in range(k + 1)]
    (ROOT / "build" / "chunks").mkdir(parents=True, exist_ok=True)
    procs = [subprocess.Popen([PY, "render.py", "--start", str(b[i]), "--end", str(b[i + 1]), "--out", f"build/chunks/c{i}.mp4"], cwd=ROOT)
             for i in range(k)]
    if any(p.wait() for p in procs): sys.exit("échec du rendu")
    assemble(k)


def assemble(k=4):
    lst = ROOT / "build" / "chunks" / "list.txt"
    lst.write_text("".join(f"file 'c{i}.mp4'\n" for i in range(k)))
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "build/video.mp4")
    run("ffmpeg", "-v", "error", "-y", "-i", "build/video.mp4", "-i", "build/audio/MIX.wav",
        "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", OUT)
    print("→", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "assemble": assemble(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    else: main()
