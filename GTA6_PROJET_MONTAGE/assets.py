"""
Catalogue des médias + préparation (cache) :
  - images redimensionnées (≥ 1.5× la sortie pour les mouvements de caméra)
  - détourage IS-Net (masque du premier plan) pour la parallaxe 2.5D
  - arrière-plan « nettoyé » (inpainting) derrière le sujet détouré
  - clips vidéo décodés en tableaux (ralenti par interpolation de mouvement)

    python assets.py --media <dossier médias> --models <dossier onnx>
"""
import argparse, json, subprocess
from pathlib import Path
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "build" / "cache"
MEDIA = Path(json.loads((ROOT / "media_path.json").read_text())["media"]) if (ROOT / "media_path.json").exists() else None

SEL, PACK = "sel/Images", "pack"
IMAGES = {
    # personnages (officiel)
    "boobie_s":  f"{SEL}/Characters/Boobie_Ike_01_screenshot.jpg",
    "boobie_l":  f"{SEL}/Characters/Boobie_Ike_landscape.jpg",
    "brian_l":   f"{SEL}/Characters/Brian_Heder_landscape.jpg",
    "cal_l":     f"{SEL}/Characters/Cal_Hampton_landscape.jpg",
    "drequan_l": f"{SEL}/Characters/DreQuan_Priest_landscape.jpg",
    "jason":     f"{SEL}/Characters/Jason_Duval_01_screenshot.jpg",
    "jl_l":      f"{SEL}/Characters/Jason_and_Lucia_01_landscape.jpg",
    "jl_s":      f"{SEL}/Characters/Jason_and_Lucia_01_screenshot.jpg",
    "jl8":       f"{SEL}/Characters/Jason_and_Lucia_08_screenshot.jpg",
    "jl_beach":  f"{SEL}/Characters/Jason_and_Lucia_Beach_landscape.jpg",
    "jl_rob":    f"{SEL}/Characters/Jason_and_Lucia_Robbery_landscape.jpg",
    "lucia":     f"{SEL}/Characters/Lucia_Caminos_01_screenshot.jpg",
    "cover":     f"{SEL}/Characters/Official_Cover_Art_landscape.jpg",
    "dimez":     f"{SEL}/Characters/Real_Dimez_01_screenshot.jpg",
    # lieux
    "ambrosia":  f"{SEL}/Locations/Ambrosia_01_screenshot.jpg",
    "keys":      f"{SEL}/Locations/Leonida_Keys_01_screenshot.jpg",
    "kalaga":    f"{SEL}/Locations/Mount_Kalaga_National_Park_01_screenshot.jpg",
    "portg":     f"{SEL}/Locations/Port_Gellhorn_01_screenshot.jpg",
    "vicecity":  f"{SEL}/Locations/Vice_City_01_screenshot.jpg",
    # Ultimate Edition
    "ue_main":      f"{SEL}/Ultimate_Edition/ULTIMATE_EDITION_01.jpg",
    "ue_cheetah":   f"{SEL}/Ultimate_Edition/ULTIMATE_EDITION_GROTTI_CHEETAH_01.jpg",
    "ue_safehouse": f"{SEL}/Ultimate_Edition/ULTIMATE_EDITION_SAFEHOUSE_VEHICLES_01.jpg",
    "ue_squalo":    f"{SEL}/Ultimate_Edition/ULTIMATE_EDITION_SQUALO_01.jpg",
    "ue_style":     f"{SEL}/Ultimate_Edition/ULTIMATE_EDITION_VICE_CITY_STYLE_01.jpg",
    "ue_wyman":     f"{SEL}/Ultimate_Edition/ULTIMATE_EDITION_WYMAN_CAR_COLLECTION_01.jpg",
    # Vintage Vice City Pack (4K)
    "vp1":    f"{PACK}/VINTAGE_VICE_CITY_PACK_01.jpg",
    "vp2":    f"{PACK}/VINTAGE_VICE_CITY_PACK_02.jpg",
    "vl1":    f"{PACK}/VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_01.jpg",
    "vl2":    f"{PACK}/VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_02.jpg",
    "vl3":    f"{PACK}/VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_03.jpg",
    "vl4":    f"{PACK}/VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_04.jpg",
    "vl5":    f"{PACK}/VINTAGE_VICE_CITY_PACK_EXCLUSIVE_LOOKS_05.jpg",
    "vs1":    f"{PACK}/VINTAGE_VICE_CITY_PACK_VAPID_STANIER_01.jpg",
    "vs2":    f"{PACK}/VINTAGE_VICE_CITY_PACK_VAPID_STANIER_02.jpg",
    "vs3":    f"{PACK}/VINTAGE_VICE_CITY_PACK_VAPID_STANIER_03.jpg",
    "vs4":    f"{PACK}/VINTAGE_VICE_CITY_PACK_VAPID_STANIER_04.jpg",
    "weapon": f"{PACK}/VINTAGE_VICE_CITY_WEAPON_PATTERN_01.jpg",
}
CLIPS = {
    "reveal":    "sel/Videos/GTA6_Logo_and_Cover_Reveal.mp4",
    "c_jason":   "sel/Videos/Jason_Duval_Video_Clip.mp4",
    "c_lucia":   "sel/Videos/Lucia_Caminos_Video_Clip.mp4",
    "c_boobie":  "sel/Videos/Boobie_Ike_Video_Clip.mp4",
    "c_brian":   "sel/Videos/Brian_Heder_Video_Clip.mp4",
    "c_cal":     "sel/Videos/Cal_Hampton_Video_Clip.mp4",
    "c_drequan": "sel/Videos/DreQuan_Priest_Video_Clip.mp4",
    "c_dimez":   "sel/Videos/Real_Dimez_Video_Clip.mp4",
    "c_raul":    "sel/Videos/Raul_Bautista_Video_Clip.mp4",
}
# images où un sujet net se détache (détourage utile)
CUTOUT = ["jason", "lucia", "jl_l", "jl_s", "jl8", "jl_beach", "jl_rob", "cal_l", "boobie_l", "boobie_s",
          "drequan_l", "brian_l", "dimez", "vp1", "vp2", "vl1", "vl2", "vl3", "vl4", "vl5", "vs2",
          "vicecity", "ue_main", "ue_style", "ue_cheetah", "ue_wyman", "ambrosia", "kalaga", "cover"]
