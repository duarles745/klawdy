"""Voice commands (offline): "Claudinho, <request>" / "Klawdy, <request>".

* Vosk (small model) only listens for the wake word; the request itself is transcribed by
  faster-whisper. Nothing leaves the computer.
* An energy gate feeds the recogniser only while there is sound above the room noise, and
  Whisper is loaded on demand and unloaded after 10 idle minutes (CPU/RAM friendly).
* The request runs with `claude -p` and a SHORT list of allowed tools (open files/folders,
  list). Installing downloaded programs and Chrome are opt-in (Settings).

Run: <venv>/bin/python -m klawdy.voice   (started by the mascot when the setting "voice" is on
or when the mic button is clicked). State for the mascot: $XDG_RUNTIME_DIR/klawdy/voice.json
"""
import collections
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata

from . import config
from .i18n import _, lang

MODELS = os.path.join(config.APP_DIR, "models")
VOSK_MODELS = {"pt": "vosk-model-small-pt-0.3", "en": "vosk-model-small-en-us-0.15"}
WHISPER_DIR = os.path.join(MODELS, "whisper")
WHISPER_MODEL = "small"
WHISPER_IDLE_UNLOAD = 600
RATE = 16000
CHUNK = 4000               # bytes = 0.125 s of 16-bit mono audio
MAX_UTTER_SECS = 25
LISTEN_SECS = 8            # waiting for the request after the wake word
BUTTON_SECS = 10           # waiting for the request after clicking the mic button
CMD_TIMEOUT = 600

# How the recognisers usually write the wake words
WAKE_DEFAULT = {
    "pt": r"claudinh[oa]s?|claudin|claudio|claudia|clau dinho|cla[ou]dinho|laudinho|gaudinho|cradinho|"
          r"cl[aá]udi[nm]ho|claudino|claudinei|klawd[iy]|clod[iy]|claudi",
    "en": r"klawdy|clawdy|klaudy|claudie|claudy|cloudy|clody|clotty|claudia|clotti",
}
HALLUCINATIONS = ("legendas pela comunidade", "obrigado por assistir", "inscreva-se", "amara.org",
                  "legenda adriana", "thanks for watching", "subtitles by")
HINT_WORDS = ("Downloads, Documentos, Desktop, AnyDesk, Google Chrome, Firefox, VS Code, Spotify, Discord, "
              "Telegram, WhatsApp, Zoom, Teams, Slack, Steam, OBS, GIMP, LibreOffice, PDF, Excel, Word, "
              "PowerPoint, zip, .deb, AppImage, Flatpak, Snap")

BASE_TOOLS = ["Read", "Glob", "Grep", "LS", "Bash(ls:*)", "Bash(find:*)", "Bash(file:*)", "Bash(stat:*)",
              "Bash(head:*)", "Bash(xdg-open:*)", "Bash(setsid -f xdg-open:*)"]
INSTALL_TOOLS = ["Bash(pkexec apt-get install:*)", "Bash(pkexec apt install:*)", "Bash(pkexec snap install:*)",
                 "Bash(flatpak install:*)", "Bash(mkdir -p ~/Applications:*)", "Bash(chmod +x:*)",
                 "Bash(mv:*)", "Bash(setsid -f:*)"]

PROMPT_PT = """Você é o assistente de voz do Klawdy no desktop Linux do usuário. O pedido veio de \
reconhecimento de voz offline e pode ter erros de transcrição: interprete a intenção mais provável.

Regras:
- "O arquivo que acabei de baixar" = o arquivo mais recente em ~/Downloads, ignorando downloads \
incompletos (.crdownload, .part, .tmp). Use `ls -t ~/Downloads | head`.
- Para abrir arquivos, pastas ou sites use: setsid -f xdg-open "CAMINHO" >/dev/null 2>&1
{installs}
- Nunca apague arquivos, não mexa em configurações do sistema e não rode nada destrutivo.
- Se o pedido for ambíguo, perigoso ou não fizer sentido, NÃO execute: diga o que entendeu.
- Responda em português, sem markdown, em no máximo duas frases curtas, dizendo o que fez.
- Se não conseguir fazer o que foi pedido, comece a resposta com "NAO_FEITO:"."""
INSTALLS_PT = """- Para instalar programas baixados:
  * .deb -> pkexec apt-get install -y "/caminho/arquivo.deb" (o sistema pede a senha: é a confirmação)
  * .snap -> pkexec snap install --dangerous "/caminho/arquivo.snap"
  * .flatpakref/.flatpak -> flatpak install --user -y "/caminho/arquivo"
  * .AppImage -> mkdir -p ~/Applications, mv para lá, chmod +x e abra com setsid -f
  * .tar.gz/.zip de programa: não instale; explique o que encontrou."""
