"""The floating mascot window: state polling, mouse, menu."""
import json
import os
import subprocess
import textwrap
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo  # noqa: E402
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import actions, compat, config, i18n, palette, sessions, skills, themes  # noqa: E402
from .compat import short  # noqa: E402
from .i18n import _  # noqa: E402
from .painter import BODY_CX, BODY_CY, MIC_CX, MIC_CY, MIC_R, PH, H, Painter, W  # noqa: E402
from .ui_windows import AnswerWindow, Bubble, ask_text, confirm_chrome  # noqa: E402

SIZE_MIN, SIZE_MAX, SIZE_STEP = 100, 350, 10
LAYOUT = 2              # bump when the window geometry changes (fixes the saved position)
ANSWER_SECS = 30
FPS_ACTIVE, FPS_IDLE, FPS_SLEEP = 30, 10, 5
BUBBLE_GAP = 84          # px above the body: antennae (34) + attention hop (48)


def clamp_size(v):
    try:
        return int(max(SIZE_MIN, min(SIZE_MAX, v)))
    except (TypeError, ValueError):
        return W


def wrap(text, width=34, max_lines=6):
    lines = []
    for para in text.strip().splitlines():
        para = para.strip()
        if para:
            lines.extend(textwrap.wrap(para, width) or [""])
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1] + "…"
    return lines


