"""
Boîte à outils graphique : chargement des médias, caméra virtuelle, parallaxe 2.5D,
textes 3D (extrusion, dégradé, néon, ombre portée), cartes, étalonnage, grain.
Tout travaille en float32 BGR [0,1] en 1920×1080.
"""
from functools import lru_cache
from pathlib import Path
import math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "build" / "cache"
FONTS = ROOT / "fonts"
W, H = 1920, 1080

# palette Vice City (BGR float)
def C(r, g, b): return np.array([b, g, r], np.float32) / 255
PINK, MAGENTA, ORANGE, YELLOW = C(255, 64, 160), C(230, 40, 200), C(255, 140, 70), C(255, 214, 102)
CYAN, BLUE, PURPLE, NAVY = C(60, 220, 255), C(60, 110, 255), C(120, 50, 210), C(14, 8, 38)
WHITE, BLACK = C(255, 255, 255), C(0, 0, 0)
RGB = lambda c: tuple(int(v * 255) for v in c[::-1])


# ═══════════════════════════════════════════ easing
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_io(x): x = clamp(x); return 0.5 - 0.5 * math.cos(math.pi * x)
def ease_out(x, p=3): x = clamp(x); return 1 - (1 - x) ** p
def ease_in(x, p=3): x = clamp(x); return x ** p
def ease_back(x, s=1.6): x = clamp(x) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2
def lerp(a, b, u): return a + (b - a) * u
def env(lt, dur, a=0.3, r=0.3):
    return clamp(min(lt / a if a > 0 else 1, (dur - lt) / r if r > 0 else 1))


# ═══════════════════════════════════════════ médias
@lru_cache(maxsize=24)
def img(key, level=2880):
    im = cv2.imread(str(CACHE / f"{key}.jpg"), cv2.IMREAD_COLOR)
    if level != im.shape[1]:
        im = cv2.resize(im, (level, int(im.shape[0] * level / im.shape[1])), interpolation=cv2.INTER_AREA)
    return im.astype(np.float32) / 255


@lru_cache(maxsize=24)
def bgimg(key, level=2880):
    p = CACHE / f"{key}_bg.jpg"
    if not p.exists(): return img(key, level)
    im = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if level != im.shape[1]:
        im = cv2.resize(im, (level, int(im.shape[0] * level / im.shape[1])), interpolation=cv2.INTER_AREA)
    return im.astype(np.float32) / 255


@lru_cache(maxsize=24)
def mask(key, level=2880):
    p = CACHE / f"{key}_mask.png"
    if not p.exists(): return None
    m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    if level != m.shape[1]:
        m = cv2.resize(m, (level, int(m.shape[0] * level / m.shape[1])), interpolation=cv2.INTER_AREA)
    m = m.astype(np.float32) / 255
    return np.clip((m - 0.08) / 0.84, 0, 1)


def has_mask(key): return (CACHE / f"{key}_mask.png").exists()


class Video:
    """Lecture séquentielle avec mémoire de la dernière image (rendu dans l'ordre)."""
    _open = {}

    @classmethod
    def get(cls, key):
        if key not in cls._open: cls._open[key] = cls(key)
        return cls._open[key]

    def __init__(self, key):
        self.path = str(CACHE / f"{key}.mp4")
        self.cap = cv2.VideoCapture(self.path)
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.idx = -1; self.frames = {}

    def frame(self, i):
        i = int(clamp(i, 0, self.n - 1))
        if i in self.frames: return self.frames[i]
        if i < self.idx or i > self.idx + 60:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, i); self.idx = i - 1
        f = None
        while self.idx < i:
            ok, f = self.cap.read()
            if not ok: break
            self.idx += 1
        if f is None: return self.frames.get(max(self.frames) if self.frames else 0, np.zeros((H, W, 3), np.float32))
        f = f.astype(np.float32) / 255
        self.frames[i] = f
        for k in [k for k in self.frames if k < i - 3]: del self.frames[k]
        return f

    def at(self, fi):
        """image à l'index fractionnaire (fondu entre images voisines)"""
        a = math.floor(fi); w = fi - a
        fa = self.frame(a)
        if w < 0.05 or a + 1 >= self.n: return fa
        return cv2.addWeighted(fa, 1 - w, self.frame(a + 1), w, 0)


# ═══════════════════════════════════════════ caméra
def fit_rect(aspect_src, crop=(0, 0, 1, 1)):
    """plus grand rectangle 16:9 (coords normalisées) dans la zone crop"""
    x0, y0, x1, y1 = crop
    cw, ch = (x1 - x0), (y1 - y0) * (1 / aspect_src)  # en unités « largeur »
    target = H / W
    if ch / cw > target:
        w = cw; h = w * target
    else:
        h = ch; w = h / target
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx, cy, w  # centre normalisé, largeur normalisée


