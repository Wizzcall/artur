"""
SHORT GTA 6 — « POV : t'es en train de télécharger GTA quand t'entends ça »
Améliore le short d'origine (1080×1920) puis ajoute une pub de fin pour la vidéo longue.

    python short.py --src <dossier de travail contenant band.mp4, orig.wav>
    → ../WIZZCALL_SHORT_GTA6.mp4

Préparation (faite une fois, voir README) :
  band.mp4 = zone d'image utile (y 356→1563) stabilisée vidstab ; orig.wav = son d'origine 48 kHz.
"""
import argparse, math, subprocess, sys
from pathlib import Path
import numpy as np
import cv2
import soundfile as sf

ROOT = Path(__file__).resolve().parent
PROJ = ROOT.parent / "GTA6_PROJET_MONTAGE"
sys.path.insert(0, str(PROJ))
import fx  # noqa: E402

W, H = 1080, 1920
fx.W, fx.H = W, H                    # le moteur graphique passe en vertical
from fx import (PINK, CYAN, ORANGE, YELLOW, NAVY, WHITE, clamp, lerp, ease_out, ease_back, ease_io,  # noqa: E402
                text3d, plain_text, blit, card, fast_blur, rgb_split, light_leak)

FPS = 30
MAIN_END = 329 / 30          # durée du short d'origine (10,967 s)
DROP = 3.74                  # le « ça » : fin de la montée, début de la musique
ONSETS = [4.435, 4.621, 4.911, 5.12, 5.306, 5.666, 5.898, 6.118, 6.316, 6.548, 7.5, 7.779, 8.104, 8.464,
          8.661, 8.928, 9.218, 9.474, 9.845, 10.182]
TR = 0.40                    # transition vers la pub
AD_START = MAIN_END - 0.05
AD_LEN = 4.3
TOTAL = AD_START + AD_LEN
BAND_H = 1208
BAND_CY = 960                # centre de la zone d'image à l'écran (356 + 604)
COVER = (815, 1165)          # bande (coords de la zone) qui masque l'ancien texte incrusté


def ex(t, tau): return math.exp(-max(0.0, t) / tau) if t >= 0 else 0.0


class Band:
    def __init__(self, path):
        cap = cv2.VideoCapture(str(path)); self.f = []
        while True:
            ok, f = cap.read()
            if not ok: break
            self.f.append(f)
    def at(self, t):
        return self.f[int(clamp(t * FPS, 0, len(self.f) - 1))].astype(np.float32) / 255


def zoom_of(t):
    z = 1.0 + 0.045 * ease_io(t / DROP)                        # poussée lente pendant la montée
    z += 0.10 * ex(t - DROP, 0.20)                             # coup de zoom sur le drop
    z += sum(0.022 * ex(t - o, 0.11) for o in ONSETS)          # pulsations sur les temps forts
    return z


def shake_of(t, fi):
    g = np.random.default_rng(fi)
    amp = 22 * ex(t - DROP, 0.25) + sum(5 * ex(t - o, 0.08) for o in ONSETS)
    return g.uniform(-amp, amp), g.uniform(-amp, amp)


def grade(x):
    x = fx.grade(x, sat=1.22)
    return np.clip((x - 0.5) * 1.08 + 0.5 + 0.01, 0, 1)


def caption_lines(t):
    e3 = ease_back((t - DROP + 0.05) / 0.35, 2.2) if t >= DROP - 0.05 else 0.0
    return [
        (text3d("POV : T'ES EN TRAIN DE", "anton", 74, (255, 255, 255), (200, 225, 255), 6, (40, 20, 90), None, 0, 0.8), 1.0),
        (text3d("TÉLÉCHARGER GTA 6", "anton", 74, (255, 255, 255), (200, 225, 255), 6, (40, 20, 90), None, 0, 0.8), 1.0),
        (text3d("QUAND T'ENTENDS ÇA", "anton", 92, (255, 236, 140), (255, 60, 160), 10, (70, 18, 120), (255, 64, 160), 16, 0.8),
         1.0 + 0.35 * (1 - e3) if t >= DROP - 0.05 else 1.0),
    ]


