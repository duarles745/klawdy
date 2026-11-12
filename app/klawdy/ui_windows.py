"""Secondary windows: speech bubble, full answer, Ctrl+. prompt box, confirmations."""
import json
import os
import textwrap

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo  # noqa: E402
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import actions, config, palette, sessions, skills  # noqa: E402
from .compat import short  # noqa: E402
from .i18n import _  # noqa: E402
from .painter import BODY_CX, BODY_CY, W, bubble_size, paint_bubble  # noqa: E402


def rgba_window(win):
    win.set_app_paintable(True)
    visual = win.get_screen().get_rgba_visual()
    if visual is not None:
        win.set_visual(visual)


def add_css(win, css):
    prov = Gtk.CssProvider()
    prov.load_from_data(palette.themed_css(css))
    Gtk.StyleContext.add_provider_for_screen(win.get_screen(), prov,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


# ======================= speech bubble (follows the mascot) =======================
class Bubble(Gtk.Window):
    """Bubble that follows the mascot and always stays inside its monitor."""
    TAIL = 10
    PAD = 3

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        rgba_window(self)
        self.area = Gtk.DrawingArea()
        self.add(self.area)
        self.area.connect("draw", self.on_draw)
        self.connect("realize", lambda *_: self.input_shape_combine_region(cairo.Region()))
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_press)
        self.on_click = None
        self.clickable = False
        self.lines = None
        self.k = 1.0
        self.below = False
        self.tail_x = 0
        self.bw = self.bh = 0
        self.geom = None
        self.visible = False

    def on_press(self, _w, ev):
        if self.clickable and ev.button == 1 and self.on_click:
            self.on_click()
        return True

    def set_clickable(self, clickable):
        """Answer bubbles take clicks; the others let clicks through."""
        if clickable == self.clickable or not self.get_window():
            return
        self.clickable = clickable
        self.input_shape_combine_region(None if clickable else cairo.Region())
        cur = Gdk.Cursor.new_from_name(self.get_display(), "pointer") if clickable else None
        self.get_window().set_cursor(cur)

    def show_bubble(self, lines, anchor_x, top_y, bottom_y, g, k, clickable=False):
        if lines != self.lines or k != self.k:
            self.lines, self.k = list(lines), k
            self.bw, self.bh = bubble_size(self.lines, k)
            self.bw = min(self.bw, g.width - 16)
            self.area.queue_draw()
        total_w = self.bw + 2 * self.PAD
        total_h = self.bh + self.TAIL + 2 * self.PAD
        x = max(g.x + 4, min(g.x + g.width - total_w - 4, anchor_x - total_w / 2))
        y = top_y - total_h
        below = y < g.y + 4                       # no room above: go below
        if below:
            y = min(bottom_y, g.y + g.height - total_h - 4)
        r = 10 * k
        tail_x = max(r + 8, min(self.bw - r - 8, anchor_x - x - self.PAD))
        geom = (int(x), int(y), total_w, total_h)
        if below != self.below or abs(tail_x - self.tail_x) > 0.5:
            self.below, self.tail_x = below, tail_x
            self.area.queue_draw()
        if geom != self.geom:
            if self.geom is None or geom[2:] != self.geom[2:]:
                self.set_size_request(total_w, total_h)
                self.resize(total_w, total_h)
            self.move(geom[0], geom[1])
            self.geom = geom
        if not self.visible:
            self.show_all()
            self.visible = True
        self.set_clickable(clickable)

    def hide_bubble(self):
        if self.visible:
            self.set_clickable(False)
            self.hide()
            self.visible = False
            self.lines = None

    def on_draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self.lines:
            y = self.PAD + (self.TAIL if self.below else 0)
            paint_bubble(cr, self.lines, self.PAD, y, self.bw, self.bh, self.k, self.tail_x,
                         self.TAIL, self.below, self.clickable)
        return False


# ======================= full answer =======================
ANSWER_CSS = b"""
.answer { background-color: #ffffff; border: 3px solid #d77757; border-radius: 18px; padding: 12px 14px; }
.answer .title { color: #3a2418; font-weight: bold; font-size: 13px; }
.answer .asked { color: #8a6a5a; font-size: 11px; font-style: italic; }
.answer .body { color: #2a1a12; font-size: 13px; }
.answer button { border-radius: 10px; padding: 3px 10px; }
"""