def move_rect(base, move, u, amt=0.13):
    cx, cy, w = base
    if move == "in":
        s = lerp(1.0, 1 - amt, u); return cx, lerp(cy, cy - 0.02, u), w * s
    if move == "out":
        s = lerp(1 - amt, 1.0, u); return cx, lerp(cy - 0.02, cy, u), w * s
    sw = w * (1 - amt * 0.85); room = (w - sw) / 2
    if move == "left": return lerp(cx + room, cx - room, u), cy, sw
    if move == "right": return lerp(cx - room, cx + room, u), cy, sw
    if move == "up": return cx, lerp(cy + room * 0.5, cy - room * 0.5, u), sw
    return cx, cy, w


def view(src, rect, out=(W, H), interp=cv2.INTER_LINEAR, border=cv2.BORDER_REFLECT):
    """rend la zone rect=(cx,cy,w) (normalisée sur la largeur source) en sortie"""
    sh, sw = src.shape[:2]
    cx, cy, w = rect
    ow, oh = out
    s = ow / (w * sw)
    M = np.array([[s, 0, ow / 2 - s * cx * sw], [0, s, oh / 2 - s * cy * sh]], np.float32)
    return cv2.warpAffine(src, M, (ow, oh), flags=interp, borderMode=border)


def level_for(rect_w, srcw=2880):
    return 1920 if rect_w * 2880 > 2300 else 2880


def kb_frame(key, rect):
    lv = level_for(rect[2])
    return view(img(key, lv), rect)


