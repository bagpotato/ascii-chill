import argparse
import os
import shutil
import sys
import time

import numpy as np

TAU = 2 * np.pi
HALF_W = 1.10
ZOOM = 1.35
LEVELS = 20
TABLE_Y, RIM_Y, BOT_Y = 0.40, 0.02, 0.52
SURF_Y = RIM_Y + 0.012

WALL, TABLE, CUP, BAND, COFFEE, STEAM = range(6)
RAMPS = [
    [(20, 12, 10), (70, 40, 24), (150, 96, 50), (236, 180, 110)],
    [(22, 13, 9), (62, 36, 22), (112, 68, 40), (176, 118, 72)],
    [(60, 44, 38), (140, 114, 98), (224, 204, 184), (255, 250, 240)],
    [(90, 30, 18), (176, 66, 38), (226, 104, 64), (250, 170, 126)],
    [(28, 13, 6), (88, 46, 20), (168, 110, 58), (232, 196, 146)],
    [(40, 36, 34), (110, 102, 98), (182, 174, 168), (244, 238, 230)],
]
HUD_DIM, HUD_PINK = len(RAMPS) * LEVELS, len(RAMPS) * LEVELS + 1

SOLID = np.array(list(" .:-=+*#%@"))
# x de salida, fase y fuerza de cada hilo de vapor
WISPS = [(-0.20, 0.0, 1.0), (-0.05, 2.1, 0.9), (0.10, 4.4, 1.0), (0.22, 5.9, 0.75)]


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def palette():
    codes = []
    t = np.linspace(0, 1, LEVELS)
    for stops in RAMPS:
        stops = np.array(stops, float)
        xs = np.linspace(0, 1, len(stops))
        rgb = np.stack([np.interp(t, xs, stops[:, k]) for k in range(3)], 1).astype(int)
        codes += [f"\x1b[38;2;{r};{g};{b}m" for r, g, b in rgb]
    codes.append("\x1b[38;2;128;118;110m")
    codes.append("\x1b[38;2;232;120;150m")
    return np.array(codes)


PAL = palette()


def grid(cols, rows):
    fit = min(1.0, cols / (rows * 2 * HALF_W))
    y, x = np.mgrid[0:rows, 0:cols].astype(float)
    X = (x - cols / 2 + 0.5) / rows / fit
    Y = (y - rows / 2 + 0.5) / (rows / 2) / fit
    return X, Y, 2 / rows / fit, np.random.default_rng(3).random((rows, cols))


def pick(ramp, lum):
    return ramp[np.clip((lum * len(ramp)).astype(int), 0, len(ramp) - 1)]