class AnswerWindow(Gtk.Window):
    """The whole answer, scrollable. Stays open until closed (Esc or button)."""

    def __init__(self, data, anchor_x, top_y, bottom_y, g):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title(_("Resposta do Claude"))
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        rgba_window(self)
        add_css(self, ANSWER_CSS)
        self.text = data.get("answer", "")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("answer")
        head = _("Resposta do Claude") if data.get("ok", True) else _("Ops, deu erro")
        title = Gtk.Label(label=head + "   ·   " + _("arraste pela borda para mover"), xalign=0)
        title.get_style_context().add_class("title")
        box.pack_start(title, False, False, 0)
        if data.get("prompt"):
            asked = Gtk.Label(label=f"“{short(' '.join(data['prompt'].split()), 110)}”", xalign=0)
            asked.set_line_wrap(True)
            asked.get_style_context().add_class("asked")
            box.pack_start(asked, False, False, 0)
        body = Gtk.Label(label=self.text, xalign=0, yalign=0)
        body.set_line_wrap(True)
        body.set_line_wrap_mode(2)        # Pango.WrapMode.WORD_CHAR
        body.set_selectable(True)
        body.set_max_width_chars(72)
        body.set_width_chars(min(72, max(30, len(self.text))))
        body.get_style_context().add_class("body")
        self.set_default_size(min(580, g.width - 40), -1)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_width(min(520, g.width - 60))
        scroll.set_max_content_height(int(g.height * 0.55))
        scroll.set_propagate_natural_height(True)
        scroll.add(body)
        box.pack_start(scroll, True, True, 0)
        btns = Gtk.Box(spacing=6)
        if data.get("sid"):
            b = Gtk.Button(label=_("Abrir conversa no terminal"))
            b.connect("clicked", lambda *_a: (actions.launch_claude(resume=data["sid"], cwd=data.get("cwd")),
                                              self.destroy()))
            btns.pack_start(b, False, False, 0)
        copy = Gtk.Button(label=_("Copiar"))
        copy.connect("clicked", self.on_copy)
        btns.pack_start(copy, False, False, 0)
        close = Gtk.Button(label=_("Fechar"))
        close.connect("clicked", lambda *_a: self.destroy())
        btns.pack_end(close, False, False, 0)
        box.pack_start(btns, False, False, 0)
        self.add(box)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_press)
        self.connect("key-press-event", self.on_key)
        self.show_all()
        w, h = self.get_size()
        x = max(g.x + 8, min(g.x + g.width - w - 8, int(anchor_x - w / 2)))
        y = int(top_y - h)
        if y < g.y + 8:
            y = int(min(bottom_y, g.y + g.height - h - 8))
        self.move(x, y)
        self.present()

    def on_press(self, _w, ev):
        if ev.button == 1:
            self.begin_move_drag(1, int(ev.x_root), int(ev.y_root), ev.time)
        return False

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def on_copy(self, btn):
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        cb.set_text(self.text, -1)
        cb.store()
        btn.set_label(_("Copiado ✓"))


# ======================= permission popup (background runs) =======================
PERM_CSS = b"""
.perm { background-color: #ffffff; border: 3px solid #d77757; border-radius: 18px; padding: 12px 14px; }
.perm .title { color: #3a2418; font-weight: bold; font-size: 13px; }
.perm .what { color: #3a2418; font-size: 13px; }
.perm .detail { color: #2a1a12; font-family: monospace; font-size: 12px;
                background-color: #fff8f4; border-radius: 8px; padding: 6px 8px; }
.perm .hint { color: #8a6a5a; font-size: 11px; }
.perm button { border-radius: 10px; padding: 4px 14px; }
.perm .allow { background-image: none; background-color: #d77757; color: #ffffff; font-weight: bold; }
"""