# ═══════════════════════════════════════════ flous rapides
def fast_blur(x, sigma):
    if sigma < 1: return x
    k = 4
    small = cv2.resize(x, (x.shape[1] // k, x.shape[0] // k), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / k)
    return cv2.resize(small, (x.shape[1], x.shape[0]), interpolation=cv2.INTER_LINEAR)


def motion_blur(x, length, horizontal=True):
    L = int(abs(length))
    if L < 3: return x
    L = min(L, 301)
    k = (L, 1) if horizontal else (1, L)
    small = cv2.resize(x, (x.shape[1] // 2, x.shape[0] // 2), interpolation=cv2.INTER_AREA)
    small = cv2.blur(small, (max(1, k[0] // 2), max(1, k[1] // 2)))
    return cv2.resize(small, (x.shape[1], x.shape[0]), interpolation=cv2.INTER_LINEAR)


def zoom_blur(x, strength, n=5):
    if strength < 0.01: return x
    acc = x.copy()
    for i in range(1, n):
        s = 1 + strength * i / n
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
        acc += cv2.warpAffine(x, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    return acc / n


def scale_frame(x, s, dx=0, dy=0, border=cv2.BORDER_REFLECT):
    M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s); M[0, 2] += dx; M[1, 2] += dy
    return cv2.warpAffine(x, M, (W, H), borderMode=border)


# ═══════════════════════════════════════════ fonds graphiques
@lru_cache(maxsize=8)
def sunset_bg(variant=0):
    y = np.linspace(0, 1, H)[:, None, None]
    if variant == 0:
        top, mid, bot = C(20, 10, 60), C(150, 30, 140), C(255, 120, 90)
    elif variant == 1:
        top, mid, bot = C(6, 6, 24), C(40, 18, 90), C(150, 40, 150)
    else:
        top, mid, bot = C(10, 20, 60), C(30, 90, 170), C(255, 90, 160)
    g = np.where(y < 0.6, top + (mid - top) * (y / 0.6), mid + (bot - mid) * ((y - 0.6) / 0.4))
    return np.broadcast_to(g, (H, W, 3)).astype(np.float32).copy()


@lru_cache(maxsize=4)
def _sun_layer(horizon=0.62, sun=True):
    out = sunset_bg(1).copy()
    hy = int(H * horizon)
    if sun:
        cx, cy, r = W // 2, hy - 30, 260
        yy, xx = np.ogrid[:H, :W]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        disk = np.clip((r - d) / 2, 0, 1)
        rel = (yy - cy).astype(np.float32)
        stripes = (rel > 0) & ((rel % 24) < (2 + rel / r * 14))
        disk = disk * (~np.broadcast_to(stripes, disk.shape))
        grad = np.clip((yy - (cy - r)) / (2 * r), 0, 1)[..., None]
        suncol = YELLOW * (1 - grad) + PINK * grad
        glow = np.clip(1 - d / (r * 2.4), 0, 1) ** 2
        out = out + PINK * glow[..., None] * 0.35
        out = out * (1 - disk[..., None]) + suncol * disk[..., None]
    out[hy:] = sunset_bg(1)[hy:] * 0.35
    return np.clip(out, 0, 1).astype(np.float32)


def synth_grid(t, horizon=0.62, color=PINK, speed=0.6, alpha=0.9, sun=True, bg=None):
    """sol en grille néon façon synthwave, qui défile vers la caméra + soleil rayé"""
    out = _sun_layer(horizon, sun).copy() if bg is None else bg.copy()
    hy = int(H * horizon)
    lay = np.zeros((H // 2, W // 2), np.uint8)
    h2, w2, hy2 = H // 2, W // 2, hy // 2
    for k in range(-24, 25):
        cv2.line(lay, (int(w2 / 2 + k * 20), hy2), (int(w2 / 2 + k * 210), h2 + 100), 255, 1, cv2.LINE_AA)
    off = (t * speed) % 1.0
    for j in range(40):
        z = j + 1 - off
        if z <= 0.98: continue
        y = hy2 + (h2 - hy2) / z
        cv2.line(lay, (0, int(y)), (w2, int(y)), 255, 1, cv2.LINE_AA)
    cv2.line(lay, (0, hy2), (w2, hy2), 255, 2, cv2.LINE_AA)
    g = cv2.resize(lay, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
    fade = np.clip((np.arange(H, dtype=np.float32) - hy) / (H - hy) * 1.8 + 0.25, 0, 1)[:, None]
    fade[:hy - 2] = 0
    g = g * fade
    glow = fast_blur(g[..., None].repeat(3, 2), 10)[..., 0]
    out = out + (g * alpha + glow * 1.2)[..., None] * color
    return np.clip(out, 0, 1)


def darken_blur_bg(frame, sigma=18, dark=0.45, tint=None):
    b = fast_blur(frame, sigma) * dark
    if tint is not None: b = b * 0.75 + tint * 0.25 * dark
    return b


# ═══════════════════════════════════════════ texte
@lru_cache(maxsize=16)
def font(name, size, var=None):
    path = {"anton": "Anton-Regular.ttf", "bebas": "BebasNeue-Regular.ttf", "script": "Pacifico-Regular.ttf",
            "mont": "Montserrat.ttf", "monoton": "Monoton-Regular.ttf"}[name]
    f = ImageFont.truetype(str(FONTS / path), size)
    if name == "mont":
        try: f.set_variation_by_name(var or "Bold")
        except Exception: pass
    return f


def _mask_text(text, fnt, spacing=0, pad=0):
    if spacing:
        widths = [fnt.getbbox(c)[2] - fnt.getbbox(c)[0] if c != " " else fnt.size * 0.3 for c in text]
        tw = int(sum(widths) + spacing * (len(text) - 1))
    else:
        bb = fnt.getbbox(text); tw = bb[2] - bb[0]
    asc, desc = fnt.getmetrics()
    th = asc + desc
    im = Image.new("L", (tw + 2 * pad, th + 2 * pad), 0)
    d = ImageDraw.Draw(im)
    if spacing:
        x = pad
        for c, w_ in zip(text, widths):
            if c != " ":
                d.text((x - fnt.getbbox(c)[0], pad), c, font=fnt, fill=255)
            x += w_ + spacing
    else:
        d.text((pad - fnt.getbbox(text)[0], pad), text, font=fnt, fill=255)
    return np.array(im).astype(np.float32) / 255


@lru_cache(maxsize=256)
def text3d(text, fname="anton", size=160, top=(255, 214, 102), bot=(255, 64, 160), depth=14, side=(70, 20, 120),
           glow=(255, 64, 160), glow_r=18, shadow=0.6, stroke=0, stroke_col=(255, 255, 255), spacing=0, var=None,
           angle=(0.6, 1.0)):
    """Texte 3D : extrusion ombrée, face en dégradé, liseré, halo néon et ombre portée.
    Renvoie un sprite RGBA float (BGR + alpha), prémultiplié."""
    fnt = font(fname, size, var)
    pad = int(depth + glow_r * 2.5 + 30)
    m = _mask_text(text, fnt, spacing, pad)
    h, w = m.shape
    rgb = np.zeros((h, w, 3), np.float32); a = np.zeros((h, w), np.float32)
    # ombre portée réaliste (décalée, floue)
    if shadow:
        sh = cv2.GaussianBlur(np.roll(np.roll(m, int(depth * 0.9 + 10), 0), int(depth * 0.6 + 8), 1), (0, 0), 10) * shadow
        a = np.maximum(a, sh)
    # halo néon
    if glow:
        g = cv2.GaussianBlur(m, (0, 0), glow_r)
        gc = np.array(glow[::-1], np.float32) / 255
        rgb = rgb * (1 - g[..., None] * 0.9) + gc * g[..., None] * 0.9
        a = np.maximum(a, g * 0.85)
    # extrusion
    sc = np.array(side[::-1], np.float32) / 255
    dx, dy = angle
    for k in range(depth, 0, -1):
        mk = np.roll(np.roll(m, int(round(k * dy)), 0), int(round(k * dx)), 1)
        shade = 0.45 + 0.55 * (1 - k / max(1, depth))
        rgb = rgb * (1 - mk[..., None]) + (sc * shade) * mk[..., None]
        a = np.maximum(a, mk)
    # liseré
    if stroke:
        st = cv2.dilate(m, np.ones((stroke * 2 + 1, stroke * 2 + 1), np.uint8))
        scol = np.array(stroke_col[::-1], np.float32) / 255
        rgb = rgb * (1 - st[..., None]) + scol * st[..., None]; a = np.maximum(a, st)
    # face avant en dégradé + reflet
    ys = np.nonzero(m.max(1) > 0.5)[0]
    y0, y1 = (ys[0], ys[-1]) if len(ys) else (0, h)
    gy = np.clip((np.arange(h) - y0) / max(1, y1 - y0), 0, 1)[:, None, None]
    tc = np.array(top[::-1], np.float32) / 255; bc = np.array(bot[::-1], np.float32) / 255
    face = tc * (1 - gy) + bc * gy
    face = face + (gy < 0.48) * 0.08
    rgb = rgb * (1 - m[..., None]) + face * m[..., None]
    a = np.maximum(a, m)
    return np.dstack([rgb, a]).astype(np.float32)


def plain_text(text, fname="mont", size=48, color=(255, 255, 255), shadow=0.7, spacing=0, var=None, glow=None, glow_r=10):
    return text3d(text, fname, size, color, color, 0, (0, 0, 0), glow, glow_r if glow else 0, shadow, 0, (0, 0, 0), spacing, var)


def blit(frame, spr, cx, cy, scale=1.0, alpha=1.0, rot=0.0, anchor="c"):
    """colle un sprite RGBA (non prémultiplié par alpha global) centré en (cx,cy)"""
    if alpha <= 0.003 or scale <= 0.01: return frame
    h, w = spr.shape[:2]
    if anchor == "l": cx = cx + w * scale / 2
    if anchor == "r": cx = cx - w * scale / 2
    if abs(scale - 1) < 1e-3 and abs(rot) < 1e-3:
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        sx0, sy0 = max(0, -x0), max(0, -y0)
        X0, Y0 = max(0, x0), max(0, y0)
        X1, Y1 = min(W, x0 + w), min(H, y0 + h)
        if X1 <= X0 or Y1 <= Y0: return frame
        s = spr[sy0:sy0 + (Y1 - Y0), sx0:sx0 + (X1 - X0)]
    else:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, scale)
        M[0, 2] += cx - w / 2; M[1, 2] += cy - h / 2
        corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], np.float32) @ M.T
        bx0, by0 = corners.min(0); bx1, by1 = corners.max(0)
        X0, Y0 = int(max(0, math.floor(bx0))), int(max(0, math.floor(by0)))
        X1, Y1 = int(min(W, math.ceil(bx1))), int(min(H, math.ceil(by1)))
        if X1 <= X0 or Y1 <= Y0: return frame
        M[0, 2] -= X0; M[1, 2] -= Y0
        s = cv2.warpAffine(spr, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    a = s[..., 3:4] * alpha
    roi = frame[Y0:Y1, X0:X1]
    frame[Y0:Y1, X0:X1] = roi * (1 - a) + s[..., :3] * a
    return frame


# ═══════════════════════════════════════════ cartes / calques
@lru_cache(maxsize=32)
def rounded_alpha(w, h, r=24):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1); cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for (x, y) in [(r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)]:
        cv2.circle(m, (x, y), r, 255, -1, cv2.LINE_AA)
    return m.astype(np.float32) / 255


def card(content, r=22, border=4, border_col=WHITE, shadow=True):
    """contenu BGR → sprite RGBA avec coins arrondis, liseré et ombre douce"""
    h, w = content.shape[:2]
    pad = 60
    out = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.float32)
    al = rounded_alpha(w, h, r)
    if shadow:
        sh = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
        sh[pad + 22:pad + 22 + h, pad + 14:pad + 14 + w] = al
        sh = cv2.GaussianBlur(sh, (0, 0), 18) * 0.75
        out[..., 3] = sh
    c = content.copy()
    if border:
        inner = cv2.erode(al, np.ones((border * 2 + 1, border * 2 + 1), np.uint8))
        edge = np.clip(al - inner, 0, 1)[..., None]
        c = c * (1 - edge) + border_col * edge
    sl = (slice(pad, pad + h), slice(pad, pad + w))
    out[sl][..., :3] = c * al[..., None]
    out[sl][..., 3] = np.maximum(out[sl][..., 3], al)
    # dé-prémultiplier pour blit
    a = np.maximum(out[..., 3:4], 1e-4)
    out[..., :3] = np.where(out[..., 3:4] > 1e-4, out[..., :3] / a, 0)
    # ombre = noir
    return out


def composite_layer(frame, layer_rgb, alpha):
    a = alpha[..., None] if alpha.ndim == 2 else alpha
    return frame * (1 - a) + layer_rgb * a


# ═══════════════════════════════════════════ étalonnage / finitions
def _lut():
    x = np.arange(256, dtype=np.float32) / 255
    s = np.clip(0.5 + (x - 0.5) * 1.07, 0, 1)
    s = s + 0.035 * np.sin(2 * np.pi * s) * -0.6  # légère courbe en S
    b = s + 0.045 * (1 - s) ** 2.2 - 0.01 * s ** 2      # ombres bleutées
    g = s - 0.012 * (1 - s) ** 2 - 0.008 * s ** 2
    r = s + 0.035 * s ** 2.0 + 0.006                    # hautes lumières chaudes/roses
    lut = np.stack([b, g, r], 1)
    return (np.clip(lut, 0, 1) * 255).astype(np.uint8)


LUT = _lut().reshape(256, 1, 3)


def grade(frame, sat=1.08):
    u8 = (np.clip(frame, 0, 1) * 255).astype(np.uint8)
    u8 = cv2.LUT(u8, LUT)
    f = u8.astype(np.float32) / 255
    g = f.mean(2, keepdims=True)
    return np.clip(g + (f - g) * sat, 0, 1)


@lru_cache(maxsize=1)
def vignette_map():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 1.414
    return (1 - 0.32 * np.clip(d, 0, 1) ** 2.2)[..., None].astype(np.float32)


@lru_cache(maxsize=1)
def grain_bank():
    g = np.random.default_rng(1)
    bank = []
    for _ in range(6):
        n = g.standard_normal((H // 2, W // 2)).astype(np.float32)
        n = cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)
        bank.append((n * 0.010)[..., None])
    return bank


def finish(frame, fi):
    frame = frame * vignette_map()
    frame = frame + grain_bank()[fi % 6]
    return np.clip(frame, 0, 1)


def letterbox(frame, amt):
    if amt <= 0: return frame
    bh = int(H * 0.115 * amt)
    if bh > 0:
        frame[:bh] = 0; frame[H - bh:] = 0
    return frame


def light_leak(frame, u, warm=True, strength=1.0):
    """fuite de lumière : blob coloré qui traverse l'image en mode « screen »"""
    yy, xx = np.ogrid[:H // 4, :W // 4]
    cx = lerp(-0.3, 1.3, u) * W / 4; cy = H / 8 * (0.6 + 0.4 * math.sin(u * 3))
    d = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 1.6) ** 2) / (W / 4)
    m = np.clip(1 - d / 0.55, 0, 1) ** 2 * strength * math.sin(math.pi * clamp(u))
    col = ORANGE * 0.6 + PINK * 0.4 if warm else CYAN * 0.5 + PURPLE * 0.5
    leak = cv2.resize((m[..., None] * col).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    return 1 - (1 - frame) * (1 - np.clip(leak * 1.3, 0, 1))


def rgb_split(frame, px):
    if abs(px) < 1: return frame
    out = frame.copy()
    out[..., 2] = np.roll(frame[..., 2], int(px), 1)
    out[..., 0] = np.roll(frame[..., 0], -int(px), 1)
    return out


def glitch_blocks(frame, seed, amt=1.0):
    g = np.random.default_rng(seed)
    out = rgb_split(frame, g.integers(6, 24) * amt)
    for _ in range(int(6 * amt)):
        y = g.integers(0, H - 40); h = g.integers(8, 70); dx = g.integers(-120, 120)
        out[y:y + h] = np.roll(out[y:y + h], int(dx * amt), 1)
    lines = (np.arange(H) % 4 < 1)[:, None, None] * 0.06 * amt
    return np.clip(out - lines, 0, 1)