def frame(t, G):
    X, Y, px, rnd = G
    X, Y, px = X / ZOOM, (Y - 0.72) / ZOOM + 0.62, px / ZOOM
    lum = np.zeros_like(X)
    mat = np.zeros(X.shape, int)
    chars = np.full(X.shape, " ")

    def paint(mask, l, m, c):
        nonlocal lum, mat, chars
        lum, mat, chars = np.where(mask, l, lum), np.where(mask, m, mat), np.where(mask, c, chars)

    amb = smooth(t / 1.2)

    # pared con el resplandor de una lámpara
    lamp = np.exp(-(((X - 0.9) / 1.1) ** 2 + ((Y + 0.9) / 0.9) ** 2))
    wl = (0.12 + 0.55 * lamp * (0.94 + 0.06 * np.sin(0.7 * t))) * amb
    paint((Y <= TABLE_Y) & (rnd < 0.03 + 0.10 * lamp), wl, WALL, ".")

    # mesa de madera y sombra de la taza
    kg = TAU / max(2.2 * px, 0.05)
    grain = 0.5 + 0.5 * np.sin(kg * Y + 2.5 * np.sin(1.3 * X + 4 * Y))
    pool = np.exp(-((X / 1.0) ** 2 + ((Y - 0.62) / 0.5) ** 2))
    shadow = np.exp(-(((X - 0.25) / 0.80) ** 2 + ((Y - 0.67) / 0.09) ** 2) ** 2)
    tl = (0.18 + 0.30 * grain) * (0.5 + 0.8 * pool) * (1 - 0.6 * shadow) * amb
    paint(Y > TABLE_Y, tl, TABLE, pick(np.array(list(" .-_=~")), tl * 2.2))

    # plato
    shown = X < -0.8 + 1.7 * smooth((t - 0.6) / 1.2)
    e1 = (X / 0.74) ** 2 + ((Y - 0.60) / 0.105) ** 2
    e2 = (X / 0.74) ** 2 + ((Y - 0.628) / 0.105) ** 2
    ring = np.exp(-(((np.sqrt(e1) - 0.84) / 0.07) ** 2))
    sl = 0.58 - 0.2 * X / 0.74 + 0.22 * ring - 0.12 * (e1 < 0.3)
    paint((e2 < 1) & shown, 0.42 - 0.12 * X, CUP, "=")
    paint((e1 < 1) & shown, sl, CUP, pick(SOLID, sl))

    # taza
    yrev = BOT_Y + 0.08 - smooth((t - 1.4) / 1.6) * (BOT_Y + 0.17 - RIM_Y)
    s = (Y - RIM_Y) / (BOT_Y - RIM_Y)
    w = 0.40 - 0.13 * np.clip(s, 0, 1) ** 2.2
    nx = X / w
    bottom = BOT_Y + 0.05 * np.sqrt(np.clip(1 - (X / 0.27) ** 2, 0, 1))
    body = (np.abs(nx) < 1) & (Y > RIM_Y) & (Y < bottom) & (Y > yrev)
    cl = 0.46 + 0.42 * np.clip(1 - ((nx + 0.35) / 1.3) ** 2, 0, 1) + 0.2 * np.exp(-(((nx + 0.55) / 0.09) ** 2))
    cl = cl + 0.12 * np.exp(-(((nx - 0.93) / 0.06) ** 2))
    cl = np.clip(cl, 0, 1)

    ho = ((X - 0.47) / 0.17) ** 2 + ((Y - 0.27) / 0.19) ** 2
    hi = ((X - 0.47) / 0.10) ** 2 + ((Y - 0.27) / 0.12) ** 2
    hl = 0.66 - 0.7 * (Y - 0.27)
    paint((ho < 1) & (hi > 1) & (X > 0.3) & (Y > yrev), hl, CUP, pick(SOLID, hl))

    curve = s - 0.07 * np.sqrt(np.clip(1 - nx * nx, 0, 1))
    stripe = (curve > 0.26) & (curve < 0.50)
    paint(body, cl, np.where(stripe, BAND, CUP), pick(SOLID, cl))

    rim = (X / 0.40) ** 2 + ((Y - RIM_Y) / 0.075) ** 2
    inner = 0.42 + 0.3 * X / 0.40
    il = np.where(rim > 0.80, 0.97, inner)
    paint((rim < 1) & (Y > yrev), il, CUP, pick(SOLID, il))

    # café: primero ondas del chorro, luego la crema girando despacio
    fill = smooth((t - 3.2) / 2.2)
    settle = smooth((t - 5.4) / 2.0)
    fr = max(fill ** 0.5, 1e-3)
    qx, qy = X / (0.355 * fr), (Y - SURF_Y) / (0.058 * fr)
    r = np.hypot(qx, qy)
    swirl = 0.5 + 0.5 * np.sin(7 * r + 2 * np.arctan2(qy, qx) - 0.35 * t)
    ripple = 0.5 + 0.5 * np.sin(22 * r * fr - 9 * t)
    kl = 0.2 + 0.6 * (settle * swirl + (1 - settle) * ripple) ** 1.5
    kl = kl + 0.25 * np.exp(-(((qx + 0.45) / 0.3) ** 2 + ((qy + 0.3) / 0.4) ** 2))
    coffee = (r < 1) & (fill > 0)
    paint(coffee, kl, COFFEE, pick(SOLID, kl))

    # chorro
    head, tail = -1.3 + (t - 3.0) * 9, -1.3 + (t - 5.3) * 9
    flow = 0.5 + 0.5 * np.sin(40 * Y - 30 * t)
    stream = (np.abs(X - 0.03) < max(0.016, 0.26 * px)) & (Y < min(head, SURF_Y)) & (Y > tail)
    paint(stream, 0.55 + 0.3 * flow, COFFEE, np.where(flow > 0.5, "|", ":"))

    # vapor
    st = smooth((t - 5.4) / 2.5)
    h = SURF_Y - Y
    hc = np.clip(h, 0, 3)
    steam = np.zeros_like(X)
    slope = np.zeros_like(X)
    for i, (x0, ph, amp) in enumerate(WISPS):
        arg = 5.0 * hc - 1.1 * t + ph
        sway = 0.07 * np.sin(0.23 * t + i)
        cx = x0 * (1 - 0.3 * np.clip(hc, 0, 1)) + (0.035 + 0.11 * hc) * np.sin(arg) + sway * hc
        a = np.exp(-(((X - cx) / (0.02 + 0.05 * hc)) ** 2)) * smooth(h / 0.06) * np.exp(-hc / 0.8)
        a = a * (0.45 + 0.55 * np.sin(5 * hc - 1.5 * t + 2 * ph)) * amp * st
        slope = np.where(a > steam, 0.11 * np.sin(arg) + (0.035 + 0.11 * hc) * 5.0 * np.cos(arg) + sway, slope)
        steam = np.maximum(steam, a)
    curl = np.where(slope > 0.45, "/", np.where(slope < -0.45, "\\",
                    np.where(slope > 0.12, ")", np.where(slope < -0.12, "(", "|"))))
    sc = np.where(steam < 0.2, ".", np.where(steam < 0.34, ":", curl))
    paint((steam > 0.09) & ~coffee & ~((rim < 1) & (Y > RIM_Y)), 0.25 + 0.75 * steam, STEAM, sc)

    col = mat * LEVELS + (np.clip(lum, 0, 1) * (LEVELS - 1)).astype(int)
    stats = {
        "temp": 92 - 30 * (1 - np.exp(-max(t - 5.5, 0) / 240)) if fill > 0 else 21.0,
        "steam": float(st * (0.85 + 0.15 * np.sin(0.5 * t))),
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
    put(chars, col, rows - 4, 2, f" temp {stats['temp']:.1f} C   steam {stats['steam']:.2f} ", HUD_DIM)
    put(chars, col, rows - 3, 2, f" letters {stats['letters']:,} ", HUD_DIM)
    put(chars, col, rows - 1, 1, " $ py coffee.py ", HUD_DIM)
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
