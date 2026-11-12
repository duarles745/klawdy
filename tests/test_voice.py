import unittest

try:
    import numpy  # noqa: F401
except ImportError:  # pragma: no cover
    numpy = None

from klawdy import config, i18n, voice


class WakeTest(unittest.TestCase):
    def test_wake_word(self):
        i18n._lang[0] = "pt"
        voice.WAKE_RE = voice.wake_re()
        self.assertEqual(voice.split_wake("Claudinho, abre a pasta Downloads"), (True, "abre a pasta downloads"))
        self.assertEqual(voice.split_wake("ei klawdy abre o navegador"), (True, "abre o navegador"))
        self.assertEqual(voice.split_wake("abre a pasta"), (False, ""))
        self.assertEqual(voice.strip_wake("Claudinho, abre a pasta Downloads."), "abre a pasta Downloads")
        i18n.reset()

    def test_tools_are_restricted_by_default(self):
        tools, prompt = voice.allowed_tools_and_prompt()
        self.assertFalse(any("install" in t for t in tools))
        self.assertNotIn("pkexec", prompt)
        config.set_setting("voice_installs", True)
        tools, prompt = voice.allowed_tools_and_prompt()
        self.assertTrue(any("pkexec apt-get install" in t for t in tools))
        config.set_setting("voice_installs", False)


@unittest.skipIf(numpy is None, "numpy not installed")
class GateTest(unittest.TestCase):
    def test_gate_feeds_only_around_sound(self):
        import numpy as np
        g = voice.Gate()
        quiet = (np.random.default_rng(1).normal(0, 50, 2000)).astype(np.int16).tobytes()
        loud = (np.sin(np.arange(2000) / 5) * 8000).astype(np.int16).tobytes()
        t = 0.0
        for _i in range(10):
            self.assertEqual(g.feed(quiet, t), [])
            t += 0.125
        out = g.feed(loud, t)
        self.assertEqual(len(out), 5)          # pre-roll (0.5 s) + the loud chunk
        self.assertEqual(g.feed(quiet, t + 0.2), [quiet])   # hangover
        self.assertEqual(g.feed(quiet, t + 2.0), [])
