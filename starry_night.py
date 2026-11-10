import argparse
import os
import shutil
import sys
import time

import numpy as np

TAU = 2 * np.pi
HALF_W = 1.26  # medio ancho del cuadro (el alto va de -1 a 1)
LEVELS = 16

SKY, PALE, GOLD, MOON, HILL, TOWN, TREE = range(7)
RAMPS = [
    [(20, 40, 120), (44, 104, 214), (130, 188, 245), (240, 248, 255)],
    [(40, 90, 130), (120, 184, 180), (206, 232, 196), (255, 255, 228)],
    [(110, 70, 8), (222, 160, 24), (250, 214, 70), (255, 250, 190)],
    [(150, 70, 8), (236, 140, 22), (255, 196, 64), (255, 240, 170)],
    [(10, 34, 64), (20, 66, 112), (44, 104, 150), (150, 200, 220)],
    [(12, 18, 42), (34, 48, 92), (70, 92, 140), (140, 160, 190)],
    [(20, 30, 14), (50, 72, 30), (104, 112, 44), (176, 150, 64)],
]
HUD_DIM, HUD_PINK = len(RAMPS) * LEVELS, len(RAMPS) * LEVELS + 1

# x, y, radio del halo
STARS = [
    (-0.52, -0.24, 0.17), (-1.06, -0.80, 0.13), (0.02, -0.62, 0.12),
    (-0.62, -0.84, 0.11), (0.36, -0.84, 0.11), (-1.10, -0.36, 0.10),
    (-0.24, -0.86, 0.10), (0.60, -0.50, 0.10), (-0.30, -0.50, 0.09),
    (0.70, -0.86, 0.09), (-0.96, -0.58, 0.08),
    (-1.62, -0.66, 0.11), (1.58, -0.30, 0.10), (-1.95, -0.15, 0.09),
]
ORDER = [3, 0, 6, 9, 1, 4, 7, 10, 2, 5, 8, 11, 12, 13]
# x, y, radio, brazos, sentido, segundo de entrada
SWIRLS = [(0.00, -0.12, 0.36, 2, 1, 4.0), (0.50, 0.02, 0.21, 1, -1, 4.8)]
MOON_POS = (0.98, -0.70)

# [dirección del trazo][intensidad]
GLYPH = np.array([
    [".", "-", "~", "="],
    [".", "`", "\\", "\\"],
    [".", ":", "|", "|"],
    [".", ",", "/", "/"],
])


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def frac(x):
    return x - np.floor(x)


def noise(i, seed):
    return frac(np.sin(i * seed) * 43758.5453)


def palette():
    codes = []
    t = np.linspace(0, 1, LEVELS)
    for stops in RAMPS:
        stops = np.array(stops, float)
        xs = np.linspace(0, 1, len(stops))
        rgb = np.stack([np.interp(t, xs, stops[:, k]) for k in range(3)], 1).astype(int)
        codes += [f"\x1b[38;2;{r};{g};{b}m" for r, g, b in rgb]
    codes.append("\x1b[38;2;128;128;140m")
    codes.append("\x1b[38;2;232;120;150m")
    return np.array(codes)


PAL = palette()
BG = "\x1b[48;2;5;8;24m"


def grid(cols, rows):
    fit = min(1.0, cols / (rows * 2 * HALF_W))
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    X = (x - cols / 2 + 0.5) / rows / fit
    Y = (y - rows / 2 + 0.5) / (rows / 2) / fit
    return X, Y, 2 / rows / fit


def blend(lum, tx, ty, w, l2, sx, sy):
    sel = w > 0.4
    return lum * (1 - w) + l2 * w, np.where(sel, sx, tx), np.where(sel, sy, ty)


