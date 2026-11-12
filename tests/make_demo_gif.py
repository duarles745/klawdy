"""Render docs/klawdy-<lang>.gif from the real drawing code (no screen needed).

    python3 tests/make_demo_gif.py en|pt
"""
import os
import sys
import tempfile
import types

for var in ("HOME", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[var] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import cairo  # noqa: E402
from PIL import Image  # noqa: E402

from klawdy import i18n, painter, palette, skills  # noqa: E402
from klawdy.i18n import _  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
i18n._lang[0] = LANG
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", f"klawdy-{LANG}.gif")
CW, CH, FPS = 380, 330, 12
SCALE = 1.25
clock = [1000.0]
painter.time = types.SimpleNamespace(time=lambda: clock[0])


class K(painter.Painter):
    pass


k = K()
k.scale, k.t0, k.last_active, k._next_blink = SCALE, 1000.0, 1000.0, 1e12
k.costume, k.scenery, k.voice, k.mic_hover, k.mic_pressed_at = "none", False, None, False, 0

SAMPLE_ANSWER = {"pt": ["Sua pasta Downloads tem 12 arquivos:", "3 PDFs, 5 imagens e 4 instaladores."],
                 "en": ["Your Downloads folder has 12 files:", "3 PDFs, 5 images and 4 installers."]}
SCENES = [  # (seconds, state, skill, bubble lines)
    (1.6, "idle", "", None),
    (2.2, "working", "", [_("Trabalhando") + "…", "Refactor auth module · Bash"]),
    (1.6, "attention", "", [_("Precisa de você!"), "Refactor auth module"]),
    (1.6, "done", "", [_("Pronto!"), "Refactor auth module"]),
    (2.4, "working", "engineering:code-review", [_("Em batalha") + "…", "skill: code-review", "api · Review PR"]),
    (2.4, "idle", "", [_("Resposta:"), *SAMPLE_ANSWER[LANG], _("→ clique aqui para ver tudo")]),
]


def background(cr):
    g = cairo.LinearGradient(0, 0, 0, CH)
    g.add_color_stop_rgb(0, 0.16, 0.18, 0.27)
    g.add_color_stop_rgb(1, 0.27, 0.22, 0.33)
    cr.set_source(g)
    cr.paint()


frames = []
for secs, st, skill, lines in SCENES:
    for _i in range(int(secs * FPS)):
        clock[0] += 1 / FPS
        k.state, k.gear = st, skills.skill_gear(skill, custom={})
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, CW, CH)
        cr = cairo.Context(surf)
        background(cr)
        sprite = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(painter.W * SCALE), int(painter.H * SCALE))
        k.paint(cairo.Context(sprite), with_mic=True)
        x0, y0 = (CW - painter.W * SCALE) / 2, CH - painter.H * SCALE - 6
        cr.set_source_surface(sprite, x0, y0)
        cr.paint()
        if lines:
            kk = 1.0
            bw, bh = painter.bubble_size(lines, kk)
            ax = x0 + painter.BODY_CX * SCALE
            top = y0 + (painter.BODY_CY - 2.5 * painter.PH - 84) * SCALE
            bx = max(6, min(CW - bw - 6, ax - bw / 2))
            painter.paint_bubble(cr, lines, bx, top - bh - 10, bw, bh, kk, ax - bx, 10,
                                 clickable=lines[0] == _("Resposta:"))
        img = Image.frombuffer("RGBA", (CW, CH), bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB")
        frames.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))

palette.set_color_theme("orange")
frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=int(1000 / FPS), loop=0, optimize=True)
print(OUT, len(frames), "frames", os.path.getsize(OUT) // 1024, "KB")
