# ascii · chill

Calm animations to leave running in your terminal. Each one draws itself in a few seconds and then loops. Everything is colored ASCII characters, generated in real time with Python and NumPy.

## Animations

| File | Scene | What happens |
| --- | --- | --- |
| `art.py` | Black hole | A ring of light traces itself, breathes, and in a flash the spinning accretion disk emerges. |
| `starry_night.py` | The Starry Night | Van Gogh's sky: the stars light up, the wind rolls in, the swirls coil, and the village and cypresses grow. |
| `campfire.py` | Campfire | Logs, stones and three sparks until it catches. Flames, embers, smoke and a crackle of sparks every few seconds. |
| `coffee.py` | Coffee | The cup appears, the stream pours in, and the coffee sits steaming while the crema slowly swirls. |
| `cat.py` | Sleeping cat | A tabby cat curls up on its cushion, its eyes close and it falls asleep. It breathes, dreams, and now and then twitches an ear. |

## Requirements

- Python 3.9 or higher
- NumPy
- A terminal with 24-bit color: Windows Terminal, kitty, Alacritty, WezTerm, iTerm2, GNOME Terminal…

## Installation

```bash
git clone https://github.com/bagpotato/ascii-chill.git
cd ascii-chill
pip install numpy
```

## Usage

With the menu:

```bash
python menu.py
```

| Key | Action |
| --- | --- |
| Arrows, `w`/`s` or `j`/`k` | Move the selection |
| `Enter` or space | Launch the selected animation |
| `1`–`5` | Launch directly |
| `Ctrl+C` | Exit the animation and return to the menu |
| `q` or `Esc` | Quit |

Or run each animation on its own:

```bash
python cat.py
```

On Windows use `py` instead of `python`:

```
py menu.py
```

### Options

`--fps N` changes the frames per second (30 by default). It works both in the menu and in each script:

```bash
python menu.py --fps 20
python campfire.py --fps 20
```

## Tips

- The animations adapt to the window size, even if you resize it while they run.
- The bigger the terminal and the smaller the font, the more detail you get. From about 150 columns by 40 rows they look the way they were designed to.
- If it stutters in full screen, lower the fps. `campfire.py` is the heaviest.

## Common problems on Windows

**`python art.py` does nothing and shows no error.** Windows ships a `python` alias that points to the Microsoft Store. Use `py`, or turn off the `python.exe` and `python3.exe` aliases in *Settings → Apps → Advanced app settings → App execution aliases*.

**Colors look wrong or strange codes appear.** The legacy console (classic `cmd.exe`) doesn't display 24-bit color properly. Open it in Windows Terminal.

## How it works

Each script is self-contained and follows the same recipe:

1. A grid is created with the coordinates of every terminal cell, corrected so that a circle looks round even though characters are taller than they are wide.
2. A `frame(t, grid)` function uses NumPy to compute, for all cells at once, which character and color apply at time `t`. No state is kept between frames: the whole scene is a function of time.
3. The result is converted to text with ANSI color sequences and written in one go to the terminal's alternate screen, so the terminal is left as it was when you exit.

The bottom line of each animation shows the time, a few facts about the scene, and the actual fps.

## Structure

```
menu.py            menu to launch the animations
art.py             black hole
starry_night.py    the starry night
campfire.py        campfire
coffee.py          coffee
cat.py             sleeping cat
```

To add a new animation to the menu, just create the script with a `main()` function and add a line to the `SCENES` list in `menu.py`.

## Credits
- `starry_night.py` is a free interpretation of *The Starry Night* by Vincent van Gogh (1889).