NO_INSTALLS_PT = "- Instalar programas está desativado nas configurações: se pedirem, explique isso."

PROMPT_EN = """You are Klawdy's voice assistant on the user's Linux desktop. The request comes from \
offline speech recognition and may contain transcription errors: go for the most likely intent.

Rules:
- "The file I just downloaded" = the newest file in ~/Downloads, ignoring incomplete downloads \
(.crdownload, .part, .tmp). Use `ls -t ~/Downloads | head`.
- To open files, folders or websites use: setsid -f xdg-open "PATH" >/dev/null 2>&1
{installs}
- Never delete files, never change system settings and never run anything destructive.
- If the request is ambiguous, dangerous or makes no sense, do NOT act: say what you understood.
- Answer in English, no markdown, at most two short sentences saying what you did.
- If you could not do it, start the answer with "NAO_FEITO:"."""
INSTALLS_EN = """- To install downloaded programs:
  * .deb -> pkexec apt-get install -y "/path/file.deb" (the system asks for the password: that is the confirmation)
  * .snap -> pkexec snap install --dangerous "/path/file.snap"
  * .flatpakref/.flatpak -> flatpak install --user -y "/path/file"
  * .AppImage -> mkdir -p ~/Applications, mv it there, chmod +x and open with setsid -f
  * .tar.gz/.zip programs: do not install; explain what you found."""
NO_INSTALLS_EN = "- Installing programs is disabled in the settings: if asked, explain that."


def log(*a):
    config.log(*a, path=config.VOICE_LOG)


def play(name):
    if not config.setting("sounds"):
        return
    path = os.path.join(config.SOUNDS_DIR, name + ".wav")
    player = shutil.which("pw-play") or shutil.which("paplay") or shutil.which("aplay")
    if player and os.path.exists(path):
        subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def set_voice(state, text=""):
    config.write_json(config.VOICE_FILE, {"state": state, "text": text, "time": time.time()})


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def wake_re():
    extra = [re.escape(norm(w)) for w in (config.setting("wake_words") or []) if w.strip()]
    pattern = "|".join([WAKE_DEFAULT.get(lang(), WAKE_DEFAULT["en"])] + extra)
    return re.compile(rf"\b(?:hey |ei |oi )?({pattern})\b")


WAKE_RE = wake_re()


def split_wake(text):
    """(True, request_after_it) if the text contains the wake word."""
    n = norm(text)
    m = WAKE_RE.search(n)
    if not m:
        return False, ""
    return True, n[m.end():].strip(" ,.")


def strip_wake(text):
    """Remove the wake word from the start of Whisper's text (keeping accents/case)."""
    words = text.split()
    for i, w in enumerate(words[:3]):
        if WAKE_RE.search(norm(w.strip(",.!?;:"))) or norm(w).startswith(("clau", "klaw", "claw")):
            return " ".join(words[i + 1:]).strip(" ,.")
    return text.strip(" ,.")


def rms(data):
    import numpy as np  # noqa: WPS433
    x = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(math.sqrt(float((x * x).mean()))) if len(x) else 0.0


class Transcriber:
    """faster-whisper, loaded on demand and unloaded when idle."""

    def __init__(self):
        self.model = None
        self.lock = threading.Lock()
        self.loading = threading.Event()
        self.last_use = 0.0
        threading.Thread(target=self._janitor, daemon=True).start()

    def warm_up(self):
        self.last_use = time.time()
        if self.model is None and not self.loading.is_set():
            self.loading.set()
            threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            from faster_whisper import WhisperModel  # noqa: WPS433
            m = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", download_root=WHISPER_DIR,
                             cpu_threads=max(2, (os.cpu_count() or 4) - 2))
            with self.lock:
                self.model = m
            log("whisper loaded")
        except Exception as e:  # noqa: BLE001
            log("whisper unavailable:", e)
        finally:
            self.loading.clear()

    def _janitor(self):
        while True:
            time.sleep(60)
            if self.model is not None and time.time() - self.last_use > WHISPER_IDLE_UNLOAD:
                with self.lock:
                    self.model = None
                log("whisper unloaded (idle)")

    @staticmethod
    def hint():
        names = []
        try:
            d = os.path.expanduser("~/Downloads")
            files = sorted(os.listdir(d), key=lambda f: os.path.getmtime(os.path.join(d, f)), reverse=True)
            for f in files[:6]:
                base = re.split(r"[_\-. ]\d", f)[0]       # "anydesk_8.1.0-1_amd64.deb" -> "anydesk"
                base = os.path.splitext(base)[0].replace("_", " ").replace("-", " ")
                if not re.fullmatch(r"[0-9a-f ]{6,}", base):
                    names.append(base[:30])
        except OSError:
            pass
        return "Klawdy. Claudinho. " + HINT_WORDS + (". " + ", ".join(names) if names else "") + "."

    def transcribe(self, pcm):
        self.warm_up()
        deadline = time.time() + 12
        while self.model is None and self.loading.is_set() and time.time() < deadline:
            time.sleep(0.1)
        with self.lock:
            model = self.model
        if model is None or len(pcm) < RATE:     # under 0.5 s
            return None
        import numpy as np  # noqa: WPS433
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segs, _info = model.transcribe(audio, language=lang(), beam_size=2, without_timestamps=True,
                                       condition_on_previous_text=False, initial_prompt=self.hint(),
                                       vad_filter=True, max_new_tokens=80)
        text = " ".join(sg.text.strip() for sg in segs).strip()
        self.last_use = time.time()
        if any(h in norm(text) for h in HALLUCINATIONS) and len(text) < 40:
            return ""
        return text