def frame(t, G):
    X, Y, px = G
    xmin, xmax, ymax = X[0, 0], X[0, -1], Y[-1, 0]
    kp = TAU / max(3.0 * px, 0.085)
    kd = TAU / max(5.0 * px, 0.16)

    # cielo: trazos ondulados que corren hacia la derecha
    a1, a2, a3 = 1.7 * X + 0.25 * t, 4.3 * X - 0.2 * t + 1.3, 9.1 * X + 3 * Y + 0.3 * t
    f = Y + 0.15 * np.sin(a1) + 0.07 * np.sin(a2) + 0.025 * np.sin(a3)
    tx = 1 + 0.075 * np.cos(a3)
    ty = -(0.255 * np.cos(a1) + 0.301 * np.cos(a2) + 0.2275 * np.cos(a3))
    jit = noise(np.floor(kp * f / TAU), 12.9898) * TAU
    lum = (0.5 + 0.5 * np.sin(kp * f)) ** 0.8 * (0.62 + 0.38 * np.sin(kd * X - 1.6 * t + jit))
    lum = 0.3 + 0.6 * lum

    hill = 0.36 - 0.20 * smooth((X + 0.3) / 1.5) - 0.045 * np.sin(3.1 * X + 1.0) - 0.02 * np.sin(7.3 * X)
    glow = np.exp(-(((hill - Y) / 0.17) ** 2))
    river = np.exp(-(((Y + 0.24 - 0.10 * np.sin(1.7 * X + 0.4)) / 0.13) ** 2)) * smooth((0.3 - X) / 0.7)
    lum = lum * (1 + 0.4 * glow + 0.35 * river)
    mat = np.where((glow > 0.55) & (lum > 0.62), PALE, SKY)
    lum = lum * smooth(((t - 2.0) * (xmax - xmin + 0.6) / 3.0 - (X - xmin)) / 0.6)

    # remolinos
    ks = TAU / max(3.4 * px, 0.09)
    for cx, cy, R, arms, sgn, t0 in SWIRLS:
        on = smooth((t - t0) / 2.5)
        dx, dy = X - cx, Y - cy
        r = np.hypot(dx, dy) + 1e-6
        w = np.exp(-((r / R) ** 2)) * on
        sp = 0.5 + 0.5 * np.sin(ks * r - sgn * arms * np.arctan2(dy, dx) - 1.8 * t + 5 * (1 - on))
        gt = -sgn * arms / r
        lum, tx, ty = blend(lum, tx, ty, w, 0.38 + 0.62 * sp ** 0.7,
                            (-gt * dx - ks * dy) / r, (-gt * dy + ks * dx) / r)
        mat = np.where((w > 0.5) & (sp > 0.7), PALE, mat)

    # estrellas: núcleo y anillos concéntricos
    kr = TAU / max(2.6 * px, 0.055)
    core = np.zeros(X.shape, bool)
    lit = 0
    for i, (sx, sy, R) in enumerate(STARS):
        on = smooth((t - 0.3 - 0.17 * ORDER[i]) / 0.9)
        if on <= 0 or not xmin - R < sx < xmax + R:
            continue
        lit += on > 0.5
        dx, dy = X - sx, Y - sy
        d = np.hypot(dx, dy)
        w = np.exp(-((d / (R * (0.35 + 0.65 * on))) ** 2)) * on
        ring = 0.5 + 0.5 * np.sin(kr * d - 2.2 * t + i)
        l2 = (0.4 + 0.6 * ring) * (0.85 + 0.15 * np.sin(1.3 * t + 2.1 * i))
        lum, tx, ty = blend(lum, tx, ty, w, l2, -dy, dx)
        mat = np.where(w > 0.5, GOLD, np.where((w > 0.22) & (mat == SKY), PALE, mat))
        core |= (d < max(0.3 * R, 0.8 * px)) & (on > 0.3)

    # luna
    on = smooth((t - 5.6) / 1.2)
    dx, dy = X - MOON_POS[0], Y - MOON_POS[1]
    d = np.hypot(dx, dy)
    w = np.exp(-((d / 0.25) ** 2)) * on
    ring = 0.5 + 0.5 * np.sin(kr * d - 2.0 * t)
    lum, tx, ty = blend(lum, tx, ty, w, 0.45 + 0.55 * ring, -dy, dx)
    mat = np.where(w > 0.45, GOLD, np.where((w > 0.2) & (mat == SKY), PALE, mat))
    disk = (d < 0.115) & (on > 0.3)
    crescent = disk & (np.hypot(dx + 0.065, dy) > 0.10)

    lum = np.clip(lum * (1 + 0.6 * np.exp(-(((t - 6.4) / 0.3) ** 2))), 0, 1)
    lum = np.where(core | crescent, 1.0, np.where(disk, 0.7, lum))
    mat = np.where(core, GOLD, np.where(crescent, MOON, np.where(disk, GOLD, mat)))

    # el suelo sube desde abajo
    rg = smooth((t - 6.2) / 2.2)
    shown = Y > ymax + 0.1 - rg * (ymax + 0.1)
    town = 0.60 + 0.03 * np.sin(4 * X + 2)

    hills = (Y > hill) & shown
    hl = 0.5 + 0.5 * np.sin(0.9 * kp * (Y - hill) + 1.4 * np.sin(2.6 * X))
    lum = np.where(hills, 0.28 + 0.55 * hl * (0.7 + 0.3 * np.sin(kd * X + 9 * Y)), lum)
    mat = np.where(hills, HILL, mat)
    tx = np.where(hills, 1.0, tx)
    ty = np.where(hills, np.gradient(hill, axis=1) / (px / 2) * np.clip(1 - (Y - hill) * 3, 0, 1), ty)

    ridge = hills & (Y - hill < 1.05 * px)
    lum = np.where(ridge, 0.95, lum)

    ground = (Y > town) & shown
    lum = np.where(ground, 0.22 + 0.3 * (0.5 + 0.5 * np.sin(kp * Y + 3 * np.sin(5 * X))), lum)
    mat = np.where(ground, TOWN, mat)
    tx, ty = np.where(ground, 1.0, tx), np.where(ground, 0.0, ty)

    # iglesia
    sp = np.clip((Y - 0.10) / 0.42, 0, 1)
    spire = (sp > 0) & (sp < 1) & (np.abs(X - 0.10) < np.maximum(0.3 * px, 0.006 + 0.04 * sp ** 1.3))
    church = (spire | ((np.abs(X - 0.17) < 0.10) & (Y > 0.50) & (Y < town + 0.08))) & shown

    # casas
    hw = max(0.15, 4 * px)
    hi = np.floor((X + 7) / hw)
    u = (X + 7) / hw - hi
    eave = town - 0.05 - 0.11 * noise(hi, 127.1)
    top = eave + 0.14 * np.abs(u - 0.5)
    house = (noise(hi, 311.7) > 0.22) & (u > 0.1) & (u < 0.9) & (Y > top) & (Y < town + 0.10) & shown
    roof = house & (Y < top + 1.1 * px)
    window = house & (np.abs(u - 0.5) < 0.2) & (np.abs(Y - (eave + 0.07 + 1.3 * px)) < 0.5 * px)
    k3 = noise(hi, 74.7)
    window_on = window & (k3 > 0.15) & (t > 8.2 + 3.0 * k3)

    built = church | house
    lum = np.where(built, np.where(roof | spire, 0.9, 0.55), lum)
    lum = np.where(window_on, 0.85 + 0.1 * np.sin(2 * t + 40 * k3), lum)
    mat = np.where(built, TOWN, mat)
    mat = np.where(window_on, GOLD, mat)

    # cipreses: crecen como una llama
    gc = smooth((t - 7.2) / 3.0)
    bottom = max(ymax, 1.0) + 0.05
    tree = np.zeros(X.shape, bool)
    tree_x = np.zeros_like(X)
    for xc, top_y, wmax, ph in ((-0.96, 0.05, 0.13, 2.0), (-0.74, -0.84, 0.27, 0.0)):
        ytop = bottom - gc * (bottom - top_y)
        s = np.clip((Y - ytop) / max(bottom - ytop, 1e-6), 0, 1)
        cx = xc + 0.03 * np.sin(6 * Y - 1.1 * t + ph) * (0.35 + 0.65 * (1 - s))
        wd = np.maximum(wmax * s ** 0.85 * (1 + 0.1 * np.sin(15 * Y + 1.6 * t + ph)), 0.6 * px * (s > 0))
        inside = (s > 0) & (np.abs(X - cx) < wd) & (gc > 0)
        tree_x = np.where(inside, X - cx, tree_x)
        tree |= inside
    kt = TAU / max(2.2 * px, 0.06)
    wob = 4 * Y - 1.1 * t
    v = np.sin(kt * tree_x + 8 * Y + 2.5 * np.sin(wob))
    lum = np.where(tree, 0.3 + 0.7 * (0.5 + 0.5 * v) ** 1.2, lum)
    mat = np.where(tree, TREE, mat)
    tx = np.where(tree, -(8 + 10 * np.cos(wob)) / kt * 2.5, tx)
    ty = np.where(tree, 1.0, ty)

    sector = np.rint((np.arctan2(ty, tx) % np.pi) / (np.pi / 4)).astype(int) % 4
    level = np.digitize(lum, [0.2, 0.45, 0.7])
    chars = GLYPH[sector, level]
    free = ~tree
    solid = hills & ~ground & free & (sector == 0)
    chars = np.where(solid, np.array([":", "=", "%", "#"])[level], chars)
    chars = np.where(built & free, np.where(roof, "^", np.where(spire, "|", "%")), chars)
    chars = np.where(window & free, np.where(window_on, "#", "."), chars)
    chars = np.where((core | crescent) & free, "@", np.where(disk & ~crescent & free, "o", chars))
    chars = np.where(lum < 0.05, " ", chars)
    col = mat * LEVELS + (np.clip(lum, 0, 1) * (LEVELS - 1)).astype(int)

    stats = {
        "stars": int(lit),
        "wind": 1.6 + 0.4 * np.sin(0.25 * t),
        "strokes": int((chars != " ").sum()),
    }
    return chars, col, stats


