import argparse
import os
import shutil
import sys
import time

import numpy as np

TAU = 2 * np.pi
HALF_W = 1.30
ZOOM = 1.45
LEVELS = 20
FLOOR_Y = 0.50
HEAD = (-0.40, 0.375)
WINDOW = (0.62, 1.16, -0.90, -0.30)

FLOOR, CUSH, FUR, DARK, CREAM, PINK, NIGHT, ZZ = range(8)
RAMPS = [
    [(20, 13, 10), (60, 38, 24), (110, 72, 44), (170, 120, 78)],
    [(26, 30, 60), (58, 68, 128), (104, 116, 184), (176, 186, 236)],
    [(84, 40, 12), (184, 98, 28), (238, 156, 62), (255, 220, 156)],
    [(40, 18, 6), (92, 42, 12), (136, 68, 20), (170, 96, 36)],
    [(90, 80, 70), (170, 156, 140), (230, 220, 204), (255, 252, 244)],
    [(110, 50, 60), (190, 100, 112), (240, 150, 160), (255, 200, 206)],
    [(10, 14, 40), (34, 48, 110), (110, 130, 210), (220, 228, 255)],
    [(36, 36, 64), (90, 90, 150), (150, 150, 220), (210, 210, 255)],
]
N = len(RAMPS) * LEVELS
HUD_DIM, HUD_PINK, FACE, EYE = N, N + 1, N + 2, N + 3

SOLID = np.array(list(" .:;~+=*x%#@"))


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def frac(x):
    return x - np.floor(x)


def bump(age, at, width):
    return float(np.exp(-(((age - at) / width) ** 2)))


def palette():
    codes = []
    t = np.linspace(0, 1, LEVELS)
    for stops in RAMPS:
        stops = np.array(stops, float)
        xs = np.linspace(0, 1, len(stops))
        rgb = np.stack([np.interp(t, xs, stops[:, k]) for k in range(3)], 1).astype(int)
        codes += [f"\x1b[38;2;{r};{g};{b}m" for r, g, b in rgb]
    for r, g, b in ((128, 118, 110), (232, 120, 150), (96, 46, 18), (150, 226, 130)):
        codes.append(f"\x1b[38;2;{r};{g};{b}m")
    return np.array(codes)


PAL = palette()


def grid(cols, rows):
    fit = min(1.0, cols / (rows * 2 * HALF_W))
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    X = (x - cols / 2 + 0.5) / rows / fit
    Y = (y - rows / 2 + 0.5) / (rows / 2) / fit
    rng = np.random.default_rng(9)
    return X, Y, 2 / rows / fit, rng.random((rows, cols)), rng.random((rows, cols))


def pick(ramp, lum):
    return ramp[np.clip((lum * len(ramp)).astype(int), 0, len(ramp) - 1)]


def triangle(X, Y, a, b, c):
    def side(p, q):
        return (X - p[0]) * (q[1] - p[1]) - (Y - p[1]) * (q[0] - p[0])

    s1, s2, s3 = side(a, b), side(b, c), side(c, a)
    return ((s1 >= 0) & (s2 >= 0) & (s3 >= 0)) | ((s1 <= 0) & (s2 <= 0) & (s3 <= 0))


