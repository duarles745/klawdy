"""Temas do mascote: cores, fantasias (personagens famosos) e cenários de fundo.

Tudo em pixel art desenhada com cairo, sem imagens externas. O mascote.py só chama:
  accent(key, t)                 -> (cor, sombra) do tema de cor
  costume_body(key)              -> (cor, sombra) do corpo da fantasia, ou None (usa o tema de cor)
  costume_hides_eyes(key)        -> True se a fantasia desenha os próprios olhos
  draw_costume(...)              -> roupa/acessórios por cima do corpo
  draw_scene(key, cr, w, h, t)   -> cenário atrás do mascote
"""
import colorsys
import math

import cairo

OUT = (0.22, 0.13, 0.09)

# ---------------------------------------------------------------- temas de cor
# (chave, nome, emoji, cor principal, sombra)
COLOR_THEMES = [
    ("orange", "Laranja (clássico)", "🟠", (0.843, 0.467, 0.341), (0.70, 0.36, 0.25)),
    ("blue", "Azul", "🔵", (0.30, 0.55, 0.92), (0.20, 0.38, 0.72)),
    ("green", "Verde", "🟢", (0.30, 0.74, 0.40), (0.20, 0.55, 0.28)),
    ("purple", "Roxo", "🟣", (0.60, 0.40, 0.88), (0.43, 0.27, 0.68)),
    ("pink", "Rosa", "🩷", (0.95, 0.50, 0.70), (0.78, 0.33, 0.52)),
    ("red", "Vermelho", "🔴", (0.88, 0.25, 0.25), (0.67, 0.15, 0.15)),
    ("cyan", "Ciano", "🩵", (0.25, 0.78, 0.85), (0.15, 0.58, 0.66)),
    ("yellow", "Amarelo", "🟡", (0.96, 0.78, 0.20), (0.78, 0.58, 0.10)),
    ("graphite", "Grafite", "⚫", (0.42, 0.45, 0.50), (0.28, 0.30, 0.34)),
    ("rainbow", "Arco-íris", "🌈", None, None),
]
_COLORS = {k: (m, s) for k, _n, _e, m, s in COLOR_THEMES}


def accent(key, t=0.0):
    """Cor principal e sombra do tema de cor (o arco-íris muda com o tempo)."""
    if key == "rainbow":
        h = (t * 0.12) % 1.0
        return colorsys.hsv_to_rgb(h, 0.62, 0.92), colorsys.hsv_to_rgb(h, 0.75, 0.70)
    return _COLORS.get(key) or _COLORS["orange"]