class PermissionWindow(Gtk.Window):
    """Approve / deny one tool call of a background run. Opens below the mascot.

    It never takes the keyboard focus by itself, so typing elsewhere can't approve anything."""

    def __init__(self, req, anchor_x, below_y, top_y, g, waiting=0, on_answer=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.req_id = req["id"]
        self.on_answer = on_answer
        self.set_title(_("Claude pede permissão"))
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_focus_on_map(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.stick()
        rgba_window(self)
        add_css(self, PERM_CSS)
        what, detail = sessions.perm_summary(req.get("tool"), req.get("input"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("perm")
        proj = os.path.basename(req.get("cwd") or "") or "~"
        title = Gtk.Label(label=f"🔐 {_('Claude pede permissão')} · {proj}", xalign=0)
        title.get_style_context().add_class("title")
        box.pack_start(title, False, False, 0)
        lw = Gtk.Label(label=what, xalign=0)
        lw.set_line_wrap(True)
        lw.get_style_context().add_class("what")
        box.pack_start(lw, False, False, 0)
        if detail:
            ld = Gtk.Label(label=detail, xalign=0)
            ld.set_line_wrap(True)
            ld.set_line_wrap_mode(2)        # Pango.WrapMode.WORD_CHAR
            ld.set_selectable(True)
            ld.set_max_width_chars(60)
            ld.get_style_context().add_class("detail")
            box.pack_start(ld, False, False, 0)
        hint = _("Sem resposta em alguns minutos, o pedido é recusado.")
        if waiting:
            hint += "  ·  " + _("mais {n} na fila", n=waiting)
        lh = Gtk.Label(label=hint, xalign=0)
        lh.set_line_wrap(True)
        lh.get_style_context().add_class("hint")
        box.pack_start(lh, False, False, 0)
        btns = Gtk.Box(spacing=6)
        deny = Gtk.Button(label=_("Recusar"))
        deny.connect("clicked", lambda *_a: self.answer(False))
        allow = Gtk.Button(label=_("Aprovar"))
        allow.get_style_context().add_class("allow")
        allow.connect("clicked", lambda *_a: self.answer(True))
        btns.pack_end(allow, False, False, 0)
        btns.pack_end(deny, False, False, 0)
        box.pack_start(btns, False, False, 0)
        self.add(box)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_press)
        self.connect("key-press-event", self.on_key)
        self.set_default_size(min(440, g.width - 40), -1)
        self.show_all()
        w, h = self.get_size()
        x = max(g.x + 8, min(g.x + g.width - w - 8, int(anchor_x - w / 2)))
        y = int(below_y)
        if y + h > g.y + g.height - 8:              # no room below the mascot: go above
            y = int(max(g.y + 8, top_y - h))
        self.move(x, y)

    def answer(self, allow):
        actions.answer_permission(self.req_id, allow)
        if self.on_answer:
            self.on_answer(self.req_id)
        self.destroy()

    def on_press(self, _w, ev):
        if ev.button == 1:
            self.begin_move_drag(1, int(ev.x_root), int(ev.y_root), ev.time)
        return False

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.answer(False)
            return True
        return False


# ======================= Ctrl+. prompt box =======================
PROMPT_CSS = b"""
window { background-color: transparent; }
.bubble { background-color: #ffffff; border: 3px solid #d77757; border-radius: 18px; padding: 12px 14px; }
.title { color: #3a2418; font-weight: bold; font-size: 13px; }
.hint { color: #8a6a5a; font-size: 11px; }
entry {
  min-width: 340px; min-height: 34px; font-size: 14px; border-radius: 10px;
  border: 2px solid #d77757; background-color: #fff8f4; color: #3a2418; box-shadow: none;
}
"""


class PromptPopup(Gtk.Window):
    def __init__(self, skill=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.skill = skill
        info = skills.find_skill(skill) if skill else None
        self.set_title(_("Perguntar ao Claude"))
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        rgba_window(self)
        add_css(self, PROMPT_CSS)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("bubble")
        if skill:
            g = skills.skill_gear(skill)
            icons = "🪖" + ("⚔️" if "sword" in g else "") + ("🛡️" if "shield" in g else "")
            title = Gtk.Label(label=f"{icons}  " + _("Usar a skill") + f"  /{skill}", xalign=0)
        else:
            title = Gtk.Label(label=_("O que o Claude deve fazer?"), xalign=0)
        title.get_style_context().add_class("title")
        box.pack_start(title, False, False, 0)
        if info and info["desc"]:
            desc = Gtk.Label(label=textwrap.shorten(info["desc"], 220, placeholder="…"), xalign=0)
            desc.set_line_wrap(True)
            desc.set_max_width_chars(58)
            desc.get_style_context().add_class("hint")
            box.pack_start(desc, False, False, 0)

        self.targets = sessions.list_targets()          # which conversation gets the message
        self.combo = Gtk.ComboBoxText()
        for tg in self.targets:
            self.combo.append_text(tg["label"])
        self.combo.set_active(0)
        self.combo.set_can_focus(False)
        box.pack_start(self.combo, False, False, 0)

        self.entry = Gtk.Entry()
        if skill:
            self.entry.set_placeholder_text((info or {}).get("hint") or _("o que ela deve fazer? (pode deixar vazio)"))
        else:
            self.entry.set_placeholder_text(_("ex.: resuma os arquivos da pasta Downloads"))
        box.pack_start(self.entry, False, False, 0)
        hint = Gtk.Label(label=_("Enter envia  ·  Esc cancela  ·  Ctrl+↑/↓ troca a conversa  ·  "
                                 "arraste a borda para mover"), xalign=0)
        hint.get_style_context().add_class("hint")
        box.pack_start(hint, False, False, 0)
        self.add(box)

        self.entry.connect("activate", self.on_send)
        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)
        self.dragged = False
        self._save_id = None
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_press)
        self.connect("configure-event", self.on_configure)
        self.place()

    def on_press(self, _w, ev):
        if ev.button == 1:
            self.dragged = True
            self.begin_move_drag(1, int(ev.x_root), int(ev.y_root), ev.time)
        return False

    def on_configure(self, *_a):
        if self.dragged:
            if self._save_id:
                GLib.source_remove(self._save_id)
            self._save_id = GLib.timeout_add(300, self.save_pos)
        return False

    def save_pos(self):
        self._save_id = None
        if self.dragged:
            x, y = self.get_position()
            config.set_setting("prompt_pos", {"x": x, "y": y})
        return False

    def place(self):
        pw, ph = 420, 150
        disp = Gdk.Display.get_default()
        monitors = [disp.get_monitor(i).get_workarea() for i in range(disp.get_n_monitors())]
        p = config.setting("prompt_pos")
        if p and any(g.x <= p["x"] + 40 < g.x + g.width and g.y <= p["y"] + 20 < g.y + g.height
                     for g in monitors):
            self.move(int(p["x"]), int(p["y"]))            # where you left it
            return
        g = (disp.get_primary_monitor() or disp.get_monitor(0)).get_workarea()
        try:
            with open(config.POS_FILE) as f:
                pos = json.load(f)
            k = max(100, min(350, config.setting("size"))) / W
            x = int(pos["x"] + BODY_CX * k - pw / 2)
            y = int(pos["y"] + (BODY_CY - 90) * k - ph)
        except Exception:
            x, y = g.x + g.width - pw - 40, g.y + g.height - 200 - ph - 20
        self.move(max(g.x + 8, min(x, g.x + g.width - pw - 8)), max(g.y + 8, y))

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.save_pos()
            self.destroy()
            return True
        if ev.state & Gdk.ModifierType.CONTROL_MASK and ev.keyval in (Gdk.KEY_Up, Gdk.KEY_Down):
            step = -1 if ev.keyval == Gdk.KEY_Up else 1
            self.combo.set_active((self.combo.get_active() + step) % len(self.targets))
            return True
        return False

    def on_send(self, *_a):
        text = self.entry.get_text().strip()
        tg = self.targets[max(0, self.combo.get_active())]
        self.save_pos()
        self.destroy()
        if self.skill:                       # "/skill request": Claude loads the skill
            skills.remember_skill(self.skill)
            text = f"/{self.skill} {text}".strip()
        if not text:
            return
        if tg["kind"] == "new_term":
            actions.launch_claude(text)
        elif tg["kind"] == "live":
            actions.spawn_self("--send", tg["tag"], tg["sid"], tg["cwd"], text)
        elif tg["kind"] == "past":
            actions.spawn_self("--run", "--resume", tg["sid"], "--cwd", tg["cwd"], "--", text)
        else:
            actions.spawn_self("--run", "--", text)


def prompt_main(skill=None):
    win = PromptPopup(skill)
    win.show_all()
    win.present()
    win.entry.grab_focus()
    Gtk.main()


# ======================= confirmations =======================
def confirm(parent, title, text, ok_label):
    d = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.WARNING,
                          buttons=Gtk.ButtonsType.NONE, text=title)
    d.format_secondary_text(text)
    d.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL, ok_label, Gtk.ResponseType.OK)
    d.set_default_response(Gtk.ResponseType.CANCEL)
    d.set_keep_above(True)
    d.present()
    resp = d.run()
    d.destroy()
    return resp == Gtk.ResponseType.OK