class Mascot(Painter, Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Klawdy")
        self.set_decorated(False)
        self.set_resizable(False)
        self.costume = config.setting("costume")
        self.scenery = config.setting("scenery")
        self.size = clamp_size(config.setting("size"))
        self.scale = self.size / W
        self.set_size_request(*self.win_size())
        self.set_default_size(*self.win_size())
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.bubble = Bubble()
        self.bubble.on_click = self.expand_answer
        self.answer_win = None
        self.settings_win = None
        self.stick()
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)

        self.area = Gtk.DrawingArea()
        self.add(self.area)
        self.area.connect("draw", lambda _w, cr: self.paint(cr) or False)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("leave-notify-event", lambda *_: setattr(self, "mic_hover", False))
        self.connect("scroll-event", self.on_scroll)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("configure-event", self.on_configure)
        self.connect("realize", lambda *_: self.apply_input_shape())
        self.connect("destroy", self.on_destroy)

        self.t0 = time.time()
        self.state = "idle"
        self.real_state = "idle"
        self.sessions = []
        self.last_active = time.time()
        self.show_details = False
        self.press = None
        self._save_id = None
        self._click_id = None
        self._flash = None
        self._next_blink = time.time() + 3
        self.answer = None
        self.mic_hover = False
        self.mic_pressed_at = 0.0
        self.voice = None
        self.skill = ""
        self.gear = set()
        self._answer_mtime = self.answer_mtime()
        self._fps = 0

        self.restore_position()
        self.poll()
        self.schedule_tick()
        GLib.timeout_add(300, self.poll)

    # ---------- frame rate: smooth when something happens, cheap when idle ----------
    def wanted_fps(self):
        if (self.state != "idle" or self.voice_active() or self.mic_hover or self.answer
                or palette.color_key() == "rainbow" or time.time() - self.mic_pressed_at < 4):
            return FPS_ACTIVE
        return FPS_SLEEP if self.sleeping() else FPS_IDLE

    def schedule_tick(self):
        self._fps = self.wanted_fps()
        GLib.timeout_add(int(1000 / self._fps), self.tick)

    def tick(self):
        if palette.color_key() == "rainbow":
            palette.apply(time.time() - self.t0)
        self.area.queue_draw()
        self.update_bubble()
        if self.wanted_fps() != self._fps:
            self.schedule_tick()
            return False
        return True

    # ---------- position and size ----------
    def restore_position(self):
        try:
            with open(config.POS_FILE) as f:
                p = json.load(f)
            k = self.scale
            if p.get("layout", 1) < LAYOUT:          # keep the mascot at the same spot
                p["y"] = int(p["y"]) - round(30 * k)
            self.move(int(p["x"]), int(p["y"]))
        except Exception:
            disp = Gdk.Display.get_default()
            g = (disp.get_primary_monitor() or disp.get_monitor(0)).get_workarea()
            w, h = self.win_size()
            self.move(g.x + max(0, g.width - w - 30), g.y + max(0, g.height - h - 30))

    def win_size(self):
        return round(W * self.scale), round(H * self.scale)

    def set_size(self, size):
        size = clamp_size(size)
        if size == self.size:
            return
        oldw, oldh = self.win_size()
        x, y = self.get_position()
        self.size = size
        self.scale = size / W
        neww, newh = self.win_size()
        self.set_size_request(neww, newh)
        self.resize(neww, newh)
        self.move(int(x + (oldw - neww) / 2), int(y + oldh - newh))   # keep standing on the same spot
        self.apply_input_shape()
        config.set_setting("size", size)
        self.flash(_("Tamanho: {size}px", size=size), 1.5)

    def set_color(self, key):
        palette.set_color_theme(key)
        config.set_setting("color", key)
        name = next((n for k, n, *_r in themes.COLOR_THEMES if k == key), key)
        self.flash(_("Cor: {name}", name=_(name)), 1.5)

    def set_costume(self, key):
        self.costume = key
        config.set_setting("costume", key)
        name = next((n for k, n, *_r in themes.COSTUMES if k == key), key)
        self.flash(_("Fantasia: {name}", name=_(name)), 1.5)

    def set_scenery(self, on):
        self.scenery = on
        config.set_setting("scenery", on)
        self.flash(_("Cenário ligado") if on else _("Cenário removido"), 1.5)

    def on_scroll(self, _w, ev):
        d = 0
        if ev.direction == Gdk.ScrollDirection.UP:
            d = 1
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            d = -1
        elif ev.direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = ev.get_scroll_deltas()
            d = -1 if dy > 0 else (1 if dy < 0 else 0)
        if d:
            self.set_size(self.size + d * SIZE_STEP)
        return True

    def on_destroy(self, *_):
        self.bubble.destroy()
        Gtk.main_quit()

    def on_configure(self, *_):
        self.update_bubble()
        if self._save_id:
            GLib.source_remove(self._save_id)
        self._save_id = GLib.timeout_add(800, self.save_position)
        return False

    def save_position(self):
        self._save_id = None
        try:
            x, y = self.get_position()
            config.write_json(config.POS_FILE, {"x": x, "y": y, "layout": LAYOUT})
        except Exception:
            pass
        return False

    def apply_input_shape(self):
        """Only Klawdy and the mic button take clicks; the rest of the window lets them through."""
        k = self.scale
        region = cairo.Region(cairo.RectangleInt(round((BODY_CX - 85) * k), round((BODY_CY - 45) * k),
                                                 round(170 * k), round(90 * k)))
        m = MIC_R + 4
        region.union(cairo.RectangleInt(round((MIC_CX - m) * k), round((MIC_CY - m) * k),
                                        round(2 * m * k), round(2 * m * k)))
        self.input_shape_combine_region(region)

    # ---------- bubble (separate window following the mascot) ----------
    def update_bubble(self):
        lines = self.bubble_lines()
        if not lines:
            self.bubble.hide_bubble()
            return
        x, y = self.get_position()
        k = self.scale
        cx = x + BODY_CX * k
        disp = Gdk.Display.get_default()
        mon = disp.get_monitor_at_point(int(cx), int(y + BODY_CY * k)) or disp.get_monitor(0)
        g = mon.get_workarea()
        top = y + (BODY_CY - 2.5 * PH - BUBBLE_GAP) * k   # above the antennae, even mid-hop
        bottom = y + (BODY_CY + 2.5 * PH + 16) * k    # below the feet
        clickable = bool(self.answer) and lines is self.answer["lines"]
        self.bubble.show_bubble(lines, cx, top, bottom, g, max(0.85, min(1.4, k)), clickable)

    # ---------- state ----------
    @staticmethod
    def answer_mtime():
        try:
            return os.path.getmtime(config.ANSWER_FILE)
        except OSError:
            return 0

    def poll(self):
        now = time.time()
        sess = sessions.read_sessions(now)

        m = self.answer_mtime()                       # new answer from a background request?
        if m and m != self._answer_mtime:
            self._answer_mtime = m
            try:
                with open(config.ANSWER_FILE) as f:
                    a = json.load(f)
                head = _("Resposta:") if a.get("ok") else _("Ops, deu erro:")
                lines = [head] + wrap(a.get("answer", ""), 34, 5) + [_("→ clique aqui para ver tudo")]
                self.answer = dict(a, lines=lines, expires=now + ANSWER_SECS)
            except Exception:
                pass
        if self.answer and now >= self.answer["expires"]:
            self.answer = None                        # disappears by itself after 30 s

        new_state = sess[0]["eff"] if sess else "idle"
        if new_state != "idle":
            self.last_active = now
        if new_state == "attention" and self.real_state != "attention":
            s = sess[0]
            actions.notify(_("Claude precisa de você"),
                           f"{self.proj(s)}: {s.get('message') or _('aguardando aprovação')}")
            actions.play_sound("atencao")
        elif new_state == "done" and self.real_state == "working" and not self.voice_active():
            actions.play_sound("pronto")
        self.real_state = new_state

        self.voice = sessions.read_voice(now)         # voice commands drive the animation
        if self.voice and self.voice["state"] == "listening":
            new_state, self.last_active = "attention", now
        elif self.voice and self.voice["state"] == "running":
            new_state, self.last_active = "working", now
        self.state = new_state
        self.sessions = sess
        armed = [x for x in sess if x.get("skill") and x["eff"] != "idle"]   # viking gear
        skill = armed[0]["skill"] if armed else ""
        if skill and skill != self.skill:
            actions.play_sound("entendi")
        self.skill = skill
        self.gear = skills.skill_gear(skill)
        return True

    def voice_active(self):
        return bool(self.voice and self.voice.get("state") in ("listening", "running"))

    @staticmethod
    def proj(s):
        return s.get("name") or os.path.basename(s.get("cwd") or "") or "~"

    def bubble_lines(self):
        now = time.time()
        dots = "." * (1 + int(now * 2) % 3)
        if self._flash and now < self._flash[1]:
            return self._flash[0].split("\n")
        if self.show_details:
            if not self.sessions:
                return [_("Nenhuma sessão aberta."), _("Duplo clique: novo Claude"), _("Ctrl+. : perguntar algo")]
            return [f"• {self.proj(s)}: {sessions.state_label(s['eff'])}" for s in self.sessions[:5]]
        v = self.voice
        if v and v.get("state") == "listening":
            return [_("Ouvindo") + dots, _("fale o que deseja")]
        if v and v.get("state") == "running":
            return [_("Entendi! Executando") + dots] + wrap(f"“{v.get('text', '')}”", 34, 3)
        if self.answer:
            return self.answer["lines"]
        s = self.sessions[0] if self.sessions else {}
        if self.state == "attention":
            return [_("Precisa de você!"), self.proj(s)]
        if self.state == "working":
            if self.skill:
                return [_("Em batalha") + dots, f"skill: {self.skill}", self.proj(s)]
            tool = s.get("tool")
            return [_("Trabalhando") + dots, self.proj(s) + (f" · {tool}" if tool else "")]
        if self.state == "done":
            return [_("Pronto!"), self.proj(s)]
        return None

    def flash(self, text, secs=4):
        self._flash = (text, time.time() + secs)

    # ---------- mouse ----------
    def on_mic(self, ev):
        x, y = ev.x / self.scale, ev.y / self.scale
        return (x - MIC_CX) ** 2 + (y - MIC_CY) ** 2 <= (MIC_R + 4) ** 2

    def mic_click(self):
        if not actions.voice_installed():
            self.flash(_("Comando de voz não instalado\n(rode o instalador com --voice)"), 4)
            return
        os.makedirs(config.STATE_DIR, exist_ok=True)
        with open(config.TRIGGER_FILE, "w") as f:
            f.write(str(time.time()))
        self.mic_pressed_at = time.time()
        actions.start_voice()                         # make sure the recogniser is running

    def on_press(self, _w, ev):
        if ev.button == 1 and self.on_mic(ev):
            self.press = None
            if ev.type == Gdk.EventType.BUTTON_PRESS:
                self.mic_click()
            return True
        if ev.button == 1:
            if ev.type == Gdk.EventType._2BUTTON_PRESS:
                self.press = None
                if self._click_id:
                    GLib.source_remove(self._click_id)
                    self._click_id = None
                actions.launch_claude()
                return True
            self.press = (ev.x_root, ev.y_root, ev.time)
        elif ev.button == 3:
            self.popup_menu(ev)
        return True

    def on_motion(self, _w, ev):
        hover = self.on_mic(ev)
        if hover != self.mic_hover:
            self.mic_hover = hover
            if hover and self._fps != FPS_ACTIVE:
                self.schedule_tick()
        if self.press and (ev.state & Gdk.ModifierType.BUTTON1_MASK):
            dx, dy = ev.x_root - self.press[0], ev.y_root - self.press[1]
            if dx * dx + dy * dy > 25:
                self.begin_move_drag(1, int(self.press[0]), int(self.press[1]), self.press[2])
                self.press = None
        return True

    def on_release(self, _w, ev):
        if ev.button == 1 and self.press:
            self.press = None
            if self._click_id:
                GLib.source_remove(self._click_id)
            delay = Gtk.Settings.get_default().get_property("gtk-double-click-time")
            self._click_id = GLib.timeout_add(delay + 20, self.single_click)
        return True

    def single_click(self):
        self._click_id = None
        if self.answer:
            self.answer = None                        # clicking Klawdy closes the answer bubble
            return False
        with_tty = [s for s in self.sessions if s.get("tty")]
        if with_tty:
            self.focus_session(with_tty[0])
        else:
            self.show_details = not self.show_details
        return False

    def focus_session(self, s):
        if not s.get("tty"):
            self.open_history(s)                      # background session: open its history
            return
        if not s.get("tag"):
            self.flash(_("Sessão antiga: reinicie o Claude\npara poder ir até ela"))
            return
        ok = actions.shell_call("Activate", s["tag"])
        if ok is None:
            self.flash(_("Extensão do GNOME inativa\n(faça logout/login e ative)"))
        elif not ok:
            self.flash(_("Janela de {name} não encontrada\n(está em outra aba?)", name=self.proj(s)))

    # ---------- history / names ----------
    def open_history(self, s):
        """Open the conversation in a new terminal; a copy if it is still in use elsewhere."""
        sid = s["sid"]
        cwd = compat.transcript_info(sessions.transcript_path(sid))[0] or s.get("cwd")
        busy = bool(s.get("tty")) or s.get("eff") == "working"
        actions.launch_claude(resume=sid, cwd=cwd, fork=busy)
        if busy:
            self.flash(_("Conversa em uso: abri uma cópia\ncom todo o histórico"), 5)

    def rename_session(self, s):
        name = ask_text(None, _("Renomear conversa"),
                        _("Nome desta conversa (deixe vazio para o automático):"),
                        sessions.load_names().get(s["sid"]) or s.get("name", ""))
        if name is not None:
            sessions.save_name(s["sid"], name)
            self.flash(_("Renomeada: {name}", name=name or _("automático")), 3)

    def reset_prompt_pos(self):
        st = config.load_settings()
        st.pop("prompt_pos", None)
        config.save_settings(st)
        self.flash(_("Caixa de texto volta a abrir\njunto ao Klawdy"), 3)

    # ---------- full answer ----------
    def expand_answer(self, last=False):
        data = self.answer
        if data is None or last:
            try:
                with open(config.ANSWER_FILE) as f:
                    data = json.load(f)
            except Exception:
                self.flash(_("Nenhuma resposta ainda"), 2)
                return
        self.answer = None
        if self.answer_win:
            self.answer_win.destroy()
        x, y = self.get_position()
        k = self.scale
        cx, top = x + BODY_CX * k, y + (BODY_CY - 2.5 * PH - BUBBLE_GAP) * k
        disp = Gdk.Display.get_default()
        mon = disp.get_monitor_at_point(int(cx), int(y + BODY_CY * k)) or disp.get_monitor(0)
        self.answer_win = AnswerWindow(data, cx, top, y + (BODY_CY + 60) * k, mon.get_workarea())
        self.answer_win.connect("destroy", lambda *_: setattr(self, "answer_win", None))

    # ---------- settings ----------
    def open_settings(self):
        from .ui_settings import SettingsWindow
        if self.settings_win:
            self.settings_win.present()
            return
        self.settings_win = SettingsWindow(self)
        self.settings_win.connect("destroy", lambda *_: setattr(self, "settings_win", None))

    def set_chrome(self, on, parent=None):
        if on and not confirm_chrome(parent):
            return False
        config.set_setting("chrome", on)
        self.flash(_("Chrome ligado") if on else _("Chrome desligado"), 2)
        return True

    def set_voice(self, on):
        if on and not actions.voice_installed():
            self.flash(_("Comando de voz não instalado\n(rode o instalador com --voice)"), 4)
            return False
        config.set_setting("voice", on)
        if on:
            actions.start_voice()
        self.flash(_("Comando de voz ligado") if on else _("Comando de voz desligado"), 2)
        return True

    def set_lang(self, lang):
        config.set_setting("lang", lang)
        i18n.reset()
        skills._cache[0] = 0
        self.flash(_("Idioma alterado"), 2)

    # ======================= menu =======================
    def popup_menu(self, ev):
        menu = Gtk.Menu()

        def add(parent, label, cb=None, sensitive=True):
            it = Gtk.MenuItem(label=label)
            if cb:
                it.connect("activate", cb)
            it.set_sensitive(sensitive and cb is not None)
            parent.append(it)
            return it

        def submenu(parent, label):
            it = Gtk.MenuItem(label=label)
            sub = Gtk.Menu()
            it.set_submenu(sub)
            parent.append(it)
            return sub

        def check(parent, label, active, cb):
            it = Gtk.CheckMenuItem(label=label)
            it.set_active(active)
            it.connect("toggled", cb)
            parent.append(it)
            return it

        add(menu, _("Perguntar ao Claude…  (Ctrl+.)"), lambda *_: actions.launch_prompt_popup())
        add(menu, _("Falar um pedido  (botão do microfone)"), lambda *_: self.mic_click())
        self.build_skill_menu(submenu(menu, _("⚔️ Usar uma skill")))
        if os.path.exists(config.ANSWER_FILE):
            add(menu, _("Ver última resposta"), lambda *_: self.expand_answer(last=True))
        menu.append(Gtk.SeparatorMenuItem())

        icons = {"attention": "🔔", "working": "⚙️", "done": "✅", "idle": "🟢"}
        for s in self.sessions[:8]:
            where = _("terminal") if s.get("tty") else _("segundo plano")
            sub = submenu(menu, f"{icons.get(s['eff'], '🟢')} {self.proj(s)}  "
                                f"({sessions.state_label(s['eff'])}, {where})")
            if s.get("tty"):
                add(sub, _("Ir para a janela do terminal"), lambda _i, s=s: self.focus_session(s))
            add(sub, _("Abrir histórico num terminal novo"), lambda _i, s=s: self.open_history(s))
            add(sub, _("Renomear…"), lambda _i, s=s: self.rename_session(s))
            add(sub, f"id {s['sid'][:8]} · {s.get('cwd') or '~'}")
        past = submenu(menu, _("🕘 Conversas anteriores (abrir no terminal)"))
        targets = [tg for tg in sessions.list_targets() if tg["kind"] == "past"]
        for tg in targets[:12]:
            label = tg["label"].lstrip("⭐ ").replace(_("Mais recente: "), "")
            add(past, label, lambda _i, tg=tg: actions.launch_claude(resume=tg["sid"], cwd=tg["cwd"]))
        if not targets:
            add(past, _("(nenhuma)"))
        menu.append(Gtk.SeparatorMenuItem())

        self.build_mcp_menu(submenu(menu, _("🔌 MCPs / conectores")))

        look = submenu(menu, _("🎨 Aparência"))
        size = submenu(look, _("Tamanho ({size}px)", size=self.size))
        for label, v in ((_("Pequeno"), 120), (_("Médio"), 180), (_("Padrão"), W), (_("Grande"), 290),
                         (_("Máximo"), SIZE_MAX)):
            add(size, f"{label} — {v}px" + ("  ✓" if v == self.size else ""), lambda _i, v=v: self.set_size(v))
        add(size, _("Dica: role a rodinha sobre o mascote"))
        colors = submenu(look, _("Tema de cor"))
        for key, name, emoji, _m, _s in themes.COLOR_THEMES:
            add(colors, f"{emoji}  {_(name)}" + ("  ✓" if key == palette.color_key() else ""),
                lambda _i, key=key: self.set_color(key))
        costumes = submenu(look, _("Fantasia (personagens)"))
        for key, name, emoji, *_r in themes.COSTUMES:
            add(costumes, f"{emoji}  {_(name)}" + ("  ✓" if key == self.costume else ""),
                lambda _i, key=key: self.set_costume(key))
        add(costumes, _("Personagens com cor própria ignoram o tema de cor (só os balões mudam)"))
        check(look, _("🖼️ Cenário de fundo"), self.scenery, lambda it: self.set_scenery(it.get_active()))

        vc = check(menu, _("Comando de voz (palavra de ativação)"), config.setting("voice"),
                   lambda it: self.set_voice(it.get_active()) or it.set_active(config.setting("voice")))
        vc.set_sensitive(actions.voice_installed())
        check(menu, _("Efeitos sonoros"), config.setting("sounds"),
              lambda it: config.set_setting("sounds", it.get_active()))
        check(menu, _("Falar as respostas em voz alta"), config.setting("speak"),
              lambda it: config.set_setting("speak", it.get_active()))
        box = submenu(menu, _("Caixa de texto (Ctrl+.)"))
        fixed = config.setting("prompt_pos") is not None
        add(box, _("Posição: onde você deixou  ✓") if fixed else _("Posição: junto ao Klawdy  ✓"))
        add(box, _("Voltar para junto do Klawdy"), lambda *_: self.reset_prompt_pos(), fixed)
        add(box, _("Dica: arraste a caixa pela borda para mudar o lugar"))
        menu.append(Gtk.SeparatorMenuItem())
        add(menu, _("⚙️ Configurações…"), lambda *_: self.open_settings())
        add(menu, _("Novo Claude"), lambda *_: actions.launch_claude())
        add(menu, _("Mostrar/esconder sessões"), lambda *_: setattr(self, "show_details", not self.show_details))
        add(menu, _("Sair"), lambda *_: Gtk.main_quit())
        menu.show_all()
        menu.popup_at_pointer(ev)

    GROUP_NAMES = {"anthropic-skills": "Suas skills (claude.ai)", "claude-code": "Do Claude Code",
                   "personal": "Pessoais (~/.claude/skills)"}

    def build_skill_menu(self, sub):
        """Choosing a skill opens the Ctrl+. box prepared for it."""
        def gear_icons(name):
            g = skills.skill_gear(name)
            return ("⚔️" if "sword" in g else "") + ("🛡️" if "shield" in g else "")

        def item(parent, s, label=None):
            it = Gtk.MenuItem(label=f"{label or s['name'].split(':', 1)[-1]}  {gear_icons(s['name'])}")
            if s["desc"]:
                it.set_tooltip_text(textwrap.shorten(s["desc"], 320, placeholder="…"))
            it.connect("activate", lambda *_: actions.launch_prompt_popup(s["name"]))
            parent.append(it)

        def child(parent, label):
            m = Gtk.Menu()
            it = Gtk.MenuItem(label=label)
            it.set_submenu(m)
            parent.append(it)
            return m

        def note(parent, label):
            it = Gtk.MenuItem(label=label)
            it.set_sensitive(False)
            parent.append(it)

        recent = [s for s in (skills.find_skill(n) for n in config.setting("recent_skills")) if s]
        if recent:
            note(sub, _("Usadas recentemente"))
            for s in recent:
                item(sub, s, s["name"])
            sub.append(Gtk.SeparatorMenuItem())
        groups = {}
        for s in skills.list_skills():
            groups.setdefault(s["group"], []).append(s)
        for g in sorted(groups, key=lambda g: (g != "claude-code", g != "anthropic-skills", g)):
            items = sorted(groups[g], key=lambda s: s["name"])
            label = _(self.GROUP_NAMES[g]) if g in self.GROUP_NAMES else g.replace("-", " ").title()
            gm = child(sub, f"{label}  ({len(items)})")
            if len(items) <= 24:
                for s in items:
                    item(gm, s)
                continue
            for i in range(0, len(items), 20):           # long lists in blocks of 20
                chunk = items[i:i + 20]
                a, b = chunk[0]["name"].split(":", 1)[-1], chunk[-1]["name"].split(":", 1)[-1]
                cm = child(gm, f"{a[:14]}  …  {b[:14]}")
                for s in chunk:
                    item(cm, s)
        sub.append(Gtk.SeparatorMenuItem())
        note(sub, _("⚔️ espada · 🛡️ escudo (o elmo vem sempre)"))

    # ---------- MCPs ----------
    _mcp_busy = False
    MCP_CACHE = os.path.join(config.CACHE_DIR, "mcp.json")

    def mcp_cached(self):
        try:
            with open(self.MCP_CACHE) as f:
                return json.load(f)
        except Exception:
            return {"time": 0, "servers": []}

    def refresh_mcp(self, announce=True):
        if Mascot._mcp_busy:
            return
        Mascot._mcp_busy = True
        if announce:
            self.flash(_("Verificando os MCPs…\n(leva uns segundos)"), 4)

        def work():
            servers = compat.mcp_list()
            if servers:
                config.write_json(self.MCP_CACHE, {"time": time.time(), "servers": servers})
            Mascot._mcp_busy = False
            if announce:
                n = sum(1 for x in servers if compat.mcp_status_kind(x["status"]) == "ok")
                GLib.idle_add(self.flash, _("MCPs atualizados:\n{n} conectados", n=n), 4)
        threading.Thread(target=work, daemon=True).start()

    def build_mcp_menu(self, sub):
        data = self.mcp_cached()
        if time.time() - data.get("time", 0) > 600:
            self.refresh_mcp(announce=not data["servers"])
        disabled = compat.mcp_disabled()

        def toggle_mcp(item, name):
            try:
                ok = compat.mcp_set_enabled(name, item.get_active())
            except Exception as ex:  # noqa: BLE001
                self.flash(_("Não consegui mudar:\n{err}", err=ex), 5)
                return
            if ok:
                self.flash(_("{name}: ligado", name=short(name, 30)) if item.get_active()
                           else _("{name}: desligado", name=short(name, 30)), 4)
            else:
                self.flash(_("Não consegui mudar {name}\n(veja o log)", name=short(name, 30)), 5)

        ch = Gtk.CheckMenuItem(label=_("🌐 Claude in Chrome (pedidos em segundo plano)"))
        ch.set_active(bool(config.setting("chrome")))

        def toggle_chrome(item):
            if not self.set_chrome(item.get_active()):
                item.handler_block_by_func(toggle_chrome)
                item.set_active(False)
                item.handler_unblock_by_func(toggle_chrome)
        ch.connect("toggled", toggle_chrome)
        sub.append(ch)
        sub.append(Gtk.SeparatorMenuItem())

        servers = {x["name"]: x["status"] for x in data.get("servers", [])}
        for name in disabled:
            servers.setdefault(name, "off")
        if not servers:
            it = Gtk.MenuItem(label=_("Carregando a lista… abra o menu de novo"))
            it.set_sensitive(False)
            sub.append(it)
        icons = {"ok": "✔", "auth": "🔑", "unconfigured": "–", "off": "⏸", "error": "✖"}
        needs_login = []
        for name in sorted(servers, key=lambda n: (not n.startswith("claude.ai"), n.lower())):
            kind = compat.mcp_status_kind(servers[name])
            extra = {"auth": _(" (precisa login)"), "unconfigured": _(" (não configurado)")}.get(kind, "")
            it = Gtk.CheckMenuItem(label=f"{icons[kind]} {name}{extra}")
            it.set_active(name not in disabled)
            it.connect("toggled", toggle_mcp, name)
            sub.append(it)
            if kind == "auth":
                needs_login.append(name)
        sub.append(Gtk.SeparatorMenuItem())
        if needs_login:
            login = Gtk.Menu()
            li = Gtk.MenuItem(label=_("🔑 Fazer login em…"))
            li.set_submenu(login)
            sub.append(li)
            for name in needs_login:
                it = Gtk.MenuItem(label=name)
                it.connect("activate", lambda _i, n=name: subprocess.Popen(
                    actions.terminal_cmd(["bash", "-lc", 'claude mcp login "$1"; exec bash', "x", n])))
                login.append(it)
        for label, cb in (
                (_("Gerenciar no terminal (/mcp)"), lambda *_: actions.launch_claude("/mcp")),
                (_("Adicionar um MCP novo…"), lambda *_: actions.launch_claude(
                    _("Quero adicionar um novo servidor MCP ao Claude Code. Pergunte qual serviço "
                      "eu quero conectar e configure com `claude mcp add` (escopo user)."))),
                (_("Atualizar status agora"), lambda *_: self.refresh_mcp())):
            it = Gtk.MenuItem(label=label)
            it.connect("activate", cb)
            sub.append(it)
        hint = Gtk.MenuItem(label=_("Ligar/desligar vale para conversas novas"))
        hint.set_sensitive(False)
        sub.append(hint)


def mascot_main():
    win = Mascot()
    win.show_all()
    Gtk.main()