def render_main(band, t, fi):
    f = band.at(t)
    # fond : la même image, floutée, pour remplir les bandes noires
    s = H / BAND_H
    bg = cv2.resize(f, (int(W * s), H), interpolation=cv2.INTER_LINEAR)
    x0 = (bg.shape[1] - W) // 2
    out = fast_blur(bg[:, x0:x0 + W], 28) * 0.42 + fx.sunset_bg(1) * 0.18
    # masque de l'ancien texte (dans la zone, il suit le zoom)
    c = f.copy()
    y0, y1 = COVER
    grad = np.ones((y1 - y0, 1, 1), np.float32)
    fz = 40; grad[:fz, 0, 0] = np.linspace(0, 1, fz); grad[-fz:, 0, 0] = np.linspace(1, 0, fz)
    c[y0:y1] = c[y0:y1] * (1 - 0.97 * grad) + (NAVY * 0.85) * 0.97 * grad
    c = grade(c)
    # zoom + tremblement, puis carte avec ombre portée
    z = zoom_of(t); dx, dy = shake_of(t, fi)
    M = np.array([[z, 0, W / 2 - z * W / 2 + dx], [0, z, BAND_CY - z * BAND_H / 2 + dy]], np.float32)
    lay = cv2.warpAffine(c, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    al = cv2.warpAffine(np.ones((BAND_H, W), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)
    sh = cv2.GaussianBlur(np.roll(al, 24, 0), (0, 0), 22)[..., None]
    out = out * (1 - 0.55 * sh)
    out = out * (1 - al[..., None]) + lay * al[..., None]
    edge = np.clip(al - cv2.erode(al, np.ones((5, 5), np.uint8)), 0, 1)[..., None]
    out = np.clip(out + edge * PINK * 0.8, 0, 1)
    # nouveau sous-titre (même position que l'ancien, suit le zoom)
    cy = BAND_CY + (990 - BAND_H / 2) * z + dy
    for i, (spr, sc) in enumerate(caption_lines(t)):
        out = blit(out, spr, W / 2 - 20 + dx, cy - 110 + i * 100 + (8 if i == 2 else 0), sc, 1.0)
    # en-tête (au-dessus de l'image)
    e = ease_out(t / 0.5)
    hd = text3d("GTA VI", "anton", 130, (255, 236, 140), (255, 60, 160), 12, (70, 18, 120), (255, 64, 160), 20, 0.7)
    out = blit(out, hd, W / 2, 190 - (1 - e) * 60, 1.0 + 0.03 * ex(t - DROP, 0.3), e)
    sub = plain_text("PRÉCHARGEMENT EN COURS SUR PS5", "bebas", 44, (255, 255, 255), spacing=7, glow=(60, 200, 255), glow_r=8)
    out = blit(out, sub, W / 2, 292, 1.0, e)
    # effets du drop : flash, aberration chromatique, fuite de lumière
    fl = ex(t - DROP, 0.12)
    if fl > 0.01:
        out = rgb_split(out, 26 * fl)
        out = np.clip(out + 0.75 * fl, 0, 1)
    if DROP <= t <= DROP + 0.9:
        out = light_leak(out, (t - DROP) / 0.9, True, 0.9)
    out = np.clip(out + sum(0.06 * ex(t - o, 0.07) for o in ONSETS), 0, 1)
    return out


THUMB = None


def render_ad(t, fi):
    global THUMB
    lt = t - AD_START
    out = fx.synth_grid(lt, 0.60) * 0.85
    a = ease_back((lt - 0.05) / 0.45, 1.6)
    t1 = text3d("LA VIDÉO COMPLÈTE", "anton", 104, (255, 236, 140), (255, 60, 160), 12, (70, 18, 120), (255, 64, 160), 18, 0.7)
    out = blit(out, t1, W / 2, 330, 0.6 + 0.4 * a, clamp(lt / 0.15))
    b = ease_back((lt - 0.2) / 0.45, 1.6)
    t2 = text3d("EST DISPO !", "anton", 120, (140, 240, 255), (90, 120, 255), 12, (30, 20, 90), (60, 200, 255), 20, 0.7)
    out = blit(out, t2, W / 2, 470, 0.6 + 0.4 * b, clamp((lt - 0.2) / 0.15))
    if THUMB is None:
        im = cv2.imread(str(ROOT.parent / "GTA6_MINIATURE_1920.png")).astype(np.float32) / 255
        THUMB = card(cv2.resize(im, (940, 529), interpolation=cv2.INTER_AREA), r=24, border=6)
    c = ease_back((lt - 0.3) / 0.55, 1.5)
    fy = 870 + 10 * math.sin(lt * 3)
    out = blit(out, THUMB, W / 2, fy, 0.55 + 0.45 * c, clamp((lt - 0.3) / 0.2), -3)
    if lt > 0.7:  # bouton lecture qui pulse
        p = 1 + 0.08 * math.sin((lt - 0.7) * 8)
        r = int(78 * p * ease_back((lt - 0.7) / 0.35, 2))
        cv2.circle(out, (W // 2, int(fy)), max(1, r), tuple(float(x) for x in PINK), -1, cv2.LINE_AA)
        k = r / 78
        tri = np.array([[W / 2 - 22 * k, fy - 34 * k], [W / 2 - 22 * k, fy + 34 * k], [W / 2 + 36 * k, fy]], np.int32)
        cv2.fillPoly(out, [tri], (1, 1, 1), cv2.LINE_AA)
    d = ease_out((lt - 0.8) / 0.4)
    l1 = plain_text("9 MIN  ·  TOUT SAVOIR AVANT LA SORTIE", "bebas", 52, (255, 255, 255), spacing=5, glow=(255, 64, 160), glow_r=8)
    out = blit(out, l1, W / 2, 1210 + (1 - d) * 30, 1.0, d)
    # avatar de la chaîne + nom
    e = ease_back((lt - 1.0) / 0.4, 1.8)
    if e > 0:
        av = cv2.imread(str(ROOT.parent / "WIZZCALL_PROFIL_800.png")).astype(np.float32) / 255
        sz = 170; av = cv2.resize(av, (sz, sz), interpolation=cv2.INTER_AREA)
        m = np.zeros((sz, sz), np.float32); cv2.circle(m, (sz // 2, sz // 2), sz // 2 - 2, 1.0, -1, cv2.LINE_AA)
        spr = np.dstack([av, m])
        out = blit(out, spr, W / 2 - 170, 1390, e, clamp(e))
        cv2.circle(out, (W // 2 - 170, 1390), int(88 * clamp(e, 0, 1.2)), tuple(float(x) for x in PINK), 5, cv2.LINE_AA)
        nm = text3d("WIZZCALL", "anton", 86, (255, 255, 255), (140, 240, 255), 8, (30, 20, 90), (60, 200, 255), 14, 0.7)
        out = blit(out, nm, W / 2 - 60, 1390, 1.0, clamp(e), anchor="l")
    # flèche vers le lien de la vidéo liée
    g = ease_out((lt - 1.3) / 0.4)
    if g > 0:
        l2 = text3d("REGARDE-LA ICI", "anton", 70, (255, 236, 140), (255, 140, 70), 6, (70, 18, 120), None, 0, 0.7)
        out = blit(out, l2, W / 2, 1560, 1.0, g)
        by = 1660 + 18 * math.sin(lt * 9)
        pts = np.array([[W / 2 - 50, by], [W / 2 + 50, by], [W / 2, by + 60]], np.int32)
        cv2.fillPoly(out, [pts], tuple(float(x) for x in YELLOW), cv2.LINE_AA)
        cv2.rectangle(out, (W // 2 - 16, int(by) - 50), (W // 2 + 16, int(by)), tuple(float(x) for x in YELLOW), -1)
    return np.clip(out, 0, 1)


def render(band, fi):
    t = fi / FPS
    if t < AD_START - TR / 2:
        f = render_main(band, t, fi)
    elif t >= AD_START + TR / 2:
        f = render_ad(t, fi)
    else:  # transition zoom + flash vers la pub
        p = (t - (AD_START - TR / 2)) / TR
        if p < 0.5:
            q = ease_out(p * 2, 2) if False else (p * 2) ** 2
            f = fx.zoom_blur(cv2.warpAffine(render_main(band, min(t, MAIN_END - 0.034), fi),
                                            cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1 + 0.6 * q), (W, H),
                                            borderMode=cv2.BORDER_REFLECT), 0.22 * q)
        else:
            q = ease_out((p - 0.5) * 2, 2)
            f = cv2.warpAffine(render_ad(t, fi), cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1.35 - 0.35 * q), (W, H),
                               borderMode=cv2.BORDER_REFLECT)
        f = np.clip(f + max(0.0, 1 - abs(p - 0.5) * 5) * 0.8, 0, 1)
    return fx.finish(f, fi)


def build_audio(src, out_wav):
    SR = 48000
    o, sr = sf.read(src / "orig.wav", always_2d=True)
    N = int((TOTAL + 0.3) * SR)
    mix = np.zeros((N, 2))
    L = min(len(o), int(MAIN_END * SR))
    o = o[:L].copy(); fo = int(0.25 * SR); o[-fo:] *= np.linspace(1, 0, fo)[:, None]
    mix[:L] += o
    A = PROJ / "build" / "audio"

    def put(name, t, g):
        x, _ = sf.read(A / f"{name}.wav", always_2d=True)
        i = int(t * SR); j = min(N, i + len(x)); mix[i:j] += x[:j - i] * g
    put("sfx_boom", DROP, 0.45)               # renfort grave sur le drop
    put("sfx_whoosh_zoom", AD_START - 0.45, 0.6)
    put("sfx_impact_s", AD_START, 0.7)
    put("sfx_click", AD_START + 0.75, 0.5)    # bouton lecture
    put("sfx_ui", AD_START + 1.0, 0.5)        # avatar
    # musique originale du montage long (passage « épique ») sous la pub
    mu, _ = sf.read(A / "music_outro.wav", always_2d=True)
    s0 = int(40.0 * SR); seg = mu[s0:s0 + int((AD_LEN + 0.3) * SR)].copy()
    fi_, fo_ = int(0.12 * SR), int(0.5 * SR)
    seg[:fi_] *= np.linspace(0, 1, fi_)[:, None]; seg[-fo_:] *= np.linspace(1, 0, fo_)[:, None]
    seg = seg / (np.sqrt((seg ** 2).mean()) + 1e-9) * 10 ** (-18 / 20)
    i = int(AD_START * SR); mix[i:i + len(seg)] += seg[:N - i]
    mix = np.tanh(mix * 1.05) / np.tanh(1.05)
    sf.write(out_wav, mix.astype(np.float32), SR)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True)
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args(); src = Path(a.src)
    band = Band(src / "band.mp4")
    if a.preview is not None:
        for t in a.preview:
            f = render(band, int(round(t * FPS)))
            cv2.imwrite(str(src / f"pv_{t:05.2f}.jpg"), (f * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 90])
        return
    build_audio(src, src / "short_mix.wav")
    vid = src / "short_video.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", str(vid)],
                         stdin=subprocess.PIPE)
    for fi in range(int(math.ceil(TOTAL * FPS))):
        p.stdin.write((np.clip(render(band, fi), 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vid), "-i", str(src / "short_mix.wav"), "-map", "0:v", "-map", "1:a",
                    "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", str(ROOT.parent / "WIZZCALL_SHORT_GTA6.mp4")], check=True)
    print("ok", round(TOTAL, 2), "s")


if __name__ == "__main__":
    main()
