"""Settings window (instead of editing config.json by hand)."""
import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import __version__, actions, compat, config, themes  # noqa: E402
from .i18n import _  # noqa: E402
from .ui_windows import confirm_voice_installs  # noqa: E402

TERMINALS = ["ptyxis", "gnome-terminal", "kgx", "konsole", "xfce4-terminal", "tilix", "kitty",
             "alacritty", "wezterm", "xterm"]


class SettingsWindow(Gtk.Window):
    def __init__(self, mascot):
        super().__init__(title=_("Configurações do Klawdy"))
        self.mascot = mascot
        self.set_default_size(560, 520)
        self.set_keep_above(True)
        self.set_border_width(10)
        nb = Gtk.Notebook()
        self.add(nb)
        nb.append_page(self.page_general(), Gtk.Label(label=_("Geral")))
        nb.append_page(self.page_voice(), Gtk.Label(label=_("Voz")))
        nb.append_page(self.page_security(), Gtk.Label(label=_("Segurança")))
        nb.append_page(self.page_about(), Gtk.Label(label=_("Sobre")))
        self.show_all()
        self.present()

    # ---------- helpers ----------
    @staticmethod
    def grid():
        g = Gtk.Grid(column_spacing=12, row_spacing=10, margin=14)
        g.row = 0
        return g

    @staticmethod
    def row(g, label, widget, hint=None):
        lab = Gtk.Label(label=label, xalign=0)
        lab.set_hexpand(True)
        g.attach(lab, 0, g.row, 1, 1)
        widget.set_halign(Gtk.Align.END)
        g.attach(widget, 1, g.row, 1, 1)
        g.row += 1
        if hint:
            h = Gtk.Label(xalign=0)
            h.set_markup(f"<small>{GLib.markup_escape_text(hint)}</small>")
            h.set_line_wrap(True)
            h.set_max_width_chars(70)
            g.attach(h, 0, g.row, 2, 1)
            g.row += 1

    @staticmethod
    def combo(options, current, on_change):
        c = Gtk.ComboBoxText()
        for key, label in options:
            c.append(str(key), label)
        c.set_active_id(str(current))
        c.connect("changed", lambda w: on_change(w.get_active_id()))
        return c

    @staticmethod
    def switch(active, on_change):
        s = Gtk.Switch()
        s.set_active(bool(active))
        s.connect("notify::active", lambda w, _p: on_change(w))
        return s

    @staticmethod
    def revert(sw, value, handler):
        sw.handler_block_by_func(handler)
        sw.set_active(value)
        sw.handler_unblock_by_func(handler)

    # ---------- pages ----------
    def page_general(self):
        g = self.grid()
        self.row(g, _("Idioma"), self.combo(
            [("auto", _("Automático (idioma do sistema)")), ("pt", "Português"), ("en", "English")],
            config.setting("lang"), self.mascot.set_lang), _("Menus e balões mudam na hora."))
        size = Gtk.SpinButton.new_with_range(100, 350, 10)
        size.set_value(self.mascot.size)
        size.connect("value-changed", lambda w: self.mascot.set_size(int(w.get_value())))
        self.row(g, _("Tamanho (px)"), size)
        self.row(g, _("Tema de cor"), self.combo([(k, f"{e} {_(n)}") for k, n, e, *_r in themes.COLOR_THEMES],
                                                 config.setting("color"), self.mascot.set_color))
        self.row(g, _("Fantasia"), self.combo([(k, f"{e} {_(n)}") for k, n, e, *_r in themes.COSTUMES],
                                              self.mascot.costume, self.mascot.set_costume))
        self.row(g, _("Cenário de fundo"), self.switch(self.mascot.scenery,
                                                       lambda w: self.mascot.set_scenery(w.get_active())))
        self.row(g, _("Efeitos sonoros"), self.switch(config.setting("sounds"),
                                                      lambda w: config.set_setting("sounds", w.get_active())))
        found = [t for t in TERMINALS if shutil.which(t)]
        self.row(g, _("Terminal"), self.combo([("", _("Automático"))] + [(t, t) for t in found],
                                              config.setting("terminal") or "",
                                              lambda v: config.set_setting("terminal", v or None)))
        return g

    def page_voice(self):
        g = self.grid()
        installed = actions.voice_installed()
        status = Gtk.Label(xalign=0)
        status.set_line_wrap(True)
        status.set_max_width_chars(70)
        status.set_markup(_("✔ Instalado (reconhecimento offline, nada sai do seu computador).") if installed
                          else _("Não instalado. Para instalar (~1 GB de modelos), rode o instalador com "
                                 "<b>--voice</b>."))
        g.attach(status, 0, g.row, 2, 1)
        g.row += 1

        def on_voice(w):
            if not self.mascot.set_voice(w.get_active()):
                self.revert(w, False, on_voice)
        sw = self.switch(config.setting("voice"), on_voice)
        sw.set_sensitive(installed)
        self.row(g, _("Ouvir a palavra de ativação o tempo todo"), sw,
                 _("Desligado, o botão de microfone ao lado do Klawdy continua funcionando e só "
                   "abre o microfone quando você clica."))
        words = Gtk.Entry()
        words.set_text(", ".join(config.setting("wake_words") or []))
        words.set_placeholder_text(_("padrão: Claudinho ou Klawdy"))
        words.connect("changed", lambda w: config.set_setting(
            "wake_words", [x.strip() for x in w.get_text().split(",") if x.strip()]))
        self.row(g, _("Palavras de ativação extras"), words,
                 _("Separadas por vírgula. Vale depois de reiniciar o Klawdy."))
        self.row(g, _("Falar as respostas em voz alta"), self.switch(
            config.setting("speak"), lambda w: config.set_setting("speak", w.get_active())))

        def on_installs(w):
            if w.get_active() and not confirm_voice_installs(self):
                self.revert(w, False, on_installs)
                return
            config.set_setting("voice_installs", w.get_active())
        self.row(g, _("Permitir que a voz instale programas"), self.switch(config.setting("voice_installs"),
                                                                           on_installs),
                 _("Desligado por padrão. Mesmo ligado, o sistema pede a sua senha para .deb e .snap."))
        return g

    def page_security(self):
        g = self.grid()
        intro = Gtk.Label(xalign=0)
        intro.set_line_wrap(True)
        intro.set_max_width_chars(70)
        intro.set_text(_("Conversas abertas no terminal sempre pedem a sua aprovação. Já os pedidos em "
                         "segundo plano (Ctrl+. com “Nova conversa em segundo plano”, conversas "
                         "anteriores e comando de voz) rodam sem ninguém aprovar cada passo, então o "
                         "Klawdy só libera para eles ferramentas que não mexem no seu sistema."))
        g.attach(intro, 0, g.row, 2, 1)
        g.row += 1

        def on_chrome(w):
            if not self.mascot.set_chrome(w.get_active(), self):
                self.revert(w, False, on_chrome)
        self.row(g, _("Claude in Chrome nos pedidos em segundo plano"), self.switch(config.setting("chrome"),
                                                                                    on_chrome),
                 _("Desligado por padrão: páginas da web podem conter instruções escondidas para o "
                   "Claude (prompt injection) e ele agiria no navegador onde você está logado."))
        lst = Gtk.Label(xalign=0)
        lst.set_line_wrap(True)
        lst.set_max_width_chars(70)
        lst.set_markup(_("<b>O que o Klawdy grava no seu computador</b>\n"
                         "• ~/.config/klawdy: configurações, nomes das conversas, posição\n"
                         "• ~/.cache/klawdy: última resposta, log, lista de MCPs\n"
                         "• $XDG_RUNTIME_DIR/klawdy: estado das sessões (apagado ao desligar)\n"
                         "• ~/.claude.json: só quando você liga/desliga um MCP pelo menu "
                         "(com backup diário em ~/.cache/klawdy)\n"
                         "Nada é enviado para a internet pelo Klawdy; a voz é reconhecida offline."))
        g.attach(lst, 0, g.row, 2, 1)
        g.row += 1
        return g

    def page_about(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=14)
        head = Gtk.Label(xalign=0)
        head.set_markup(f"<b>Klawdy {__version__}</b>\n" + GLib.markup_escape_text(
            _("Projeto não oficial da comunidade, sem vínculo com a Anthropic. Claude e Claude Code "
              "são marcas da Anthropic. Licença MIT.")))
        head.set_line_wrap(True)
        head.set_max_width_chars(70)
        box.pack_start(head, False, False, 0)
        title = Gtk.Label(xalign=0)
        title.set_markup("<b>" + GLib.markup_escape_text(_("Diagnóstico (compatibilidade com o Claude Code)"))
                         + "</b>")
        box.pack_start(title, False, False, 0)
        diag = Gtk.Label(label=_("Verificando…"), xalign=0, yalign=0)
        diag.set_selectable(True)
        diag.set_line_wrap(True)
        diag.set_max_width_chars(70)
        box.pack_start(diag, False, False, 0)

        def work():
            lines = [f"{'✔' if ok else '✖'} {name}: {detail}" for name, ok, detail in compat.diagnose()]
            GLib.idle_add(diag.set_text, "\n".join(lines))
        threading.Thread(target=work, daemon=True).start()
        btns = Gtk.Box(spacing=6)
        for label, path in ((_("Abrir log"), config.LOG_FILE), (_("Abrir pasta de configurações"), config.CONF_DIR)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, p=path: subprocess.Popen(["xdg-open", p]))
            btns.pack_start(b, False, False, 0)
        box.pack_start(btns, False, False, 0)
        return box