def hexcol(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


# ---------------------------------------------------------------- fantasias
# (chave, nome, emoji, corpo/sombra ou None, esconde olhos, tem cenário)
COSTUMES = [
    ("none", "Klawdy clássico", "🟧", None, False, True),
    ("creeper", "Creeper (Minecraft)", "🟩", ((0.36, 0.72, 0.31), (0.22, 0.50, 0.20)), True, True),
    ("doom", "Doom Slayer (DOOM)", "💀", ((0.31, 0.47, 0.27), (0.20, 0.32, 0.17)), True, True),
    ("mario", "Mario (Super Mario)", "🍄", None, False, True),
    ("pikachu", "Pikachu (Pokémon)", "⚡", ((0.99, 0.84, 0.18), (0.86, 0.64, 0.10)), False, True),
    ("sonic", "Sonic (Sega)", "💨", ((0.12, 0.32, 0.88), (0.07, 0.20, 0.64)), True, True),
    ("amongus", "Tripulante (Among Us)", "🚀", None, True, True),
    ("steve", "Steve (Minecraft)", "⛏️", ((0.78, 0.56, 0.42), (0.62, 0.42, 0.30)), True, True),
    ("gta6", "Vice City vaporwave (estilo GTA 6)", "🌴", None, True, True),
]
_COSTUMES = {c[0]: c for c in COSTUMES}


def _info(key):
    return _COSTUMES.get(key) or _COSTUMES["none"]


def costume_body(key):
    return _info(key)[3]


def costume_hides_eyes(key):
    return _info(key)[4]


def costume_has_scene(key):
    return _info(key)[5]


# ---------------------------------------------------------------- utilidades
def cells(cr, ox, oy, lst, rgb, outline=True, alpha=1.0):
    """Células de 8x8 (c = coluna, h = meia-linha), na mesma grade do equipamento viking."""
    if outline:
        cr.set_source_rgba(*OUT, 0.7)
        for (c, h) in lst:
            cr.rectangle(ox + c * 8 - 1.5, oy + h * 8 - 1.5, 11, 11)
        cr.fill()
    cr.set_source_rgba(*rgb, alpha)
    for (c, h) in lst:
        cr.rectangle(ox + c * 8, oy + h * 8, 8.5, 8.5)
    cr.fill()


def mirror(lst):
    """Espelha no centro do corpo (c -> 17 - c)."""
    return lst + [(17 - c, h) for c, h in lst]


def half_cells(body):
    for (c, r) in body:
        yield (c, 2 * r)
        yield (c, 2 * r + 1)


def rect(cr, x, y, w, h, rgb, alpha=1.0):
    cr.set_source_rgba(*rgb, alpha)
    cr.rectangle(x, y, w, h)
    cr.fill()


def rrect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def noise(a, b, n):
    return ((a * 73856093) ^ (b * 19349663) ^ (n * 83492791)) % 1000 / 1000.0


def hand_row(body, col, default=2):
    return min((r for (c, r) in body if c == col), default=default)


# ================================================================ fantasias
def draw_costume(key, cr, ox, oy, body, st, t, eye_kind, gear):
    fn = _DRAW.get(key)
    if fn:
        cr.save()
        fn(cr, ox, oy, body, st, t, eye_kind, gear)
        cr.restore()


def _creeper(cr, ox, oy, body, st, t, eye_kind, gear):
    # textura "manchada" do bloco
    for (c, h) in half_cells(body):
        n = noise(c, h, 3)
        if n < 0.22:
            cells(cr, ox, oy, [(c, h)], (0.27, 0.60, 0.24), outline=False)
        elif n > 0.84:
            cells(cr, ox, oy, [(c, h)], (0.48, 0.82, 0.40), outline=False)
    face = (0.05, 0.09, 0.05)
    eyes = mirror([(4, 2), (5, 2), (4, 3), (5, 3)])
    if eye_kind == "closed":
        eyes = mirror([(4, 3), (5, 3)])
    cells(cr, ox, oy, eyes, face, outline=False)
    mouth = [(8, 4), (9, 4), (7, 5), (8, 5), (9, 5), (10, 5), (7, 6), (10, 6)]
    cells(cr, ox, oy, mouth, face, outline=False)
    if st == "attention":                       # "ssssss…" antes de explodir
        a = 0.55 * max(0.0, math.sin(t * 9))
        cells(cr, ox, oy, list(half_cells(body)), (1, 1, 1), outline=False, alpha=a)


def _doom(cr, ox, oy, body, st, t, eye_kind, gear):
    helm = (0.22, 0.36, 0.20)
    helm_hi = (0.40, 0.58, 0.34)
    metal = (0.42, 0.43, 0.40)
    # ombreiras (braços) e botas
    for (c, r) in body:
        if c in (2, 15) and r <= 3:
            cells(cr, ox, oy, [(c, 2 * r), (c, 2 * r + 1)], metal, outline=False)
        if r == 4:
            cells(cr, ox, oy, [(c, 8), (c, 9)], (0.30, 0.24, 0.20), outline=False)
    # capacete cobrindo a cabeça + queixeira
    cells(cr, ox, oy, [(c, h) for c in range(4, 14) for h in range(0, 6)], helm, outline=False)
    cells(cr, ox, oy, [(c, 0) for c in range(5, 13)], helm_hi, outline=False)
    cells(cr, ox, oy, [(c, 6) for c in range(6, 12)], metal, outline=False)
    # viseira escura com brilho
    rect(cr, ox + 5 * 8, oy + 2 * 8 + 2, 8 * 8, 14, (0.04, 0.04, 0.04))
    glow = (1.0, 0.72, 0.10)
    if st == "attention":
        glow = (1.0, 0.15, 0.10) if int(t * 8) % 2 == 0 else (1.0, 0.72, 0.10)
    gh = 2 if eye_kind == "closed" else 5
    rect(cr, ox + 5 * 8 + 3, oy + 2 * 8 + 2 + (14 - gh) / 2, 8 * 8 - 6, gh, glow)
    # símbolo no peito
    cells(cr, ox, oy, [(8, 7), (9, 7)], (0.85, 0.30, 0.10), outline=False)
    # espingarda na mão direita (some quando uma skill traz a espada)
    if "sword" not in gear:
        hx = ox + 17 * 8 - 2
        hy = oy + hand_row(body, 16) * 16 + 7
        rect(cr, hx, hy - 3, 36, 4, (0.20, 0.20, 0.22))
        rect(cr, hx, hy + 1, 36, 3, (0.30, 0.30, 0.33))
        rect(cr, hx + 6, hy + 4, 14, 4, (0.50, 0.31, 0.17))
        rect(cr, hx - 8, hy - 2, 9, 8, (0.50, 0.31, 0.17))
        if st == "working" and (t * 1.1) % 1.0 < 0.12:          # clarão do tiro
            cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
            cr.set_source_rgba(1.0, 0.8, 0.2, 0.95)
            cr.arc(hx + 40, hy, 8, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.arc(hx + 40, hy, 3.5, 0, 2 * math.pi)
            cr.fill()


def _mario(cr, ox, oy, body, st, t, eye_kind, gear):
    red, red_d = (0.86, 0.10, 0.10), (0.62, 0.05, 0.05)
    blue = (0.15, 0.26, 0.86)
    brown = (0.30, 0.15, 0.08)
    # macacão
    cells(cr, ox, oy, [(c, h) for c in range(4, 14) for h in (6, 7)], blue, outline=False)
    cells(cr, ox, oy, [(4, 4), (4, 5), (13, 4), (13, 5)], blue, outline=False)
    cells(cr, ox, oy, [(5, 6), (12, 6)], (0.98, 0.84, 0.12), outline=False)       # botões
    # luvas brancas
    for (c, r) in body:
        if c in (1, 16) and r <= 3:
            cells(cr, ox, oy, [(c, 2 * r), (c, 2 * r + 1)], (0.98, 0.98, 0.98), outline=False)
    # bigode
    cells(cr, ox, oy, [(7, 4), (10, 4)] + [(c, 5) for c in range(6, 12) if c not in (8, 9)],
          brown, outline=False)
    # boné
    cap = ([(c, -2) for c in range(6, 12)] + [(c, -1) for c in range(4, 14)]
           + [(c, 0) for c in range(3, 15)])
    cells(cr, ox, oy, cap, red)
    cells(cr, ox, oy, [(c, 1) for c in range(3, 15)], red_d, outline=False)
    cells(cr, ox, oy, [(c, 0) for c in range(5, 8)], (0.98, 0.45, 0.40), outline=False)       # brilho
    cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
    cr.arc(ox + 9 * 8, oy - 8, 6.5, 0, 2 * math.pi)
    cr.set_source_rgb(1, 1, 1)
    cr.fill()
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(10)
    cr.set_source_rgb(*red)
    cr.move_to(ox + 9 * 8 - 4.2, oy - 4.5)
    cr.show_text("M")
    if st == "done":                                                   # moeda subindo
        ph = (t * 1.5) % 1.0
        cr.set_source_rgb(0.98, 0.80, 0.10)
        cr.save()
        cr.translate(ox + 16 * 8 + 8, oy - 12 - ph * 22)
        cr.scale(max(0.15, abs(math.cos(t * 9))), 1)
        cr.arc(0, 0, 7, 0, 2 * math.pi)
        cr.fill()
        cr.restore()


def _pikachu(cr, ox, oy, body, st, t, eye_kind, gear):
    y, tip = (0.99, 0.84, 0.18), (0.10, 0.08, 0.06)
    ear_l = [(4, -1), (5, -1), (4, -2), (5, -2), (4, -3), (5, -3), (3, -4), (4, -4), (3, -5), (4, -5)]
    ear_tip = [(3, -6), (4, -6), (3, -7), (3, -5)]
    ear_l = [c for c in ear_l if c not in ear_tip]
    cells(cr, ox, oy, mirror(ear_l), y)
    cells(cr, ox, oy, mirror(ear_tip), tip)
    # bochechas vermelhas
    cells(cr, ox, oy, mirror([(3, 4), (4, 4), (3, 5), (4, 5)]), (0.92, 0.18, 0.12), outline=False)
    # focinho
    cells(cr, ox, oy, [(8, 3)], tip, outline=False)
    cells(cr, ox, oy, [(7, 5), (8, 6), (9, 6), (10, 5)], tip, outline=False)
    # listras marrons nas costas (aparecem na barriga do desenho, fica simpático)
    cells(cr, ox, oy, [(6, 7), (11, 7)], (0.55, 0.34, 0.12), outline=False)
    if st in ("working", "attention"):                                  # faíscas
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        for i, (bx, by) in enumerate(((ox + 2 * 8, oy + 40), (ox + 17 * 8, oy + 36))):
            if int(t * 6 + i) % 2 == 0:
                s = 1 if i else -1
                cr.set_source_rgb(1.0, 0.95, 0.30)
                cr.move_to(bx, by - 12)
                cr.line_to(bx + 6 * s, by - 2)
                cr.line_to(bx + 1 * s, by - 2)
                cr.line_to(bx + 8 * s, by + 12)
                cr.line_to(bx - 1 * s, by + 2)
                cr.line_to(bx + 3 * s, by + 2)
                cr.close_path()
                cr.fill()


def _gta6(cr, ox, oy, body, st, t, eye_kind, gear):
    pink, cyan, purple = (1.0, 0.25, 0.66), (0.15, 0.86, 0.92), (0.56, 0.26, 0.86)
    # camisa havaiana
    palette = (pink, cyan, purple)
    shirt = [(c, h) for c in range(3, 15) for h in (5, 6, 7)]
    for (c, h) in shirt:
        cells(cr, ox, oy, [(c, h)], palette[(c + 2 * h) % 3], outline=False)
    cells(cr, ox, oy, [(c, h) for (c, h) in shirt if noise(c, h, 9) > 0.92], (1, 1, 1), outline=False, alpha=0.9)
    cells(cr, ox, oy, [(8, 5), (9, 5), (8, 4), (9, 4)][:2], (1, 1, 1), outline=False, alpha=0.95)    # gola
    # óculos escuros
    shade = (0.05, 0.04, 0.10)
    lens = [(c, h) for c in (4, 5, 6, 7, 10, 11, 12, 13) for h in (2, 3)]
    cells(cr, ox, oy, lens + [(8, 2), (9, 2), (3, 2), (14, 2)], shade, outline=False)
    cells(cr, ox, oy, [(4, 2), (10, 2)], pink, outline=False, alpha=0.8)
    cells(cr, ox, oy, [(5, 3), (11, 3)], cyan, outline=False, alpha=0.8)
    ph = (t * 0.45) % 1.6                                               # brilho cruzando as lentes
    if ph < 1:
        gx = 4 + ph * 4
        for base in (0, 6):
            rect(cr, ox + (gx + base) * 8, oy + 2 * 8, 4, 12, (1, 1, 1), 0.7)


def _sonic(cr, ox, oy, body, st, t, eye_kind, gear):
    blue, blue_d = (0.12, 0.32, 0.88), (0.07, 0.20, 0.64)
    peach = (0.98, 0.78, 0.56)
    quills = [(4, -1), (5, -1), (3, -2), (4, -2), (2, -3), (3, -3), (1, -4)]
    cells(cr, ox, oy, mirror(quills) + [(8, -1), (9, -1), (8, -2), (9, -2), (8, -3)], blue)
    cells(cr, ox, oy, [(3, -3), (4, -2)], blue_d, outline=False)
    # focinho e barriga
    cells(cr, ox, oy, [(c, h) for c in range(6, 12) for h in (4, 5, 6)] + [(c, 7) for c in range(7, 11)],
          peach, outline=False)
    cells(cr, ox, oy, [(8, 4), (9, 4)], (0.05, 0.05, 0.08), outline=False)           # nariz
    cells(cr, ox, oy, [(7, 6), (10, 6)], (0.55, 0.25, 0.20), outline=False)            # sorriso
    # olhos grandes
    eyes = mirror([(5, 2), (6, 2), (5, 3), (6, 3)])
    if eye_kind == "closed":
        cells(cr, ox, oy, mirror([(5, 3), (6, 3)]), (0.05, 0.05, 0.08), outline=False)
    else:
        cells(cr, ox, oy, eyes, (1, 1, 1), outline=False)
        look = 1 if (st == "working" and math.sin(t * 1.5) > 0) else 0
        cells(cr, ox, oy, [(6 - look, 3), (11 + look, 3)], (0.10, 0.45, 0.20), outline=False)
    # luvas e tênis
    for (c, r) in body:
        if c in (1, 16) and r <= 3:
            cells(cr, ox, oy, [(c, 2 * r), (c, 2 * r + 1)], (0.98, 0.98, 0.98), outline=False)
        if r == 4:
            cells(cr, ox, oy, [(c, 8), (c, 9)], (0.85, 0.10, 0.10), outline=False)
    if st == "working":                                                 # linhas de velocidade
        for i in range(3):
            x = ox - 8 - ((t * 140 + i * 37) % 40)
            rect(cr, x, oy + 20 + i * 14, 22, 2, (1, 1, 1), 0.7)


def _amongus(cr, ox, oy, body, st, t, eye_kind, gear):
    # mochila (sombra da cor do tripulante, informada pelo painter.py)
    cells(cr, ox, oy, [(2, h) for h in range(3, 8)], _ACCENT_SHADE[0], outline=True)
    # visor
    glass, glass_d = (0.62, 0.88, 0.97), (0.30, 0.60, 0.78)
    vis = [(c, h) for c in range(7, 14) for h in (2, 3, 4)]
    vis = [x for x in vis if x not in ((7, 2), (13, 2), (7, 4), (13, 4))]
    if eye_kind == "closed":
        glass = (0.30, 0.52, 0.66)
    cells(cr, ox, oy, vis, glass, outline=True)
    cells(cr, ox, oy, [(c, 4) for c in range(8, 13)], glass_d, outline=False)
    cells(cr, ox, oy, [(8, 2), (9, 2), (8, 3)], (1, 1, 1), outline=False, alpha=0.85)
    if st == "attention":                                               # "impostor!" -> visor pisca
        a = 0.6 * max(0.0, math.sin(t * 9))
        cells(cr, ox, oy, vis, (1, 0.2, 0.2), outline=False, alpha=a)


_ACCENT_SHADE = [(0.55, 0.30, 0.22)]


def set_accent_shade(rgb):
    """O tripulante usa a cor do tema; o mascote.py informa a sombra atual."""
    _ACCENT_SHADE[0] = rgb


def _steve(cr, ox, oy, body, st, t, eye_kind, gear):
    hair, hair_d = (0.27, 0.16, 0.08), (0.18, 0.10, 0.05)
    cells(cr, ox, oy, [(c, h) for c in range(3, 15) for h in (0, 1)], hair, outline=False)
    cells(cr, ox, oy, [(3, 2), (14, 2), (3, 3), (14, 3)], hair, outline=False)
    for (c, h) in [(c, h) for c in range(3, 15) for h in (0, 1)]:
        if noise(c, h, 5) > 0.7:
            cells(cr, ox, oy, [(c, h)], hair_d, outline=False)
    # olhos: branco por fora, azul por dentro
    if eye_kind == "closed":
        cells(cr, ox, oy, [(4, 3), (5, 3), (12, 3), (13, 3)], hair, outline=False)
    else:
        cells(cr, ox, oy, [(4, 3), (13, 3)], (1, 1, 1), outline=False)
        cells(cr, ox, oy, [(5, 3), (12, 3)], (0.25, 0.20, 0.55), outline=False)
    # barba rala e boca
    cells(cr, ox, oy, [(c, h) for c in range(5, 13) for h in (4, 5) if c not in (8, 9) or h == 4],
          (0.62, 0.42, 0.30), outline=False)
    cells(cr, ox, oy, [(c, 5) for c in range(6, 12)], (0.40, 0.22, 0.16), outline=False)
    # camiseta ciano e calça azul
    cells(cr, ox, oy, [(c, h) for c in range(3, 15) for h in (6, 7)], (0.05, 0.66, 0.68), outline=False)
    for (c, r) in body:
        if c in (2, 15) and r <= 3:
            cells(cr, ox, oy, [(c, 2 * r), (c, 2 * r + 1)], (0.05, 0.66, 0.68), outline=False)
        if r == 4:
            cells(cr, ox, oy, [(c, 8), (c, 9)], (0.25, 0.25, 0.62), outline=False)
    if "sword" not in gear:                                             # picareta
        hx = ox + 17 * 8 - 2
        hy = oy + hand_row(body, 16) * 16 + 4
        rect(cr, hx + 6, hy - 22, 4, 34, (0.50, 0.31, 0.17))
        rect(cr, hx - 8, hy - 26, 28, 6, (0.45, 0.88, 0.90))
        rect(cr, hx - 12, hy - 22, 6, 6, (0.45, 0.88, 0.90))
        rect(cr, hx + 20, hy - 22, 6, 6, (0.45, 0.88, 0.90))
        cr.set_source_rgba(*OUT, 0.8)
        cr.set_line_width(1.2)
        cr.rectangle(hx - 8, hy - 26, 28, 6)
        cr.stroke()


_DRAW = {"creeper": _creeper, "doom": _doom, "mario": _mario, "pikachu": _pikachu, "gta6": _gta6,
         "sonic": _sonic, "amongus": _amongus, "steve": _steve}


# ================================================================ cenários
def draw_scene(key, cr, w, h, t):
    fn = _SCENE.get(key)
    if not fn:
        return
    cr.save()
    cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.clip()
    fn(cr, w, h, t)
    cr.restore()
    return True


def _vgrad(cr, y0, y1, stops, x0=0, x1=230):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for off, rgb in stops:
        g.add_color_stop_rgb(off, *rgb)
    cr.set_source(g)
    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
    cr.fill()


def _palm(cr, x, base_y, top_x, top_y, size, t, seed, rgb):
    cr.set_source_rgb(*rgb)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_width(4.5)
    cr.move_to(x, base_y)
    cr.curve_to(x + (top_x - x) * 0.1, base_y - (base_y - top_y) * 0.5,
                top_x - (top_x - x) * 0.3, top_y + (base_y - top_y) * 0.25, top_x, top_y)
    cr.stroke()
    sway = math.sin(t * 1.3 + seed) * 0.07
    for i, a in enumerate((-2.9, -2.35, -1.9, -1.2, -0.75, -0.2, 0.05)):
        a += sway
        L = size * (0.85 + 0.15 * ((i * 7 + seed) % 3) / 2)
        ex, ey = top_x + math.cos(a) * L, top_y + math.sin(a) * L * 0.55 + L * 0.45 * (abs(math.cos(a)) ** 1.5)
        mx, my = top_x + math.cos(a) * L * 0.55, top_y + math.sin(a) * L * 0.7 - 5
        cr.set_line_width(3.2)
        cr.move_to(top_x, top_y)
        cr.curve_to(mx, my, mx + math.cos(a) * 4, my + 2, ex, ey)
        cr.stroke()
    cr.arc(top_x, top_y + 2, 3, 0, 2 * math.pi)
    cr.fill()


def _scene_gta6(cr, w, h, t):
    hz = 120
    _vgrad(cr, 0, hz, [(0, (0.10, 0.04, 0.32)), (0.45, (0.50, 0.10, 0.58)),
                       (0.78, (1.0, 0.33, 0.58)), (1, (1.0, 0.66, 0.30))])
    for i in range(14):                                                   # estrelas
        sx, sy = noise(i, 1, 5) * w, noise(i, 2, 5) * 60
        a = 0.35 + 0.5 * abs(math.sin(t * 1.5 + i))
        rect(cr, sx, sy, 1.5, 1.5, (1, 1, 1), a)
    # sol listrado
    cx, cy, r = w / 2, 86, 46
    sun = cairo.LinearGradient(0, cy - r, 0, cy + r)
    sun.add_color_stop_rgb(0, 1.0, 0.92, 0.35)
    sun.add_color_stop_rgb(0.55, 1.0, 0.45, 0.45)
    sun.add_color_stop_rgb(1, 1.0, 0.15, 0.62)
    y = cy - r
    # faixas que ficam mais finas no topo e mais grossas embaixo (corte horizontal)
    while y < cy + r:
        frac = (y - (cy - r)) / (2 * r)
        hh = 6 + 8 * frac if frac > 0.5 else 12
        cut = 0 if frac < 0.5 else 1 + 4.5 * (frac - 0.5) * 2
        cr.save()
        cr.rectangle(0, y, w, max(0.5, hh - cut))
        cr.clip()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source(sun)
        cr.fill()
        cr.restore()
        y += hh
    # skyline
    for i in range(22):
        bx = i * 11 - 4
        bh = 14 + noise(i, 4, 8) * 34
        rect(cr, bx, hz - bh, 10, bh + 1, (0.20, 0.05, 0.32))
        for j in range(int(bh // 8)):
            if noise(i, j, 11) > 0.62:
                rect(cr, bx + 2, hz - bh + 3 + j * 8, 2, 2, (1.0, 0.45, 0.8), 0.8)
    # chão com grade neon
    _vgrad(cr, hz, h, [(0, (0.30, 0.03, 0.42)), (1, (0.08, 0.01, 0.20))])
    cr.set_line_width(1.1)
    cr.set_source_rgba(0.20, 0.95, 1.0, 0.75)
    ph = (t * 0.45) % 1.0
    for i in range(0, 9):
        yy = hz + ((i + ph) / 8.5) ** 2.1 * (h - hz)
        cr.move_to(0, yy)
        cr.line_to(w, yy)
    for i in range(-9, 10):
        cr.move_to(w / 2, hz)
        cr.line_to(w / 2 + i * 40, h)
    cr.stroke()
    cr.set_source_rgba(1.0, 0.35, 0.85, 0.95)
    cr.set_line_width(1.8)
    cr.move_to(0, hz)
    cr.line_to(w, hz)
    cr.stroke()
    # palmeiras (silhuetas)
    dark = (0.06, 0.02, 0.14)
    _palm(cr, 24, h + 2, 34, 52, 34, t, 1, dark)
    _palm(cr, 8, h + 2, 4, 96, 24, t, 4, dark)
    _palm(cr, w - 22, h + 2, w - 34, 60, 33, t, 2, dark)
    _palm(cr, w - 6, h + 2, w - 2, 100, 22, t, 5, dark)
    cr.set_source_rgba(1.0, 0.35, 0.85, 0.9)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_doom(cr, w, h, t):
    hz = 132
    _vgrad(cr, 0, hz, [(0, (0.06, 0.0, 0.02)), (0.55, (0.42, 0.04, 0.03)), (1, (0.98, 0.38, 0.06))])
    # pentagrama invertido
    cx, cy, r = w / 2, 58, 34
    a = 0.30 + 0.12 * math.sin(t * 2)
    cr.set_source_rgba(0.85, 0.05, 0.05, a)
    cr.set_line_width(2)
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.stroke()
    pts = [(cx + r * math.cos(math.pi / 2 + i * 2 * math.pi / 5),
            cy + r * math.sin(math.pi / 2 + i * 2 * math.pi / 5)) for i in range(5)]
    for i in range(5):
        p = pts[(i * 2) % 5]
        (cr.move_to if i == 0 else cr.line_to)(*p)
    cr.close_path()
    cr.stroke()
    # montanhas
    cr.set_source_rgb(0.07, 0.01, 0.01)
    cr.move_to(0, hz)
    for i in range(0, 12):
        x = i * 21
        cr.line_to(x, hz - 14 - noise(i, 7, 2) * 40)
        cr.line_to(x + 10, hz - 4 - noise(i, 8, 2) * 12)
    cr.line_to(w, hz)
    cr.close_path()
    cr.fill()
    # lava
    _vgrad(cr, hz, h, [(0, (1.0, 0.50, 0.06)), (1, (0.55, 0.07, 0.02))])
    for i in range(7):
        yy = hz + 8 + i * 10
        cr.set_source_rgba(1.0, 0.85, 0.30, 0.45)
        cr.set_line_width(1.5)
        for x in range(0, w + 8, 8):
            yv = yy + math.sin(x * 0.09 + t * 2 + i) * 1.8
            (cr.move_to if x == 0 else cr.line_to)(x, yv)
        cr.stroke()
    # brasas subindo
    for i in range(16):
        sp = 14 + noise(i, 1, 1) * 18
        yy = h - ((t * sp + i * 41) % (h + 10))
        xx = (noise(i, 2, 1) * w + math.sin(t + i) * 6) % w
        rect(cr, xx, yy, 2, 2, (1.0, 0.65 - 0.4 * (yy / h), 0.1), 0.85 * (yy / h) + 0.1)
    cr.set_source_rgba(0.75, 0.08, 0.04, 0.95)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_mario(cr, w, h, t):
    _vgrad(cr, 0, h, [(0, (0.33, 0.55, 0.98)), (1, (0.62, 0.80, 1.0))])
    # nuvens
    for i, (cx0, cy, s) in enumerate(((20, 30, 1.0), (140, 20, 0.8), (90, 54, 0.6))):
        cx = (cx0 + t * (3 + i)) % (w + 60) - 30
        for dx, dy, rr in ((0, 0, 9), (10, -4, 11), (22, 0, 9), (11, 3, 9)):
            cr.arc(cx + dx * s, cy + dy * s, rr * s, 0, 2 * math.pi)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()
    # morros com olhinhos
    for hx, hy, rr in ((46, h - 24, 40), (186, h - 24, 30)):
        cr.arc(hx, hy, rr, math.pi, 2 * math.pi)
        cr.close_path()
        cr.set_source_rgb(0.20, 0.68, 0.22)
        cr.fill_preserve()
        cr.set_source_rgb(0.05, 0.30, 0.08)
        cr.set_line_width(1.5)
        cr.stroke()
        for ex in (-6, 6):
            rect(cr, hx + ex - 1.5, hy - rr * 0.55, 3, 8, (0.05, 0.2, 0.05))
    # cano
    px = w - 38
    rect(cr, px + 3, h - 52, 28, 52, (0.10, 0.62, 0.20))
    rect(cr, px, h - 66, 34, 16, (0.10, 0.62, 0.20))
    rect(cr, px + 3, h - 66, 5, 66, (0.45, 0.88, 0.40), 0.7)
    cr.set_source_rgb(0.03, 0.25, 0.06)
    cr.set_line_width(1.5)
    cr.rectangle(px + 3, h - 52, 28, 52)
    cr.rectangle(px, h - 66, 34, 16)
    cr.stroke()
    # bloco "?"
    by = 26 + math.sin(t * 2.2) * 2
    rect(cr, 20, by, 26, 26, (0.98, 0.72, 0.10))
    cr.set_source_rgb(0.45, 0.20, 0.02)
    cr.set_line_width(2)
    cr.rectangle(20, by, 26, 26)
    cr.stroke()
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(18)
    cr.move_to(27, by + 20)
    cr.show_text("?")
    # chão de tijolos
    gy = h - 22
    rect(cr, 0, gy, w, 22, (0.78, 0.36, 0.10))
    cr.set_source_rgb(0.35, 0.12, 0.02)
    cr.set_line_width(1.5)
    for r_i in range(2):
        yy = gy + r_i * 11
        cr.move_to(0, yy)
        cr.line_to(w, yy)
        for x in range((r_i % 2) * 12, w + 24, 24):
            cr.move_to(x, yy)
            cr.line_to(x, yy + 11)
    cr.stroke()
    cr.set_source_rgb(0.95, 0.35, 0.30)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_creeper(cr, w, h, t):
    _vgrad(cr, 0, h, [(0, (0.45, 0.72, 0.98)), (1, (0.72, 0.88, 1.0))])
    rect(cr, w - 48, 16, 20, 20, (1.0, 0.95, 0.45))                      # sol quadrado
    for i, (cx0, cy) in enumerate(((10, 24), (110, 44), (60, 12))):      # nuvens de blocos
        cx = (cx0 + t * (4 + 2 * i)) % (w + 64) - 32
        for dx, dy, ww in ((8, 0, 32), (0, 8, 48), (16, -8, 16)):
            rect(cr, round((cx + dx) / 8) * 8, cy + dy, ww, 8, (1, 1, 1), 0.92)
    # árvore de blocos
    rect(cr, 28, h - 74, 8, 40, (0.42, 0.28, 0.14))
    for dx, dy in ((-8, -86), (0, -86), (8, -86), (-16, -78), (-8, -78), (0, -78), (8, -78), (16, -78),
                   (-8, -70), (0, -70), (8, -70), (-16, -70), (16, -70)):
        n = noise(dx, dy, 4)
        rect(cr, 32 + dx - 0, h + dy, 8, 8, (0.18 + 0.1 * n, 0.52 + 0.12 * n, 0.16))
    # grama e terra
    gy = h - 34
    for x in range(0, w + 8, 8):
        rect(cr, x, gy, 8, 8, (0.30 + 0.06 * noise(x, 1, 6), 0.62 + 0.06 * noise(x, 2, 6), 0.20))
        for y in range(gy + 8, h, 8):
            n = noise(x, y, 7)
            rect(cr, x, y, 8, 8, (0.50 + 0.10 * n, 0.34 + 0.08 * n, 0.21 + 0.05 * n))
    cr.set_source_rgba(0.12, 0.30, 0.08, 0.9)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_classic(cr, w, h, t):
    _vgrad(cr, 0, h, [(0, (1.0, 0.93, 0.86)), (1, (0.98, 0.80, 0.68))])
    for i in range(10):                                                  # bolinhas subindo devagar
        x = noise(i, 1, 2) * w
        y = h - ((t * (6 + noise(i, 2, 2) * 8) + i * 29) % (h + 10))
        cr.arc(x, y, 2 + noise(i, 3, 2) * 3, 0, 2 * math.pi)
        cr.set_source_rgba(1, 1, 1, 0.45)
        cr.fill()
    rect(cr, 0, h - 26, w, 26, (0.84, 0.47, 0.34), 0.55)
    cr.set_source_rgba(0.84, 0.47, 0.34, 1)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_pikachu(cr, w, h, t):
    _vgrad(cr, 0, h, [(0, (0.40, 0.70, 0.98)), (1, (0.80, 0.93, 1.0))])
    for i, (cx0, cy) in enumerate(((20, 28), (130, 18))):
        cx = (cx0 + t * (3 + i)) % (w + 60) - 30
        for dx, dy, rr in ((0, 0, 9), (11, -4, 11), (23, 0, 9)):
            cr.arc(cx + dx, cy + dy, rr, 0, 2 * math.pi)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()
    cr.set_source_rgb(0.36, 0.72, 0.30)
    cr.arc(60, h - 20, 70, math.pi, 2 * math.pi)
    cr.fill()
    cr.set_source_rgb(0.28, 0.62, 0.24)
    cr.arc(190, h - 14, 56, math.pi, 2 * math.pi)
    cr.fill()
    rect(cr, 0, h - 30, w, 30, (0.30, 0.66, 0.26))
    cr.set_source_rgb(0.18, 0.46, 0.14)
    cr.set_line_width(1.6)
    for i in range(14):                                                  # tufos de grama
        x = noise(i, 1, 3) * w
        y = h - 22 + noise(i, 2, 3) * 18
        for d in (-3, 0, 3):
            cr.move_to(x, y)
            cr.line_to(x + d, y - 6)
    cr.stroke()
    # Poké Bola
    bx, by = w - 30, h - 24
    cr.arc(bx, by, 11, math.pi, 2 * math.pi)
    cr.set_source_rgb(0.90, 0.15, 0.15)
    cr.fill()
    cr.arc(bx, by, 11, 0, math.pi)
    cr.set_source_rgb(0.97, 0.97, 0.97)
    cr.fill()
    cr.set_source_rgb(0.1, 0.1, 0.12)
    cr.set_line_width(1.6)
    cr.arc(bx, by, 11, 0, 2 * math.pi)
    cr.move_to(bx - 11, by)
    cr.line_to(bx + 11, by)
    cr.stroke()
    cr.arc(bx, by, 3.2, 0, 2 * math.pi)
    cr.set_source_rgb(1, 1, 1)
    cr.fill_preserve()
    cr.set_source_rgb(0.1, 0.1, 0.12)
    cr.stroke()
    cr.set_source_rgba(0.98, 0.78, 0.12, 0.95)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_sonic(cr, w, h, t):
    _vgrad(cr, 0, h, [(0, (0.20, 0.50, 0.98)), (1, (0.65, 0.88, 1.0))])
    # montanhas ao fundo
    cr.set_source_rgb(0.30, 0.55, 0.78)
    cr.move_to(0, h - 40)
    for x, y in ((40, 100), (90, 140), (150, 90), (200, 135), (w, 110)):
        cr.line_to(x, y)
    cr.line_to(w, h - 40)
    cr.close_path()
    cr.fill()
    # palmeiras
    _palm(cr, 26, h - 30, 32, 80, 24, t, 3, (0.10, 0.45, 0.16))
    _palm(cr, w - 26, h - 30, w - 34, 90, 22, t, 6, (0.10, 0.45, 0.16))
    # grama e terra xadrez
    gy = h - 40
    rect(cr, 0, gy, w, 8, (0.20, 0.72, 0.20))
    for x in range(0, w + 16, 16):
        for j, y in enumerate(range(gy + 8, h, 16)):
            col = (0.55, 0.30, 0.10) if (x // 16 + j) % 2 == 0 else (0.80, 0.50, 0.20)
            rect(cr, x, y, 16, 16, col)
    # anéis dourados
    for i, (rx, ry) in enumerate(((52, 54), (178, 48), (200, 80))):
        yy = ry + math.sin(t * 2.4 + i) * 3
        sx = max(0.25, abs(math.cos(t * 3 + i)))
        cr.save()
        cr.translate(rx, yy)
        cr.scale(sx, 1)
        cr.arc(0, 0, 8, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgb(0.98, 0.78, 0.10)
        cr.set_line_width(3.2)
        cr.stroke()
    cr.set_source_rgba(0.12, 0.30, 0.85, 0.95)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


def _scene_amongus(cr, w, h, t):
    _vgrad(cr, 0, h, [(0, (0.02, 0.02, 0.10)), (1, (0.08, 0.06, 0.20))])
    for i in range(40):                                                  # estrelas andando para a esquerda
        sp = 3 + noise(i, 1, 4) * 12
        x = (noise(i, 2, 4) * w - t * sp) % w
        y = noise(i, 3, 4) * (h - 40)
        rect(cr, x, y, 1.5 if sp < 9 else 2.2, 1.5, (1, 1, 1), 0.4 + 0.6 * noise(i, 4, 4))
    # planeta com anel
    cx, cy = 176, 52
    cr.arc(cx, cy, 24, 0, 2 * math.pi)
    g = cairo.RadialGradient(cx - 8, cy - 8, 3, cx, cy, 26)
    g.add_color_stop_rgb(0, 0.95, 0.45, 0.35)
    g.add_color_stop_rgb(1, 0.45, 0.10, 0.25)
    cr.set_source(g)
    cr.fill()
    cr.save()
    cr.translate(cx, cy)
    cr.scale(1, 0.28)
    cr.rotate(-0.25)
    cr.arc(0, 0, 38, 0, 2 * math.pi)
    cr.restore()
    cr.set_source_rgba(0.85, 0.75, 0.95, 0.65)
    cr.set_line_width(2.2)
    cr.stroke()
    # piso da nave
    gy = h - 30
    rect(cr, 0, gy, w, 30, (0.34, 0.37, 0.42))
    rect(cr, 0, gy, w, 4, (0.55, 0.60, 0.66))
    cr.set_source_rgba(0.10, 0.12, 0.16, 0.9)
    cr.set_line_width(1.5)
    for x in range(0, w + 30, 30):
        cr.move_to(x, gy + 4)
        cr.line_to(x - 8, h)
    cr.stroke()
    for i in range(6):
        on = int(t * 1.5 + i) % 2 == 0
        rect(cr, 14 + i * 38, gy + 12, 8, 4, (0.2, 1.0, 0.4) if on else (0.1, 0.3, 0.15))
    cr.set_source_rgba(0.60, 0.80, 0.95, 0.9)
    cr.set_line_width(2)
    rrect(cr, 1, 1, w - 2, h - 2, 18)
    cr.stroke()


_SCENE = {"none": _scene_classic, "gta6": _scene_gta6, "doom": _scene_doom, "mario": _scene_mario,
          "creeper": _scene_creeper, "steve": _scene_creeper, "pikachu": _scene_pikachu,
          "sonic": _scene_sonic, "amongus": _scene_amongus}
