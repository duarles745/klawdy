"""Drawing Klawdy (pixel art) with cairo only — no GTK, so it can be rendered off-screen
(tests, the README animation).

Klawdy: a pixel-art body with two arms, SIX legs and two antennae.
Grid: one "pixel" is PW x PH (8 x 16). Gear and antennae use 8 x 8 cells.
"""
import math
import time

import cairo

from . import palette as pal
from . import themes

W, H = 230, 200                    # base window size (scale 1.0)
BODY_CX, BODY_CY = 115, 135        # body centre (room above for antennae, helmet and sword)
PW, PH = 8, 16
MIC_CX, MIC_CY, MIC_R = 22, BODY_CY + 26, 14
SLEEP_AFTER = 120

BODY_ROWS = {r: range(3, 15) for r in range(4)}
LEGS_IDLE = [3, 5, 7, 10, 12, 14]
LEGS_WALK = ([3, 5, 7, 9, 11, 13], [4, 6, 8, 10, 12, 14])   # six legs stepping


def rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def ellipse(cr, x, y, rx, ry):
    cr.save()
    cr.translate(x, y)
    cr.scale(rx, ry)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()


def sprite(t, st):
    """(body cells, eye cells, eye kind) for the current frame, on the PW x PH grid."""
    body = {(c, r) for r, cols in BODY_ROWS.items() for c in cols}
    if st == "attention":
        ar = 0 if int(t * 7) % 2 == 0 else 1             # waving both arms
        arms = [(1, ar), (2, ar), (15, ar), (16, ar)]
    elif st == "working":
        l_up = int(t * 8) % 2 == 0                        # "typing": alternating arms
        arms = [(1, 1 if l_up else 2), (2, 1 if l_up else 2),
                (15, 2 if l_up else 1), (16, 2 if l_up else 1)]
    elif st == "done":
        up = int(t * 5) % 2 == 0                          # celebrating with one arm
        arms = [(1, 2), (2, 2), (15, 0 if up else 1), (16, 0 if up else 1)]
    else:
        arms = [(1, 2), (2, 2), (15, 2), (16, 2)]
    body.update(arms)
    if st in ("working", "attention"):
        legs = LEGS_WALK[int(t * 8) % 2]
    else:
        legs = LEGS_IDLE
    body.update((c, 4) for c in legs)
    if st == "working":
        dx = 1 if math.sin(t * 1.5) > 0 else 0            # looking sideways
        eyes = [(5 + dx, 1), (12 + dx, 1)]
    else:
        eyes = [(5, 1), (12, 1)]
    if st == "attention":
        eyes += [(5, 0), (12, 0)]                         # wide-open eyes
    return body, eyes