def confirm_chrome(parent=None):
    return confirm(parent, _("Ligar o Claude in Chrome nos pedidos em segundo plano?"),
                   _("Pedidos feitos pelo Ctrl+. em segundo plano e pelo comando de voz rodam sem "
                     "ninguém aprovar cada passo. Com o Chrome ligado, o Claude poderá navegar e clicar "
                     "no seu navegador, onde você está logado.\n\nUma página pode conter instruções "
                     "escondidas para o Claude (prompt injection). Só ligue se você entende o risco. "
                     "Conversas abertas no terminal continuam pedindo sua aprovação."),
                   _("Ligar mesmo assim"))


def confirm_voice_installs(parent=None):
    return confirm(parent, _("Deixar o comando de voz instalar programas?"),
                   _("Com isto ligado, um pedido como “instala o programa que acabei de baixar” "
                     "pode instalar .deb, .snap, Flatpak ou AppImage da pasta Downloads. O sistema "
                     "ainda pede a sua senha para .deb e .snap, mas um erro de reconhecimento de voz "
                     "pode chegar até esse pedido de senha: confira antes de digitá-la."),
                   _("Permitir"))


def ask_text(parent, title, label, value=""):
    d = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    d.set_keep_above(True)
    d.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL, _("Salvar"), Gtk.ResponseType.OK)
    d.set_default_response(Gtk.ResponseType.OK)
    e = Gtk.Entry()
    e.set_text(value)
    e.set_activates_default(True)
    e.set_width_chars(40)
    box = d.get_content_area()
    box.set_spacing(6)
    box.set_border_width(12)
    box.add(Gtk.Label(label=label, xalign=0))
    box.add(e)
    d.show_all()
    d.present()
    resp = d.run()
    text = e.get_text().strip()
    d.destroy()
    return text if resp == Gtk.ResponseType.OK else None