def frame(t, G):
    X, Y, px, rnd, tw = G
    lum = np.zeros_like(X)
    mat = np.zeros(X.shape, int)
    chars = np.full(X.shape, " ")

    def paint(mask, l, m, c):
        nonlocal lum, mat, chars
        lum, mat, chars = np.where(mask, l, lum), np.where(mask, m, mat), np.where(mask, c, chars)

    amb = smooth(t / 1.2)
    breath = 0.5 - 0.5 * np.cos(1.3 * t)
    asleep = t > 5.5

    # ventana con la noche fuera
    x0, x1, y0, y1 = WINDOW
    outer = (X > x0) & (X < x1) & (Y > y0) & (Y < y1)
    glass = (X > x0 + px) & (X < x1 - px) & (Y > y0 + px) & (Y < y1 - px)
    mid_x = np.abs(X - (x0 + x1) / 2) < 0.26 * px
    mid_y = np.abs(Y - (y0 + y1) / 2) < 0.5 * px
    star = glass & (rnd < 0.05)
    paint(glass & (rnd > 0.75), 0.16 * amb, NIGHT, ".")
    paint(star, (0.45 + 0.35 * np.sin(0.9 * t + tw * TAU)) * amb, NIGHT, np.where(tw < 0.25, "+", "."))
    mx, my = x0 + 0.37, y0 + 0.19
    moon = glass & (np.hypot(X - mx, Y - my) < 0.085) & (np.hypot(X - mx + 0.05, Y - my + 0.01) > 0.075)
    paint(moon, 0.95 * amb, CREAM, "@")
    frame_ = outer & (~glass | mid_x | mid_y)
    paint(frame_, 0.55 * amb, FLOOR, np.where(mid_y | (Y < y0 + px) | (Y > y1 - px), "=", "|"))

    # el gato se dibuja ampliado
    X, Y, px = X / ZOOM, (Y - 0.62) / ZOOM + 0.60, px / ZOOM

    # suelo de tablas
    pool = np.exp(-((X / 1.1) ** 2 + ((Y - 0.62) / 0.45) ** 2))
    board = frac((Y - FLOOR_Y) / max(0.13, 3 * px))
    seam = board < px / max(0.13, 3 * px)
    fl = (0.12 + 0.3 * pool) * amb
    paint((Y > FLOOR_Y) & (seam | (rnd < 0.06)), fl, FLOOR, np.where(seam, "_", "."))

    # cojín
    shown = np.abs(X - 0.02) < 0.86 * smooth((t - 0.3) / 1.3)
    c1 = ((X - 0.02) / 0.82) ** 2 + ((Y - 0.57) / 0.15) ** 2
    c2 = ((X - 0.02) / 0.82) ** 2 + ((Y - 0.625) / 0.15) ** 2
    quilt = (np.sin(X * 24) * np.sin(Y * 52) > 0.55) * 0.14
    cl = 0.36 + 0.34 * (1 - c1) + quilt - 0.12 * X
    paint((c2 < 1) & shown, 0.3 - 0.1 * X, CUSH, "=")
    paint((c1 < 1) & shown, cl, CUSH, pick(SOLID, cl))

    # cuerpo: se dibuja girando y luego respira
    ry, rx = 0.265 * (1 + 0.045 * breath), 0.52 * (1 + 0.008 * breath)
    cx, cy = 0.08, 0.545 - ry
    ex, ey = (X - cx) / rx, (Y - cy) / ry
    r2 = ex * ex + ey * ey
    sweep = frac((np.arctan2(ey, ex) + np.pi / 2) / TAU)
    body = (r2 < 1) & (sweep < 1.05 * smooth((t - 1.2) / 2.2))
    shade = np.clip(-0.35 * ex - 0.55 * ey + 0.75 * np.sqrt(np.clip(1 - r2, 0, 1)), 0, 1)
    bl = 0.42 + 0.58 * shade
    haunch = np.sqrt(((X - 0.36) / 0.23) ** 2 + ((Y - 0.42) / 0.17) ** 2)
    bl = bl * (1 - 0.35 * np.exp(-(((haunch - 1) / 0.09) ** 2)) * (Y < 0.44))
    stripes_on = smooth((t - 3.6) / 1.2)
    stripe = (np.sin(15 * ex + 3.0 * ey * ey + 0.6 * np.sin(5 * ey)) > 1.2 - stripes_on) & (ey < 0.35)
    paint(body, np.where(stripe, bl * 0.75, bl), np.where(stripe, DARK, FUR), pick(SOLID, bl))

    # cabeza y orejas
    hd = smooth((t - 3.0) / 0.8)
    hx, hy = HEAD[0], HEAD[1] - 0.008 * breath
    twitch = bump((t - 10) % 9, 0.3, 0.12) if t > 10 else 0.0
    if hd > 0:
        for sgn, tw_ in ((-1, 0.0), (1, twitch)):
            a = (hx + sgn * 0.04 * hd, hy - 0.155 * hd)
            b = (hx + sgn * 0.175 * hd, hy - 0.085 * hd)
            c = (hx + sgn * (0.155 + 0.04 * tw_) * hd, hy - (0.30 - 0.035 * tw_) * hd)
            g = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3 + 0.01)
            grow = [(g[0] + 1.3 * (p[0] - g[0]), g[1] + 1.3 * (p[1] - g[1])) for p in (a, b, c)]
            paint(triangle(X, Y, *grow), 0.0, DARK, " ")
            paint(triangle(X, Y, a, b, c), 0.7, FUR, "%")
            paint(triangle(X, Y, *[((p[0] + g[0]) / 2, (p[1] + g[1]) / 2) for p in (a, b, c)]), 0.6, PINK, "*")
        qx, qy = (X - hx) / (0.20 * hd), (Y - hy) / (0.17 * hd)
        q2 = qx * qx + qy * qy
        hl = 0.45 + 0.55 * np.clip(-0.3 * qx - 0.45 * qy + 0.8 * np.sqrt(np.clip(1 - q2, 0, 1)), 0, 1)
        brow = (np.abs(frac((X - hx) / 0.065 + 0.5) - 0.5) < 0.2) & (qy < -0.5) & (np.abs(X - hx) < 0.10)
        muzzle = ((X - hx) / 0.095) ** 2 + ((Y - hy - 0.075) / 0.062) ** 2 < 1
        hm = np.where(muzzle, CREAM, np.where(brow & (stripes_on > 0.5), DARK, FUR))
        paint(q2 < 1.2, 0.0, DARK, " ")
        paint(q2 < 1, np.where(muzzle, hl * 0.95, hl), hm, pick(SOLID, hl))
        paw = ((X + 0.17) / 0.085) ** 2 + ((Y - 0.525) / 0.036) ** 2
        paint((paw < 1.5) & (hd > 0.9), 0.0, DARK, " ")
        paint((paw < 1) & (hd > 0.9), 0.8 - 0.3 * paw, CREAM, pick(SOLID, 0.9 - 0.3 * paw))

    # cola: rodea el cuerpo por delante
    tl = smooth((t - 3.4) / 1.4)
    flick = bump((t - 14) % 13, 0.5, 0.25) if t > 14 else 0.0
    if tl > 0:
        best = np.full(X.shape, 9.0)
        along = np.zeros_like(X)
        for u in np.linspace(0, tl, int(56 * tl) + 2):
            th = -0.35 + 2.8 * u
            k = np.clip((u - 0.72) / 0.28, 0, 1) ** 2
            tx_, ty_ = 0.10 + 0.60 * np.cos(th) - 0.03 * flick * k, 0.40 + 0.20 * np.sin(th) - 0.09 * flick * k
            d = np.hypot(X - tx_, Y - ty_) / (0.066 * (1 - 0.4 * u))
            along = np.where(d < best, u, along)
            best = np.minimum(best, d)
        tail = best < 1
        tlum = 0.5 + 0.5 * (1 - best)
        tm = np.where(along > 0.9, CREAM, np.where(np.sin(along * 42) > 0.35, DARK, FUR))
        paint(best < 1.3, 0.0, DARK, " ")
        paint(tail, tlum, tm, pick(SOLID, tlum))

    col = mat * LEVELS + (np.clip(lum, 0, 1) * (LEVELS - 1)).astype(int)

    def stamp(x, y, text, color):
        r = int(np.rint((y - Y[0, 0]) / px))
        c = int(np.rint((x - X[0, 0]) / (px / 2))) - len(text) // 2
        put(chars, col, r, max(c, 0), text, color)

    # cara: ojos abiertos al llegar, luego se le cierran
    if hd > 0.9:
        peek = asleep and t > 20 and (t - 20) % 23 < 1.2
        big = px < 0.07
        if t < 5.0:
            eyes = ("(o)", "(o)") if big else ("o", "o")
        elif not asleep:
            eyes = ("(-)", "(-)") if big else ("-", "-")
        else:
            eyes = ("\\_/", "\\_/") if big else ("-", "-")
            if peek:
                eyes = ("(o)" if big else "o", eyes[1])
        off = 0.09 if big else max(0.07, px)
        for sgn, e in zip((-1, 1), eyes):
            stamp(hx + sgn * off, hy - 0.015, e, EYE if "o" in e else FACE)
        stamp(hx, hy + 0.055, "v", PINK * LEVELS + LEVELS - 4)
        if big:
            stamp(hx, hy + 0.055 + px, "'-'", FACE)
        wk = "---" if big else "-"
        stamp(hx - 0.20 - 0.02 * len(wk), hy + 0.06, wk, CREAM * LEVELS + LEVELS - 6)
        stamp(hx + 0.20 + 0.02 * len(wk), hy + 0.06, wk, CREAM * LEVELS + LEVELS - 6)

    # zzz
    dreams = 0
    if t > 6.5:
        dreams = int((t - 6.5) / 4.2) + 1
        for k in range(3):
            p = frac((t - 6.5) / 4.2 + k / 3)
            if (t - 6.5) / 4.2 + k / 3 < 1 and k > 0 and p > (t - 6.5) / 4.2:
                continue
            zx = hx + 0.12 + 0.30 * p + 0.03 * np.sin(6 * p + k)
            zy = hy - 0.30 - 0.55 * p
            level = int(np.clip(np.sin(np.pi * p) * 1.3, 0, 1) * (LEVELS - 1))
            stamp(zx, zy, "z" if p < 0.4 else "Z", ZZ * LEVELS + level)

    stats = {
        "purr": 25 + 1.5 * np.sin(0.4 * t) if asleep else 0.0,
        "breath": 60 * 1.3 / TAU,
        "dreams": dreams,
        "letters": int((chars != " ").sum()),
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
    put(chars, col, rows - 4, 2, f" purr {stats['purr']:.0f} Hz   breath {stats['breath']:.0f}/min   dreams {stats['dreams']} ", HUD_DIM)
    put(chars, col, rows - 3, 2, f" letters {stats['letters']:,} ", HUD_DIM)
    put(chars, col, rows - 1, 1, " $ py cat.py ", HUD_DIM)
    put(chars, col, rows - 1, -2, f" running · {fps:.0f} fps ", HUD_DIM)


def render(chars, col):
    prev = np.full_like(col, -1)
    prev[:, 1:] = col[:, :-1]
    cells = np.char.add(np.where(col != prev, PAL[col], ""), chars)
    return "\n".join("".join(row) for row in cells.tolist())


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