SLOWMO = 3   # facteur de ralenti des clips personnages (interpolation de mouvement)

PREP_W = 2880  # largeur de travail (1.5 × 1920)


def isnet_mask(img_bgr, sess):
    h, w = img_bgr.shape[:2]
    x = cv2.resize(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32)
    x = x / max(1.0, x.max()) - 0.5
    x = x.transpose(2, 0, 1)[None]
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    out = (out - out.min()) / (out.max() - out.min() + 1e-6)
    m = cv2.resize(out, (w, h), interpolation=cv2.INTER_CUBIC)
    return np.clip(m, 0, 1)


def prep_image(key, src):
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    nw = PREP_W; nh = int(round(h * nw / w))
    if w >= nw:
        img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
        blur = cv2.GaussianBlur(img, (0, 0), 2.0)
        img = cv2.addWeighted(img, 1.45, blur, -0.45, 0)  # netteté après upscale
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--models", required=True)
    a = ap.parse_args()
    media = Path(a.media)
    (ROOT / "media_path.json").write_text(json.dumps({"media": str(media.resolve())}))
    CACHE.mkdir(parents=True, exist_ok=True)
    import onnxruntime as ort
    sess = ort.InferenceSession(str(Path(a.models) / "isnet-general-use.onnx"), providers=["CPUExecutionProvider"])
    report = {}
    for k, rel in IMAGES.items():
        src = media / rel
        ok = src.exists() and cv2.imread(str(src)) is not None
        report[k] = dict(file=rel, ok=bool(ok))
        if not ok:
            print("MANQUANT/CORROMPU", rel); continue
        img = prep_image(k, src)
        cv2.imwrite(str(CACHE / f"{k}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 96])
        if k in CUTOUT:
            m = isnet_mask(img, sess)
            m8 = (m * 255).astype(np.uint8)
            cv2.imwrite(str(CACHE / f"{k}_mask.png"), m8)
            # arrière-plan sans sujet : inpainting sur une version réduite puis remontée
            small = cv2.resize(img, (img.shape[1] // 4, img.shape[0] // 4), interpolation=cv2.INTER_AREA)
            ms = cv2.resize(m8, (small.shape[1], small.shape[0]))
            ms = cv2.dilate((ms > 40).astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
            bg = cv2.inpaint(small, ms, 12, cv2.INPAINT_TELEA)
            bg = cv2.resize(bg, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_CUBIC)
            mb = cv2.GaussianBlur(cv2.dilate(m8, np.ones((25, 25), np.uint8)), (0, 0), 8)[..., None] / 255.0
            bg = (img * (1 - mb) + bg * mb).astype(np.uint8)
            cv2.imwrite(str(CACHE / f"{k}_bg.jpg"), bg, [cv2.IMWRITE_JPEG_QUALITY, 94])
        print("ok", k, img.shape)
    for k, rel in CLIPS.items():
        src = media / rel
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                           capture_output=True, text=True)
        ok = src.exists() and r.returncode == 0 and float(r.stdout.strip() or 0) > 0
        report[k] = dict(file=rel, ok=bool(ok), duration=float(r.stdout.strip() or 0))
        if not ok:
            print("MANQUANT/CORROMPU", rel); continue
        out = CACHE / f"{k}.mp4"
        if k == "reveal":
            vf = "scale=1920:1080:flags=lanczos,unsharp=5:5:0.6"
        else:  # ralenti x3 par interpolation de mouvement, puis 1080 de haut
            vf = (f"setpts={SLOWMO}*PTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
                  "scale=-2:1080:flags=lanczos,unsharp=5:5:0.5")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", vf, "-an", "-c:v", "libx264",
                        "-crf", "12", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)], check=True)
        print("ok", k)
    (ROOT / "build" / "media_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
