// Klawdy GNOME Shell extension: finds the Claude Code terminal window by the tag in its title
// (set by hook.sh) and focuses it or types a message into it. D-Bus: org.klawdy.Klawdy
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const IFACE = `<node>
  <interface name="org.klawdy.Klawdy">
    <method name="Activate">
      <arg type="s" direction="in" name="tag"/>
      <arg type="b" direction="out" name="ok"/>
    </method>
    <method name="Send">
      <arg type="s" direction="in" name="tag"/>
      <arg type="s" direction="in" name="text"/>
      <arg type="b" direction="out" name="ok"/>
    </method>
  </interface>
</node>`;

export default class KlawdyExtension extends Extension {
    enable() {
        this._impl = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._impl.export(Gio.DBus.session, '/org/klawdy/Klawdy');
        this._timeouts = [];
    }

    disable() {
        this._impl?.unexport();
        this._impl = null;
        for (const id of this._timeouts ?? [])
            GLib.source_remove(id);
        this._timeouts = [];
        this._kbd = null;
    }

    _find(tag) {
        if (!tag)
            return null;
        for (const actor of global.get_window_actors()) {
            const win = actor.get_meta_window();
            if ((win.get_title() || '').includes(tag))
                return win;
        }
        return null;
    }

    _later(ms, fn) {
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            this._timeouts = this._timeouts.filter(x => x !== id);
            fn();
            return GLib.SOURCE_REMOVE;
        });
        this._timeouts.push(id);
    }

    _keys(combo) {
        // combo: list of keyvals; press in order, release in reverse
        if (!this._kbd) {
            const seat = Clutter.get_default_backend().get_default_seat();
            this._kbd = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        }
        let t = GLib.get_monotonic_time();
        for (const k of combo)
            this._kbd.notify_keyval(t++, k, Clutter.KeyState.PRESSED);
        for (const k of [...combo].reverse())
            this._kbd.notify_keyval(t++, k, Clutter.KeyState.RELEASED);
    }

    Activate(tag) {
        const win = this._find(tag);
        if (!win)
            return false;
        Main.activateWindow(win);
        return true;
    }

    // Bring the session's terminal to the front, paste the text and press Enter.
    Send(tag, text) {
        const win = this._find(tag);
        if (!win || !text)
            return false;
        const clip = St.Clipboard.get_default();
        const type = St.ClipboardType.CLIPBOARD;
        clip.get_text(type, (_c, previous) => {
            clip.set_text(type, text);
            Main.activateWindow(win);
            this._later(250, () => {
                if (global.display.get_focus_window() !== win)
                    Main.activateWindow(win);
                this._keys([Clutter.KEY_Control_L, Clutter.KEY_Shift_L, Clutter.KEY_V]);
                this._later(300, () => {
                    this._keys([Clutter.KEY_Return]);
                    // restore what was in the clipboard
                    this._later(500, () => clip.set_text(type, previous ?? ''));
                });
            });
        });
        return true;
    }
}