def allowed_tools_and_prompt():
    installs = bool(config.setting("voice_installs"))
    tools = BASE_TOOLS + (INSTALL_TOOLS if installs else [])
    if lang() == "pt":
        prompt = PROMPT_PT.format(installs=INSTALLS_PT if installs else NO_INSTALLS_PT)
    else:
        prompt = PROMPT_EN.format(installs=INSTALLS_EN if installs else NO_INSTALLS_EN)
    return tools, prompt


class Runner:
    def __init__(self, transcriber):
        self.busy = False
        self.tr = transcriber

    def run(self, vosk_text, audio=None, had_wake=False):
        if self.busy:
            play("ocupado")
            return
        self.busy = True
        threading.Thread(target=self._prepare, args=(vosk_text, audio, had_wake), daemon=True).start()

    def _prepare(self, vosk_text, audio, had_wake):
        command = None
        try:
            t0 = time.time()
            wtext = self.tr.transcribe(audio) if audio else None
            if wtext is not None:
                log(f"whisper ({time.time() - t0:.1f}s):", wtext)
                command = strip_wake(wtext) if had_wake else wtext.strip(" ,.")
        except Exception as e:  # noqa: BLE001
            log("whisper error:", e)
        if command is None:                 # Whisper unavailable: use Vosk's text
            command = vosk_text
        if not command or len(command) < 3:
            self.busy = False
            set_voice("idle")
            play("naoentendi")
            return
        self._run(command)

    def _run(self, command):
        from . import actions, compat
        started = time.strftime("%Y-%m-%d %H:%M")
        log("request:", command)
        set_voice("running", command)
        play("entendi")
        tools, prompt = allowed_tools_and_prompt()
        cmd = [compat.claude_bin(), "-p", "--model", "haiku", "--append-system-prompt", prompt]
        if config.setting("chrome"):
            cmd.append("--chrome")
            tools = tools + ["mcp__claude-in-chrome"]
        cmd += ["--allowedTools", ",".join(tools)]           # prompt goes through stdin
        try:
            r = subprocess.run(cmd, cwd=config.HOME, input=command, capture_output=True, text=True,
                               timeout=CMD_TIMEOUT)
            answer = (r.stdout or "").strip() or (r.stderr or "").strip() or _("(sem resposta)")
            ok = r.returncode == 0
        except Exception as e:  # noqa: BLE001
            answer, ok = f"{type(e).__name__}: {e}", False
        if answer.startswith("NAO_FEITO:"):
            answer, ok = answer[len("NAO_FEITO:"):].strip(), False
        log("answer:", ok, answer[:300])
        actions.save_answer(command, answer, ok, started, title=_("Pedido por voz"))
        set_voice("done" if ok else "error", command)
        play("pronto" if ok else "erro")
        if config.setting("speak") and shutil.which("spd-say"):
            subprocess.Popen(["spd-say", "-l", "pt-BR" if lang() == "pt" else "en", "-r", "10", answer[:300]],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.busy = False


def take_trigger():
    """True if the mic button was clicked (recent file); consumes it."""
    try:
        age = time.time() - os.path.getmtime(config.TRIGGER_FILE)
        os.remove(config.TRIGGER_FILE)
    except OSError:
        return False
    return age < 15


def model_dir():
    for code in (lang(), "pt", "en"):
        d = os.path.join(MODELS, VOSK_MODELS[code])
        if os.path.isdir(d):
            return d
    return None


class Gate:
    """Feeds the recogniser only around sound louder than the room noise (with pre-roll)."""

    def __init__(self):
        self.noise = 200.0
        self.active_until = float("-inf")
        self.preroll = collections.deque(maxlen=4)      # 0.5 s

    def feed(self, data, now, force=False):
        """Chunks to pass to the recogniser now (possibly empty)."""
        level = rms(data)
        loud = level > max(260.0, self.noise * 2.5)
        if not loud and now > self.active_until:
            self.noise = 0.97 * self.noise + 0.03 * level
        if force or loud:
            out = list(self.preroll) + [data] if now > self.active_until else [data]
            self.preroll.clear()
            self.active_until = now + 1.2                 # hangover lets Vosk close the phrase
            return out
        if now <= self.active_until:
            return [data]
        self.preroll.append(data)
        return []


def ui(runner, state):
    if not runner.busy:          # do not hide "running…" while Claude works
        set_voice(state)


def main():
    from vosk import KaldiRecognizer, Model, SetLogLevel  # noqa: WPS433
    SetLogLevel(-1)
    mdir = model_dir()
    if not mdir:
        log("no Vosk model in", MODELS)
        return 1
    model = Model(mdir)
    runner = Runner(Transcriber())
    signal.signal(signal.SIGTERM, lambda *_a: sys.exit(0))
    log("voice started, model", os.path.basename(mdir))

    button = False
    while True:
        if not config.setting("voice") and not button:
            set_voice("off")
            for _i in range(8):           # 2 s, watching the mic button
                time.sleep(0.25)
                if take_trigger():
                    button = True
                    break
            continue
        ui(runner, "idle")
        rec = KaldiRecognizer(model, RATE)
        gate = Gate()
        proc = subprocess.Popen(["pw-record", "--rate", str(RATE), "--channels", "1", "--format", "s16",
                                 "--raw", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        listening_until = 0.0
        utter = bytearray()        # audio of the current phrase (goes to Whisper)
        woke_partial = False
        last_check = time.time()

        def start_listening(secs):
            nonlocal listening_until
            listening_until = time.time() + secs
            runner.tr.warm_up()
            play("ouvindo")
            ui(runner, "listening")

        if button or take_trigger():
            button = False
            if runner.busy:
                play("ocupado")
            else:
                start_listening(BUTTON_SECS)
        try:
            while True:
                data = proc.stdout.read(CHUNK)
                if not data:
                    break
                now = time.time()
                if now - last_check > 2:
                    last_check = now
                    if not config.setting("voice") and not listening_until:
                        break      # turned off: release the microphone
                if take_trigger():
                    if runner.busy:
                        play("ocupado")
                    elif listening_until:                  # clicked again: cancel
                        listening_until = 0.0
                        ui(runner, "idle")
                        log("listening cancelled by the button")
                    else:                                  # button = wake word
                        rec.Reset()
                        utter = bytearray()
                        woke_partial = False
                        start_listening(BUTTON_SECS)
                    continue
                if listening_until and now > listening_until:
                    listening_until = 0.0
                    ui(runner, "idle")
                    play("naoentendi")
                for chunk in gate.feed(data, now, force=bool(listening_until or woke_partial)):
                    utter.extend(chunk)
                    if len(utter) > MAX_UTTER_SECS * RATE * 2:
                        del utter[: len(utter) - MAX_UTTER_SECS * RATE * 2]
                    if rec.AcceptWaveform(chunk):
                        text = json.loads(rec.Result()).get("text", "").strip()
                        audio, utter = bytes(utter), bytearray()
                        played, woke_partial = woke_partial, False
                        if not text:
                            if played and not listening_until:
                                ui(runner, "idle")
                            continue
                        log("heard:", text)
                        woke, rest = split_wake(text)
                        if woke and rest and len(rest) > 3:
                            listening_until = 0.0
                            runner.run(rest, audio, had_wake=True)
                        elif woke:
                            if not listening_until and not played:
                                play("ouvindo")
                            listening_until = time.time() + LISTEN_SECS
                            runner.tr.warm_up()
                            ui(runner, "listening")
                        elif listening_until:
                            listening_until = 0.0
                            runner.run(text, audio, had_wake=False)
                        elif played:
                            ui(runner, "idle")   # false alarm
                    else:
                        part = json.loads(rec.PartialResult()).get("partial", "")
                        if part and listening_until:
                            listening_until = max(listening_until, now + 3)   # still talking
                        if part and not woke_partial and not listening_until and split_wake(part)[0]:
                            woke_partial = True             # quick reaction to the wake word
                            runner.tr.warm_up()
                            play("ouvindo")
                            ui(runner, "listening")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
