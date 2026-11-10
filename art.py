import argparse
import os
import shutil
import sys
import time

import numpy as np

TAU = 2 * np.pi
R0 = 0.30                          # radio de la sombra
R_IN, R_OUT = 1.25 * R0, 3.9 * R0  # límites del disco
TILT = np.radians(17)
INC = 0.30                         # achatamiento del disco (inclinación)
FLASH = 5.0                        # segundo en que se enciende el disco
RAMP = " .,:;~=+ox*%#@"
LEVELS = 32
HUD_DIM, HUD_PINK = LEVELS, LEVELS + 1


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def palette():
    codes = []
    for i in range(LEVELS):
        l = i / (LEVELS - 1)
        r = min(1.0, 0.18 + 1.25 * l)
        g = min(1.0, 0.06 + 0.95 * l ** 1.4)
        b = min(1.0, 0.03 + 0.80 * l ** 2.6)
        codes.append(f"\x1b[38;2;{int(r * 255)};{int(g * 255)};{int(b * 255)}m")
    codes.append("\x1b[38;2;120;112;104m")
    codes.append("\x1b[38;2;232;120;150m")
    return np.array(codes)


PAL = palette()
RAMP_ARR = np.array(list(RAMP))


def grid(cols, rows):
    fit = min(1.0, cols / (rows * 2.3))
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    X = (x - cols / 2) / rows / fit
    Y = (y - rows / 2) / (rows / 2) / fit
    px = 2 / rows / fit
    rng = np.random.default_rng(7)
    return X, Y, px, rng.random((rows, cols)), rng.random((rows, cols))


def frame(t, G):
    X, Y, px, rnd, tw = G
    cam = smooth((t - FLASH + 0.3) / 2.6)
    zoom = 1 + 0.12 * (1 - cam)
    X, Y = X * zoom, Y * zoom

    r = np.hypot(X, Y)
    ang = np.arctan2(Y, X)
    u = X * np.cos(TILT) + Y * np.sin(TILT)
    v = -X * np.sin(TILT) + Y * np.cos(TILT)
    rho = np.maximum(np.hypot(u, v / INC), 1e-6)
    phi = np.arctan2(v / INC, u)

    disk_on = smooth((t - FLASH) / 2.8)
    flash = np.exp(-(((t - FLASH) / 0.22) ** 2))

    # anillo que se dibuja solo
    ring_k = smooth((t - 0.3) / 2.2)
    around = ((ang + np.pi / 2) % TAU) / TAU
    width = max(0.06 * R0, 0.6 * px)
    ring = np.exp(-(((r - 1.02 * R0) / width) ** 2)) * smooth((ring_k * 1.1 - around) / 0.1)

    # resplandor que respira
    aura_k = smooth((t - 2.2) / 1.8) * (1 - 0.6 * disk_on)
    puff = 0.6 + 0.4 * np.sin(1.6 * t)
    reach = 0.3 * R0 * (0.7 + 0.5 * puff)
    aura = 0.6 * aura_k * np.exp(-((np.maximum(r - R0, 0) / reach) ** 1.5))

    # disco de acreción
    spin = 0.9 * t
    k = min(8.0, INC * TAU * R0 / (2.2 * px))
    band = 0.72 + 0.28 * np.sin(rho / R0 * k + 0.6 * t)
    swirl = 0.85 + 0.15 * np.sin(3 * phi - 4 * spin * (R_IN / rho) ** 1.5 + rho * 6)
    edge = smooth((rho - R_IN) / (0.25 * R0)) * smooth((R_OUT - rho) / (1.4 * R0))
    doppler = 1 - 0.35 * u / rho
    disk = 2.1 * edge * band * swirl * (R_IN / np.maximum(rho, R_IN)) ** 0.45 * doppler
    span = R0 + disk_on * (R_OUT * 1.1 - R0)
    disk *= smooth((span - np.abs(u)) / (0.6 * R0)) * smooth((t - FLASH) / 0.8)

    # cara lejana del disco, curvada por encima de la sombra
    top = 0.5 - 0.5 * v / np.maximum(r, 1e-6)
    hband = np.exp(-((np.abs(r - 1.25 * R0) / (0.18 * R0 + 0.16 * R0 * top)) ** 2))
    stripes = 0.8 + 0.2 * np.sin(r / R0 * 14 + 0.6 * t)
    halo = 1.6 * hband * (0.25 + 0.75 * top ** 1.5) * stripes * smooth((t - FLASH) / 2.2)

    shock = 0.0
    if t > FLASH:
        front = R0 + (t - FLASH) * 0.55
        shock = np.exp(-(((r - front) / 0.04) ** 2)) * np.exp(-(t - FLASH) * 1.6)

    heat = np.maximum.reduce([ring * (0.9 + 0.3 * disk_on), aura, disk, halo, shock + 0 * r])
    heat = heat * (1 + 1.4 * flash)

    inside = r < R0 * 0.97
    heat = np.where(inside, np.where(v > 0, disk, 0.0), heat)

    lum = np.clip(heat / 1.3, 0, 1)
    on = heat > 0.07
    chars = np.where(on, RAMP_ARR[(lum ** 0.65 * (len(RAMP) - 1)).astype(int)], " ")
    col = (lum ** 0.75 * (LEVELS - 1)).astype(int)

    # estrellas
    star = ~on & ~inside & (rnd < 0.004)
    twinkle = 0.22 + 0.12 * np.sin(0.8 * t + tw * TAU)
    chars = np.where(star, np.where(tw < 0.2, "+", "."), chars)
    col = np.where(star, (twinkle * (LEVELS - 1)).astype(int), col)

    stats = {"spin": spin, "heat": float(heat.max()), "letters": int(on.sum())}
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
    put(chars, col, rows - 4, 2, f"spin {stats['spin']:.2f}   heat {stats['heat']:.2f}", HUD_DIM)
    put(chars, col, rows - 3, 2, f"letters {stats['letters']:,}", HUD_DIM)
    put(chars, col, rows - 1, 1, "$ py art.py", HUD_DIM)
    put(chars, col, rows - 1, -2, f"running · {fps:.0f} fps", HUD_DIM)


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
            ts = shutil.get_terminal_size((100, 40))
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
