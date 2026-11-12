import time
import unittest

try:
    import cairo
except ImportError:  # pragma: no cover
    cairo = None


@unittest.skipIf(cairo is None, "pycairo not installed")
class PainterTest(unittest.TestCase):
    def test_every_state_and_costume_renders(self):
        from klawdy import painter, themes

        class K(painter.Painter):
            pass
        for costume in [c[0] for c in themes.COSTUMES]:
            for st, gear in (("idle", set()), ("working", {"helmet", "sword", "shield"}), ("attention", set()),
                             ("done", {"helmet"})):
                k = K()
                k.scale, k.state, k.t0, k.last_active = 1.0, st, time.time() - 0.3, time.time()
                k._next_blink, k.gear, k.costume, k.scenery = time.time() + 9, gear, costume, True
                k.voice, k.mic_hover, k.mic_pressed_at = None, False, 0
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, painter.W, painter.H)
                k.paint(cairo.Context(surf))
                self.assertTrue(any(surf.get_data()), (costume, st))

    def test_six_legs(self):
        from klawdy import painter
        body, _eyes = painter.sprite(0.0, "idle")
        self.assertEqual(len([c for (c, r) in body if r == 4]), 6)