class Painter:
    """Mixin with Klawdy's drawing. Needs: scale, state, t0, last_active, _next_blink, gear,
    costume, scenery, voice, mic_hover, mic_pressed_at."""

    def sleeping(self):
        return self.state == "idle" and time.time() - self.last_active > SLEEP_AFTER

    def paint(self, cr, with_mic=True):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.scale(self.scale, self.scale)
        cr.set_antialias(cairo.ANTIALIAS_NONE)

        now = time.time()
        t = now - self.t0
        st = self.state
        sleeping = self.sleeping()
        if now > self._next_blink + 0.15:
            self._next_blink = now + 2.5 + (hash(int(now)) % 30) / 10
        blinking = self._next_blink <= now <= self._next_blink + 0.15
        eye_kind = "closed" if (sleeping or blinking) else ("happy" if st == "done" else "open")

        # hops in whole pixels to keep the retro look
        if st == "attention":
            dy = -round(abs(math.sin(t * 8)) * 3) * PH
        elif st == "done":
            dy = -round(abs(math.sin(t * 4)) * 1.5) * PH // 2
        elif st == "working":
            dy = -(int(t * 4) % 2) * 3
        else:
            dy = round(math.sin(t * (1.0 if sleeping else 1.8)) * 1.5) * 2
        ox = BODY_CX - 9 * PW              # column 0
        oy = BODY_CY - 2.5 * PH + dy       # row 0

        if self.scenery:
            themes.draw_scene(self.costume, cr, W, H, t)

        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        k = 1 + dy / 120
        ellipse(cr, BODY_CX, BODY_CY + 2.5 * PH + 10, 66 * k, 6 * k)
        cr.set_source_rgba(0, 0, 0, 0.18)
        cr.fill()
        if st == "attention":
            ellipse(cr, BODY_CX, BODY_CY + dy - 8, 108, 70)
            cr.set_source_rgba(*pal.ACCENT, 0.20 + 0.15 * math.sin(t * 8))
            cr.fill()
        cr.set_antialias(cairo.ANTIALIAS_NONE)

        body, eyes = sprite(t, st)
        main_c, shade_c = themes.costume_body(self.costume) or (pal.ACCENT, pal.ACCENT_SHADE)
        themes.set_accent_shade(shade_c)

        self.draw_antennae(cr, ox, oy, t, st, sleeping, main_c, shade_c)

        cr.set_source_rgba(*pal.OUT, 0.55)          # thin dark outline
        for (c, r) in body:
            cr.rectangle(ox + c * PW - 1.5, oy + r * PH - 1.5, PW + 3, PH + 3)
        cr.fill()
        cr.set_source_rgb(*main_c)
        for (c, r) in body:
            cr.rectangle(ox + c * PW, oy + r * PH, PW + 0.5, PH + 0.5)
        cr.fill()
        cr.set_source_rgb(*shade_c)                  # subtle volume at the bottom of each run
        for (c, r) in body:
            if (c, r + 1) not in body:
                cr.rectangle(ox + c * PW, oy + r * PH + PH - 3, PW + 0.5, 3)
        cr.fill()

        cr.set_source_rgb(*pal.EYE)
        for (c, r) in ([] if themes.costume_hides_eyes(self.costume) else eyes):
            x, y = ox + c * PW, oy + r * PH
            if eye_kind == "open":
                cr.rectangle(x, y, PW, PH)
            elif eye_kind == "closed":
                cr.rectangle(x - 1, y + PH * 0.55, PW + 2, PH * 0.3)
            else:  # happy: ^ ^
                cr.rectangle(x - 2, y + PH * 0.45, 3, PH * 0.3)
                cr.rectangle(x + PW - 1, y + PH * 0.45, 3, PH * 0.3)
                cr.rectangle(x + 1, y + PH * 0.2, PW - 2, PH * 0.3)
        cr.fill()

        gear = self.gear
        themes.draw_costume(self.costume, cr, ox, oy, body, st, t, eye_kind, gear)
        if gear:
            self.draw_gear(cr, ox, oy, body, gear, t)

        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        mark_x = ox - 3 * PW if "sword" in gear else ox + 17 * PW + 2
        if st == "working":                          # spinning ✻, like Claude Code's indicator
            glyphs = "·✢✳✶✻✽✻✶✳✢"
            cr.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(24)
            cr.set_source_rgb(*pal.ACCENT)
            cr.move_to(mark_x, oy + 6 - (2 * PH if "helmet" in gear else 0))
            cr.show_text(glyphs[int(t * 8) % len(glyphs)])
        if sleeping:
            self.draw_zzz(cr, t, ox + 16 * PW, oy)
        if with_mic:
            self.draw_mic(cr, t)
        if st == "attention":
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(30)
            cr.move_to(mark_x + 2, oy + 10)
            cr.set_source_rgb(*pal.ACCENT)
            cr.show_text("!")

    # ---------- antennae ----------
    def draw_antennae(self, cr, ox, oy, t, st, sleeping, main_c, shade_c):
        for side, col in ((-1, 5), (1, 12)):
            x = ox + col * PW + 2
            if sleeping:                             # drooping
                segs = [(0, -10), (side * 4, -16)]
                tip = (x + side * 9, oy - 18)
            else:
                wob = (2 if int(t * 6 + (side > 0)) % 2 else -2) if st == "working" else 0
                segs = [(0, -12), (side * 4, -24)]
                tip = (x + side * 4 + wob - 2, oy - 34)
            cr.set_source_rgba(*pal.OUT, 0.6)
            for (sx, sy) in segs:
                cr.rectangle(x + sx - 1.5, oy + sy - 1.5, 4 + 3, 12 + 3)
            cr.rectangle(tip[0] - 1.5, tip[1] - 1.5, 11, 11)
            cr.fill()
            cr.set_source_rgb(*main_c)
            for (sx, sy) in segs:
                cr.rectangle(x + sx, oy + sy, 4, 12.5)
            cr.fill()
            glow = st == "attention" and int(t * 8) % 2 == 0
            cr.set_source_rgb(*(pal.TIP_GLOW if glow else pal.lighter(main_c, 0.25)))
            cr.rectangle(tip[0], tip[1], 8, 8)
            cr.fill()
            cr.set_source_rgb(*shade_c)
            cr.rectangle(tip[0], tip[1] + 6, 8, 2)
            cr.fill()
            if glow:
                cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
                cr.arc(tip[0] + 4, tip[1] + 4, 9, 0, 2 * math.pi)
                cr.set_source_rgba(*pal.TIP_GLOW, 0.35)
                cr.fill()
                cr.set_antialias(cairo.ANTIALIAS_NONE)

    # ---------- viking gear (8 x 8 cells) ----------
    @staticmethod
    def _cells(cr, ox, oy, cells, rgb, outline=True):
        if outline:
            cr.set_source_rgba(*pal.OUT, 0.7)
            for (c, h) in cells:
                cr.rectangle(ox + c * 8 - 1.5, oy + h * 8 - 1.5, 11, 11)
            cr.fill()
        cr.set_source_rgb(*rgb)
        for (c, h) in cells:
            cr.rectangle(ox + c * 8, oy + h * 8, 8.5, 8.5)
        cr.fill()

    def draw_gear(self, cr, ox, oy, body, gear, t):
        if "helmet" in gear:
            horn = [(3, -1), (2, -1), (2, -2), (1, -2), (1, -3), (1, -4)]
            self._cells(cr, ox, oy, horn + [(17 - c, h) for c, h in horn], pal.HORN)
            self._cells(cr, ox, oy, [(1, -4), (16, -4)], pal.HORN_SHADE, outline=False)
            dome = ([(c, -1) for c in range(4, 14)] + [(c, -2) for c in range(5, 13)]
                    + [(c, -3) for c in range(7, 11)])
            self._cells(cr, ox, oy, dome, pal.STEEL)
            self._cells(cr, ox, oy, [(6, -2), (7, -3)], pal.STEEL_LIGHT, outline=False)
            cr.set_source_rgb(*pal.STEEL_DARK)
            cr.rectangle(ox + 4 * 8, oy - 4, 10 * 8, 4)
            cr.rectangle(ox + 8 * 8 + 2, oy - 3 * 8, 4, 3 * 8 - 4)
            cr.fill()
            cr.set_source_rgb(*pal.GOLD)
            for c in (5, 7, 10, 12):
                cr.rectangle(ox + c * 8 + 2, oy - 8 + 1, 3, 3)
            cr.fill()

        r_right = min((r for (c, r) in body if c == 16), default=2)
        r_left = min((r for (c, r) in body if c == 1), default=2)

        if "shield" in gear:                 # round viking shield on the left arm
            sx, sy, R = ox + 12, oy + r_left * PH + 10, 21
            cr.arc(sx, sy, R + 2, 0, 2 * math.pi)
            cr.set_source_rgb(*pal.OUT)
            cr.fill()
            for i in range(4):
                cr.move_to(sx, sy)
                cr.arc(sx, sy, R, i * math.pi / 2, (i + 1) * math.pi / 2)
                cr.close_path()
                cr.set_source_rgb(*(pal.SHIELD_RED if i % 2 == 0 else pal.SHIELD_CREAM))
                cr.fill()
            cr.set_line_width(3)
            cr.set_source_rgb(*pal.STEEL_DARK)
            cr.arc(sx, sy, R - 1, 0, 2 * math.pi)
            cr.stroke()
            cr.arc(sx, sy, 6, 0, 2 * math.pi)
            cr.set_source_rgb(*pal.STEEL)
            cr.fill_preserve()
            cr.set_source_rgb(*pal.STEEL_DARK)
            cr.set_line_width(1.5)
            cr.stroke()
            cr.rectangle(sx - 3, sy - 3, 2, 2)
            cr.set_source_rgb(*pal.STEEL_LIGHT)
            cr.fill()

        if "sword" in gear:                  # sword raised in the right hand
            hx, hy = ox + 16 * PW + 4, oy + r_right * PH + 8
            parts = [
                (hx - 3, hy - 46, 6, 40, pal.STEEL),        # blade
                (hx - 1, hy - 50, 2, 4, pal.STEEL),         # tip
                (hx - 3, hy - 46, 2, 40, pal.STEEL_LIGHT),  # shiny edge
                (hx - 10, hy - 8, 20, 4, pal.GOLD),         # guard
                (hx - 2, hy - 4, 4, 10, pal.WOOD),          # grip
                (hx - 3, hy + 6, 6, 4, pal.GOLD),           # pommel
            ]
            cr.set_source_rgba(*pal.OUT, 0.7)
            for x, y, w, h, _ in parts[:1] + parts[3:]:
                cr.rectangle(x - 1.5, y - 1.5, w + 3, h + 3)
            cr.rectangle(hx - 2.5, hy - 51.5, 5, 6)
            cr.fill()
            for x, y, w, h, rgb in parts:
                cr.set_source_rgb(*rgb)
                cr.rectangle(x, y, w, h)
                cr.fill()
            if self.state == "working":      # glint running along the blade
                ph = (t * 1.2) % 1.6
                if ph < 1:
                    cr.set_source_rgba(1, 1, 1, 0.85)
                    cr.rectangle(hx - 3, hy - 46 + ph * 34, 6, 6)
                    cr.fill()

    # ---------- microphone button and zzz ----------
    def draw_mic(self, cr, t):
        v = self.voice or {}
        vs = v.get("state")
        waiting = time.time() - self.mic_pressed_at < 4 and vs not in ("listening", "running")
        r = MIC_R + (1.5 if self.mic_hover else 0)
        cx, cy = MIC_CX, MIC_CY
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        if vs == "listening":
            for i in range(2):               # waves while listening
                ph = (t * 1.2 + i / 2) % 1
                cr.arc(cx, cy, r + 2 + ph * 12, 0, 2 * math.pi)
                cr.set_source_rgba(0.88, 0.25, 0.25, 0.55 * (1 - ph))
                cr.set_line_width(2)
                cr.stroke()
            bg, fg, ring = (0.88, 0.25, 0.25), (1, 1, 1), (0.55, 0.10, 0.10)
        elif vs == "running":
            bg, fg, ring = pal.ACCENT, (1, 1, 1), pal.ACCENT_SHADE
        else:
            bg, fg, ring = (1.0, 0.97, 0.94), (0.25, 0.16, 0.12), pal.ACCENT
        cr.arc(cx, cy + 2, r, 0, 2 * math.pi)
        cr.set_source_rgba(0, 0, 0, 0.22)
        cr.fill()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgb(*bg)
        cr.fill_preserve()
        cr.set_source_rgb(*ring)
        cr.set_line_width(2.2)
        cr.stroke()
        if vs == "running" or waiting:
            a = t * 6
            cr.arc(cx, cy, r + 3.5, a, a + 1.6)
            cr.set_source_rgb(*(pal.ACCENT if waiting else pal.ACCENT_SHADE))
            cr.set_line_width(2.4)
            cr.stroke()
        cr.set_source_rgb(*fg)
        rounded_rect(cr, cx - 3.6, cy - 8.5, 7.2, 11.5, 3.6)
        cr.fill()
        cr.set_line_width(1.8)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.arc(cx, cy - 1.5, 6.2, 0.05 * math.pi, 0.95 * math.pi)
        cr.stroke()
        cr.move_to(cx, cy + 4.7)
        cr.line_to(cx, cy + 8)
        cr.move_to(cx - 3.5, cy + 8.2)
        cr.line_to(cx + 3.5, cy + 8.2)
        cr.stroke()

    def draw_zzz(self, cr, t, x0, y0):
        cr.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        for i in range(3):
            phase = (t * 0.5 + i / 3) % 1
            cr.set_font_size(11 + 7 * phase)
            cr.set_source_rgba(*pal.ACCENT_SHADE, 1 - phase)
            cr.move_to(x0 + phase * 20, y0 - 4 - phase * 26)
            cr.show_text("z")


