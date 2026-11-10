import argparse
import os
import shutil
import sys
import time

import numpy as np

TAU = 2 * np.pi
HALF_W = 0.85
BASE = 0.34  # altura de la base de las llamas (Y crece hacia abajo)
LEVELS = 20

FIRE, WOOD, STONE, GROUND, SMOKE = range(5)
RAMPS = [
    [(70, 10, 4), (176, 28, 6), (238, 88, 10), (255, 172, 32), (255, 236, 120), (255, 255, 236)],
    [(56, 28, 12), (128, 70, 28), (190, 116, 50), (244, 184, 104)],
    [(34, 32, 38), (92, 82, 78), (172, 132, 98), (244, 194, 134)],
    [(26, 10, 6), (92, 40, 14), (172, 92, 30), (232, 152, 60)],
    [(26, 22, 24), (72, 62, 60), (132, 118, 110), (192, 178, 168)],
]
HUD_DIM, HUD_PINK = len(RAMPS) * LEVELS, len(RAMPS) * LEVELS + 1

FLAME = np.array(list(" .':^;*!+xX%#@"))
SOFT = np.array(list(" .:~"))
ROCK = np.array(list(".:oO0@"))

# desplazamiento, escala y fase de cada lengua de fuego
TONGUES = [(0.0, 1.0, 0.0), (-0.21, 0.66, 3.7), (0.22, 0.58, 8.1), (0.07, 0.8, 5.2)]
# extremos de cada tronco y segundo en que aparece
LOGS = [
    (-0.36, 0.40, 0.38, 0.43, 0.2),
    (-0.46, 0.52, 0.16, 0.16, 0.6),
    (0.46, 0.52, -0.16, 0.16, 1.0),
]
STONES = 11
SPARKS, BURST = 46, 16
RNG = np.random.default_rng(11)
P = RNG.random((SPARKS, 6))
Q = RNG.random((BURST, 2))
S = RNG.random(STONES)


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def frac(x):
    return x - np.floor(x)


def vnoise(x, y):
    xi, yi = np.floor(x), np.floor(y)
    u, v = smooth(x - xi), smooth(y - yi)

    def h(i, j):
        return frac(np.sin(i * 127.1 + j * 311.7) * 43758.5453)

    top = h(xi, yi) * (1 - u) + h(xi + 1, yi) * u
    bot = h(xi, yi + 1) * (1 - u) + h(xi + 1, yi + 1) * u
    return top * (1 - v) + bot * v


def fbm(x, y, octaves=3):
    total, amp = 0.0, 0.5
    for _ in range(octaves):
        total = total + amp * vnoise(x, y)
        x, y, amp = x * 2.03 + 17.0, y * 2.03 + 31.0, amp * 0.5
    return total / (1 - 0.5 ** octaves)


def palette():
    codes = []
    t = np.linspace(0, 1, LEVELS)
    for stops in RAMPS:
        stops = np.array(stops, float)
        xs = np.linspace(0, 1, len(stops))
        rgb = np.stack([np.interp(t, xs, stops[:, k]) for k in range(3)], 1).astype(int)
        codes += [f"\x1b[38;2;{r};{g};{b}m" for r, g, b in rgb]
    codes.append("\x1b[38;2;120;112;104m")
    codes.append("\x1b[38;2;232;120;150m")
    return np.array(codes)


PAL = palette()


def grid(cols, rows):
    fit = min(1.0, cols / (rows * 2 * HALF_W))
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    X = (x - cols / 2 + 0.5) / rows / fit
    Y = (y - rows / 2 + 0.5) / (rows / 2) / fit
    rng = np.random.default_rng(5)
    return X, Y, 2 / rows / fit, rng.random((rows, cols)), rng.random((rows, cols))


def pick(ramp, lum):
    return ramp[np.clip((lum * len(ramp)).astype(int), 0, len(ramp) - 1)]


