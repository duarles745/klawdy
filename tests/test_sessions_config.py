import json
import os
import shutil
import time
import unittest

from klawdy import config, sessions


def write_state(name, **kw):
    os.makedirs(config.STATE_DIR, exist_ok=True)
    with open(os.path.join(config.STATE_DIR, name + ".json"), "w") as f:
        json.dump(kw, f)


class SessionsTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(config.STATE_DIR, ignore_errors=True)

    def test_read_sessions(self):
        now = time.time()
        write_state("aaa", state="working", time=now, cwd=config.HOME, title="Refactor")
        write_state("bbb", state="attention", time=now, ntype="idle_prompt", cwd="/proj/x")
        write_state("ccc", state="attention", time=now - 5, message="Claude needs permission")
        write_state("old", state="working", time=now - 7 * 3600)
        write_state("voice", state="listening", time=now)          # voice.json is not a session
        s = sessions.read_sessions(now)
        self.assertEqual([x["sid"] for x in s], ["ccc", "aaa", "bbb"])
        self.assertEqual(s[2]["eff"], "done")                       # idle prompt = waiting for you
        self.assertEqual(s[1]["name"], "Refactor")
        self.assertFalse(os.path.exists(os.path.join(config.STATE_DIR, "old.json")))

    def test_names(self):
        sessions.save_name("abcd1234", "My name")
        self.assertEqual(sessions.session_name("abcd1234", config.HOME), "My name")
        self.assertEqual(sessions.session_name("abcd1234", "/srv/app"), "app · My name")
        sessions.save_name("abcd1234", "")
        self.assertEqual(sessions.session_name("abcd1234", "/srv/app"), "app #abcd")


class ConfigTest(unittest.TestCase):
    def test_safe_defaults(self):
        for key in ("chrome", "voice", "voice_installs"):
            self.assertFalse(config.DEFAULTS[key], key)

    def test_migration(self):
        old = config.OLD_CONF
        os.makedirs(old, exist_ok=True)
        for name, data in (("config.json", {"size": 180, "chrome": True, "sounds": False}),
                           ("names.json", {"sid1": "Name"})):
            with open(os.path.join(old, name), "w") as f:
                json.dump(data, f)
        for p in (config.SETTINGS_FILE, config.NAMES_FILE, os.path.join(config.CONF_DIR, ".migrated")):
            if os.path.exists(p):
                os.remove(p)
        self.assertTrue(config.migrate())
        st = config.load_settings()
        self.assertEqual(st["size"], 180)
        self.assertFalse(st["sounds"])
        self.assertNotIn("chrome", st)                              # security options are not carried
        with open(config.NAMES_FILE) as f:
            self.assertEqual(json.load(f), {"sid1": "Name"})
        self.assertFalse(config.migrate())                          # only once
