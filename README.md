# ascii · chill

Animaciones tranquilas para dejar corriendo en la terminal. Cada una se dibuja sola en unos segundos y después se queda en bucle. Todo son caracteres ASCII con color, generados en tiempo real con Python y NumPy.

## Animaciones

| Archivo | Escena | Qué pasa |
| --- | --- | --- |
| `art.py` | Agujero negro | Un anillo de luz se traza, respira, y de un destello sale el disco de acreción girando. |
| `starry_night.py` | La noche estrellada | El cielo de Van Gogh: se encienden las estrellas, entra el viento, se enrollan los remolinos y crecen el pueblo y los cipreses. |
| `campfire.py` | Fogata | Troncos, piedras y tres chispazos hasta que prende. Llamas, brasas, humo y un chasquido de chispas cada pocos segundos. |
| `coffee.py` | Café | Aparece la taza, cae el chorro y el café se queda humeando mientras la crema gira despacio. |
| `cat.py` | Gato durmiendo | Un gato atigrado se acurruca en su cojín, se le cierran los ojos y se duerme. Respira, sueña y de vez en cuando mueve una oreja. |

## Requisitos

- Python 3.9 o superior
- NumPy
- Una terminal con color de 24 bits: Windows Terminal, kitty, Alacritty, WezTerm, iTerm2, GNOME Terminal…

## Instalación

```bash
git clone https://github.com/bagpotato/ascii-chill.git
cd ascii-chill
pip install numpy
```

## Uso

Con el menú:

```bash
python menu.py
```

| Tecla | Acción |
| --- | --- |
| Flechas, `w`/`s` o `j`/`k` | Mover la selección |
| `Enter` o espacio | Lanzar la animación seleccionada |
| `1`–`5` | Lanzar directamente |
| `Ctrl+C` | Salir de la animación y volver al menú |
| `q` o `Esc` | Salir |

O cada animación por separado:

```bash
python cat.py
```

En Windows usa `py` en lugar de `python`:

```
py menu.py
```

### Opciones

`--fps N` cambia los fotogramas por segundo (30 por defecto). Sirve tanto en el menú como en cada script:

```bash
python menu.py --fps 20
python campfire.py --fps 20
```

## Consejos

- Las animaciones se adaptan al tamaño de la ventana, también si la cambias en marcha.
- Cuanto más grande la terminal y más pequeña la fuente, más detalle. A partir de unas 150 columnas por 40 filas se ven como están pensadas.
- Si va a tirones a pantalla completa, baja los fps. `campfire.py` es la más pesada.

## Problemas habituales en Windows

**`python art.py` no hace nada y no da error.** Windows trae un alias de `python` que apunta a la Microsoft Store. Usa `py`, o desactiva los alias de `python.exe` y `python3.exe` en *Configuración → Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución de aplicaciones*.

**Los colores salen mal o aparecen códigos raros.** La consola antigua (`cmd.exe` clásico) no muestra bien el color de 24 bits. Ábrelo en Windows Terminal.

## Cómo funciona

Cada script es independiente y sigue la misma receta:

1. Se crea una rejilla con las coordenadas de cada celda de la terminal, corregidas para que un círculo se vea redondo aunque los caracteres sean más altos que anchos.
2. Una función `frame(t, rejilla)` calcula con NumPy, para todas las celdas a la vez, qué carácter y qué color tocan en el instante `t`. No se guarda estado entre fotogramas: la escena entera es una función del tiempo.
3. El resultado se convierte en texto con secuencias ANSI de color y se escribe de una vez en la pantalla alternativa de la terminal, así que al salir la terminal queda como estaba.

La línea inferior de cada animación muestra el tiempo, un par de datos de la escena y los fps reales.

## Estructura

```
menu.py            menú para lanzar las animaciones
art.py             agujero negro
starry_night.py    la noche estrellada
campfire.py        fogata
coffee.py          café
cat.py             gato durmiendo
```

Para añadir una animación nueva al menú basta con crear el script con una función `main()` y añadir una línea a la lista `SCENES` de `menu.py`.

## Créditos

- `art.py` nació de [este reel de Instagram](https://www.instagram.com/reel/DfgG102pfVQ/) con un agujero negro en ASCII.
- `starry_night.py` es una interpretación libre de *La noche estrellada* de Vincent van Gogh (1889).