def frame(t, G):
    X, Y, px, rnd, tw = G
    grow = smooth((t - 2.6) / 3.5)
    age = (t - 9) % 7 if t >= 9 else 99.0
    pop = np.exp(-((age / 0.15) ** 2))
    flick = 0.78 + 0.22 * float(vnoise(t * 5.0, 0.0)) + 0.5 * pop
    H = (0.10 + 0.92 * grow) * (0.94 + 0.08 * np.sin(1.7 * t)) + 0.12 * pop
    light = grow * flick
    h = BASE - Y

    # llamas: varias lenguas deformadas por ruido que sube
    n1 = fbm(X * 5.0, Y * 3.4 + 2.8 * t, 4)
    n2 = fbm(X * 2.1 + 40, Y * 1.6 + 1.3 * t)
    heat = np.zeros_like(X)
    for dx, sc, ph in TONGUES:
        Hh = H * sc * (0.85 + 0.3 * float(vnoise(0.9 * t + ph, ph + 5.0)))
        yn = h / Hh
        yc = np.clip(yn, 0, 1.2)
        lean = 0.35 * (float(vnoise(0.45 * t + ph, ph)) - 0.5) * Hh
        xd = X - dx * (1.3 - 0.75 * yc) - lean * yc ** 1.5 + 0.3 * (n2 - 0.5) * (0.25 + yc)
        drop = ((yc + 0.12) / 0.37) ** 0.35 * np.clip(1 - yn, 0, 1.15) ** 0.85
        width = 0.17 * (0.4 + 0.6 * grow) * sc ** 0.5 * drop
        core = 1 - np.abs(xd) / np.maximum(width, 1e-6)
        hh = core * 0.9 + (n1 - 0.5) * (0.9 + 1.4 * yc) - 0.25 * yc + 0.15
        heat = np.maximum(heat, hh * smooth((yn + 0.12) / 0.12) * (yn < 1.15))
    heat = heat * (0.85 + 0.25 * flick) * smooth((t - 2.5) / 0.6)
    # chispazos del encendido
    for ts in (1.9, 2.25, 2.55):
        heat = heat + np.exp(-((np.hypot(X, Y - BASE) / 0.06) ** 2)) * np.exp(-(((t - ts) / 0.07) ** 2))
    heat = np.clip(heat, 0, 1)

    lum = np.zeros_like(X)
    mat = np.zeros(X.shape, int)
    chars = np.full(X.shape, " ")

    # suelo iluminado
    glow = np.exp(-((X / 0.95) ** 2 + ((Y - 0.52) / 0.34) ** 2))
    ground = (Y > 0.36) & (rnd < 0.55)
    gl = 0.06 + 0.8 * glow * light
    lum, mat = np.where(ground, gl, lum), np.where(ground, GROUND, mat)
    chars = np.where(ground, pick(np.array(list(" ..,,::;")), gl * 1.4), chars)

    # humo
    hs = np.clip(h - 0.85 * H, 0, 3)
    plume = np.exp(-(((X - 0.15 * np.sin(0.3 * t) * hs) / (0.08 + 0.28 * hs)) ** 2))
    wisp = fbm(X * 3.1 + 9 + 0.6 * np.sin(2 * Y + 0.4 * t), Y * 2.0 + 0.8 * t)
    sm = plume * smooth(hs / 0.2) * np.exp(-hs / 0.55) * wisp ** 2.2 * grow * grow * 3.6
    smoke = (sm > 0.12) & (rnd > 0.2)
    lum, mat = np.where(smoke, sm, lum), np.where(smoke, SMOKE, mat)
    chars = np.where(smoke, pick(SOFT, sm * 1.3), chars)

    star = (Y < 0.30) & (rnd < 0.004) & ~smoke
    lum = np.where(star, 0.35 + 0.25 * np.sin(0.8 * t + tw * TAU), lum)
    mat = np.where(star, SMOKE, mat)
    chars = np.where(star, np.where(tw < 0.2, "+", "."), chars)

    def stones(front):
        nonlocal lum, mat, chars
        for j in range(STONES):
            a = TAU * j / STONES + 0.2
            if (np.sin(a) > 0) != front or t < 0.9 + 0.1 * j:
                continue
            sx, sy = 0.60 * np.cos(a), 0.52 + 0.13 * np.sin(a)
            r = (0.055 + 0.025 * S[j]) * (1.2 if front else 0.9)
            lx, ly = (X - sx) / (1.35 * r), (Y - sy) / (0.8 * r)
            inside = lx * lx + ly * ly < 1
            fx, fy = -sx, BASE - 0.15 - sy
            shade = 0.5 + 0.5 * (lx * fx + ly * fy) / np.hypot(fx, fy)
            sl = 0.2 + 0.75 * shade * (0.3 + 0.7 * light)
            lum, mat = np.where(inside, sl, lum), np.where(inside, STONE, mat)
            chars = np.where(inside, pick(ROCK, sl), chars)

    stones(False)

    fire = heat > 0.13
    lum, mat = np.where(fire, heat, lum), np.where(fire, FIRE, mat)
    chars = np.where(fire, pick(FLAME, heat ** 0.85), chars)

    # troncos: tapan la llama salvo donde arde más fuerte
    for ax, ay, bx, by, t0 in LOGS:
        vx, vy = bx - ax, by - ay
        L = np.hypot(vx, vy)
        u = ((X - ax) * vx + (Y - ay) * vy) / (L * L)
        side = ((X - ax) * vy - (Y - ay) * vx) / L
        inside = (u > 0) & (u < np.clip((t - t0) / 0.8, 0, 1)) & (np.abs(side) < 0.052) & (heat < 0.82)
        bark = 0.5 + 0.5 * np.sin(u * L * 46 + 5 * np.sin(side * 60))
        near = np.exp(-(np.hypot(X, Y - BASE) / 0.45))
        slope = "=" if abs(vy) < 0.1 else ("/" if vx * vy < 0 else "\\")
        wl = (0.30 + 0.25 * bark) * (0.6 + 1.1 * light * near)
        end = (u < 0.035) | (u > 0.965)
        wl = np.where(end, wl + 0.2, wl)
        ember = inside & (np.abs(X) < 0.26 * grow) & (fbm(X * 11, Y * 11 - 0.4 * t) > 0.5)
        el = 0.25 + 0.3 * fbm(X * 9 + 3, Y * 9 + 0.6 * t) * flick
        lum = np.where(inside, np.where(ember, el, wl), lum)
        mat = np.where(inside, np.where(ember, FIRE, WOOD), mat)
        chars = np.where(inside, np.where(end, "@", np.where(ember, "%", np.where(bark > 0.45, slope, "~"))), chars)

    stones(True)

    # chispas
    rows, cols = X.shape
    count = 0

    def dots(x, y, b):
        nonlocal count
        c = np.rint((x - X[0, 0]) / (px / 2)).astype(int)
        r = np.rint((y - Y[0, 0]) / px).astype(int)
        ok = (b > 0.05) & (c >= 0) & (c < cols) & (r >= 0) & (r < rows)
        c, r, b = c[ok], r[ok], b[ok]
        ok = heat[r, c] < 0.3
        c, r, b = c[ok], r[ok], b[ok]
        chars[r, c] = np.where(b > 0.6, "*", np.where(b > 0.3, "'", "."))
        lum[r, c] = 0.3 + 0.6 * b
        mat[r, c] = FIRE
        count += len(b)

    period = 2.2 + 2.5 * P[:, 0]
    p = frac(t / period + P[:, 1])
    born = t - p * period
    dots((P[:, 2] - 0.5) * 0.3 + (P[:, 3] - 0.5) * 0.9 * p + 0.05 * np.sin(7 * p + 6 * P[:, 4]),
         BASE - 0.3 - p * (0.8 + 0.9 * P[:, 5]),
         (1 - p) ** 1.5 * (born > 4.0))
    if age < 1.8:
        th = -np.pi / 2 + (Q[:, 0] - 0.5) * 1.7
        v = 0.6 + 0.8 * Q[:, 1]
        dots(v * np.cos(th) * age * 0.8, BASE - 0.25 + v * np.sin(th) * age + 0.55 * age * age,
             np.full(BURST, 1 - age / 1.8))

    col = mat * LEVELS + (np.clip(lum, 0, 1) * (LEVELS - 1)).astype(int)
    stats = {"heat": float(heat.mean() * 12), "sparks": count, "letters": int((chars != " ").sum())}
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
    put(chars, col, rows - 4, 2, f" heat {stats['heat']:.2f}   sparks {stats['sparks']:02d} ", HUD_DIM)
    put(chars, col, rows - 3, 2, f" letters {stats['letters']:,} ", HUD_DIM)
    put(chars, col, rows - 1, 1, " $ py campfire.py ", HUD_DIM)
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