def put(chars, col, row, c0, text, color):
    rows, cols = chars.shape
    if c0 < 0:
        c0 = cols + c0 - len(text)
    n = min(len(text), cols - c0)
    if n <= 0 or c0 < 0 or not 0 <= row < rows:
        return
    chars[row, c0:c0 + n] = list(text[:n])
    col[row, c0:c0 + n] = color


def hud(chars, col, t, fps, stats):
    rows = chars.shape[0]
    put(chars, col, 1, -2, f"t {t:05.2f}s", HUD_PINK)
    put(chars, col, rows - 4, 2, f" stars {stats['stars']:02d}   wind {stats['wind']:.2f} ", HUD_DIM)
    put(chars, col, rows - 3, 2, f" strokes {stats['strokes']:,} ", HUD_DIM)
    put(chars, col, rows - 1, 1, " $ py starry_night.py ", HUD_DIM)
    put(chars, col, rows - 1, -2, f" running · {fps:.0f} fps ", HUD_DIM)


def render(chars, col):
    prev = np.full_like(col, -1)
    prev[:, 1:] = col[:, :-1]
    cells = np.char.add(np.where(col != prev, PAL[col], ""), chars)
    return BG + "\x1b[K\n".join("".join(row) for row in cells.tolist()) + "\x1b[K"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    if os.name == "nt":
        os.system("")  # activa las secuencias ANSI en la consola de Windows

    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l\x1b[2J")
    size, G, fps = None, None, float(args.fps)
    t0 = time.perf_counter()
    try:
        while True:
            start = time.perf_counter()
            ts = shutil.get_terminal_size((120, 40))
            if ts != size:
                size = ts
                G = grid(max(ts.columns - 1, 20), max(ts.lines, 10))
                out.write("\x1b[2J")
            t = start - t0
            chars, col, stats = frame(t, G)
            hud(chars, col, t, fps, stats)
            out.write("\x1b[H" + render(chars, col) + "\x1b[0m")
            out.flush()
            time.sleep(max(0.0, 1 / args.fps - (time.perf_counter() - start)))
            fps = 0.9 * fps + 0.1 / max(time.perf_counter() - start, 1e-6)
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()


if __name__ == "__main__":
    main()
