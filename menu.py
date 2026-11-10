import argparse
import importlib
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# módulo, título, descripción, color de acento
SCENES = [
    ("art", "black hole", "anillo de luz, halo y disco de acreción", (236, 150, 70)),
    ("starry_night", "starry night", "el cielo de Van Gogh, trazo a trazo", (110, 170, 240)),
    ("campfire", "campfire", "llamas, brasas, chispas y humo", (255, 140, 40)),
    ("coffee", "coffee", "una taza recién servida y su vapor", (214, 170, 120)),
    ("cat", "sleeping cat", "respira, sueña y mueve una oreja", (240, 160, 70)),
]


def rgb(c):
    return f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m"


PINK, DIM, TEXT = rgb((232, 120, 150)), rgb((120, 112, 104)), rgb((214, 208, 200))
BOLD, RESET = "\x1b[1m", "\x1b[0m"


def available(name):
    return (HERE / f"{name}.py").exists()


def read_key():
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            return {"H": "up", "P": "down"}.get(msvcrt.getwch(), "")
        if ch == "\x03":
            raise KeyboardInterrupt
        return {"\r": "enter", " ": "enter", "\x1b": "esc"}.get(ch, ch.lower())

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        data = os.read(fd, 8).decode(errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    keys = {"\x1b[A": "up", "\x1b[B": "down", "\x1b": "esc", "\n": "enter", "\r": "enter", " ": "enter"}
    return keys.get(data, data[:1].lower())


def draw(sel, note):
    cols, rows = shutil.get_terminal_size((100, 30))
    wide = cols >= 84
    lines = [(PINK + BOLD, "ascii · chill"), (DIM, "animaciones para la terminal"), ("", "")]
    for i, (name, title, desc, accent) in enumerate(SCENES):
        mark = ">" if i == sel else " "
        row = f"{mark} {i + 1}  {title:<16}{name + '.py':<18}"
        if not available(name):
            lines.append((DIM, row + ("falta el archivo" if wide else "")))
        elif i == sel:
            lines.append((rgb(accent) + BOLD, row + (desc if wide else "")))
        else:
            lines.append((TEXT, row + (DIM + desc if wide else "")))
    lines += [("", ""), (DIM, f"flechas mover   enter lanzar   1-{len(SCENES)} directo   q salir"),
              (DIM, "ctrl+c dentro de una animación vuelve aquí")]
    if note:
        lines += [("", ""), (PINK, note)]

    width = max(len(text.replace(DIM, "")) for _, text in lines)
    left = max((cols - width) // 2, 0)
    top = max((rows - len(lines)) // 2, 0)
    out = ["\x1b[?1049h\x1b[?25l\x1b[2J"]
    for i, (style, text) in enumerate(lines):
        out.append(f"\x1b[{top + i + 1};{left + 1}H{style}{text}{RESET}")
    sys.stdout.write("".join(out))
    sys.stdout.flush()


def launch(name):
    if not available(name):
        return f"no encuentro {name}.py junto a menu.py"
    try:
        importlib.import_module(name).main()
    except ModuleNotFoundError as e:
        return f"falta el módulo {e.name}: py -m pip install {e.name}"
    except Exception as e:
        sys.stdout.write("\x1b[0m\x1b[?25h")
        return f"{name}.py se ha parado: {type(e).__name__}: {e}"
    return ""


def main():
    ap = argparse.ArgumentParser(description="Menú para lanzar las animaciones.")
    ap.add_argument("--fps", type=int, default=30, help="fotogramas por segundo de las animaciones")
    ap.parse_args()

    if os.name == "nt":
        os.system("")  # activa las secuencias ANSI en la consola de Windows
    sys.path.insert(0, str(HERE))

    sel, note = 0, ""
    try:
        while True:
            draw(sel, note)
            key = read_key()
            note = ""
            if key in ("up", "k", "w"):
                sel = (sel - 1) % len(SCENES)
            elif key in ("down", "j", "s"):
                sel = (sel + 1) % len(SCENES)
            elif key in ("q", "esc"):
                break
            elif key == "enter":
                note = launch(SCENES[sel][0])
            elif key.isdigit() and 1 <= int(key) <= len(SCENES):
                sel = int(key) - 1
                note = launch(SCENES[sel][0])
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