# ---------------------------------------------------------------- speech bubble (pure cairo)
def bubble_size(lines, k):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    cr = cairo.Context(surf)
    cr.set_font_size(12 * k)
    widths = []
    for i, line in enumerate(lines):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD if i == 0 else cairo.FONT_WEIGHT_NORMAL)
        widths.append(cr.text_extents(line).x_advance)
    return math.ceil(max(widths) + 22 * k), math.ceil((15 * len(lines) + 12) * k)


def paint_bubble(cr, lines, x, y, bw, bh, k, tail_x, tail=10, below=False, clickable=False):
    """Rounded speech bubble with a tail pointing down (or up if `below`)."""
    tx = x + tail_x
    r = 10 * k
    cr.new_sub_path()
    cr.arc(x + bw - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + bw - r, y + bh - r, r, 0, math.pi / 2)
    if not below:
        cr.line_to(tx + 8, y + bh)
        cr.line_to(tx, y + bh + tail - 1)
        cr.line_to(tx - 8, y + bh)
    cr.arc(x + r, y + bh - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    if below:
        cr.line_to(tx - 8, y)
        cr.line_to(tx, y - tail + 1)
        cr.line_to(tx + 8, y)
    cr.close_path()
    cr.set_source_rgb(1, 0.98, 0.96)
    cr.fill_preserve()
    cr.set_source_rgb(*pal.ACCENT)
    cr.set_line_width(2.6)
    cr.stroke()
    cr.set_source_rgb(*pal.OUT)
    cr.set_font_size(12 * k)
    lh = 15 * k
    cr.save()
    cr.rectangle(x, y, bw, bh)
    cr.clip()
    for i, line in enumerate(lines):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD if i == 0 else cairo.FONT_WEIGHT_NORMAL)
        if clickable and i == len(lines) - 1:
            cr.set_source_rgb(*pal.ACCENT_SHADE)
        cr.move_to(x + 11 * k, y + 6 * k + lh * (i + 1) - 3 * k)
        cr.show_text(line)
    cr.restore()
