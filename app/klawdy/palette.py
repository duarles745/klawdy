"""Colours. ACCENT/ACCENT_SHADE change with the colour theme (themes.py), so always read them
as `palette.ACCENT` at draw time instead of importing the value."""
from . import themes

ACCENT = (0.843, 0.467, 0.341)
ACCENT_SHADE = (0.70, 0.36, 0.25)
EYE = (0.08, 0.06, 0.06)
OUT = (0.22, 0.13, 0.09)
TIP_GLOW = (1.0, 0.86, 0.35)

STEEL = (0.62, 0.66, 0.72)
STEEL_LIGHT = (0.85, 0.88, 0.92)
STEEL_DARK = (0.36, 0.39, 0.45)
HORN = (0.96, 0.91, 0.78)
HORN_SHADE = (0.80, 0.72, 0.55)
GOLD = (0.93, 0.74, 0.22)
WOOD = (0.50, 0.31, 0.17)
SHIELD_RED = (0.74, 0.17, 0.16)
SHIELD_CREAM = (0.95, 0.89, 0.74)

_color_key = ["orange"]


def color_key():
    return _color_key[0]


def apply(t=0.0):
    """Recompute the accent (the rainbow theme changes with time)."""
    global ACCENT, ACCENT_SHADE
    ACCENT, ACCENT_SHADE = themes.accent(_color_key[0], t)


def set_color_theme(key):
    _color_key[0] = key
    apply()


def lighter(rgb, k=0.35):
    return tuple(c + (1 - c) * k for c in rgb)


def themed_css(css):
    """Replace the fixed orange of the CSS with the current theme colour."""
    soft = tuple(1 - (1 - c) * 0.10 for c in ACCENT)
    return (css.replace(b"#d77757", themes.hexcol(ACCENT).encode())
            .replace(b"#fff8f4", themes.hexcol(soft).encode()))
