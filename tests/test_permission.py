import json
import os
import shutil
import subprocess
import threading
import time
import unittest

from tests import ROOT

from klawdy import actions, config, sessions

HOOK = os.path.join(ROOT, "app", "permission.sh")
REQ = {"session_id": "s1", "cwd": "/w/proj", "hook_event_name": "PermissionRequest",
       "tool_name": "WebSearch", "tool_input": {"query": "ibovespa hoje"}}


@unittest.skipUnless(shutil.which("jq"), "jq not installed")
class PermissionHookTest(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(config.STATE_DIR, ignore_errors=True)
        os.makedirs(config.STATE_DIR)
        with open(config.MASCOT_PID, "w") as f:
            f.write(str(os.getpid()))          # this test process plays the mascot

    def run_hook(self, answer=None, wait=5):
        def answerer():
            for _ in range(100):
                reqs = sessions.read_permissions()
                if reqs:
                    self.seen = reqs[0]
                    if answer is not None:
                        actions.answer_permission(reqs[0]["id"], answer)
                    return
                time.sleep(0.05)
        self.seen = None
        t = threading.Thread(target=answerer)
        t.start()
        r = subprocess.run(["bash", HOOK], input=json.dumps(REQ), text=True, capture_output=True,
                           env=dict(os.environ, KLAWDY_PERM_WAIT=str(wait)), timeout=30)
        t.join()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(os.listdir(config.PERM_DIR), [])       # cleans up after itself
        return json.loads(r.stdout)["hookSpecificOutput"]["decision"] if r.stdout.strip() else None

    def test_allow(self):
        self.assertEqual(self.run_hook(True), {"behavior": "allow"})
        self.assertEqual((self.seen["tool"], self.seen["input"]), ("WebSearch", {"query": "ibovespa hoje"}))

    def test_deny(self):
        self.assertEqual(self.run_hook(False)["behavior"], "deny")

    def test_no_answer_gives_up(self):
        self.assertIsNone(self.run_hook(None, wait=1))

    def test_no_mascot_means_no_wait(self):
        os.remove(config.MASCOT_PID)
        t0 = time.time()
        r = subprocess.run(["bash", HOOK], input=json.dumps(REQ), text=True, capture_output=True, timeout=10)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertLess(time.time() - t0, 3)


class PermissionSummaryTest(unittest.TestCase):
    def test_summaries(self):
        self.assertEqual(sessions.perm_summary("WebSearch", {"query": "q"}), ("Pesquisar na web", "q"))
        what, detail = sessions.perm_summary("Bash", {"command": "ls", "description": "List files"})
        self.assertEqual((what, detail), ("Rodar um comando no terminal", "List files\n\n$ ls"))
        what, detail = sessions.perm_summary("mcp__claude_ai_Google_Drive__search_files", {"q": "x"})
        self.assertEqual(what, "Usar o conector Google_Drive")
        self.assertTrue(detail.startswith("search_files"))
        self.assertEqual(sessions.perm_summary("Strange", None), ("Usar a ferramenta Strange", ""))
        self.assertEqual(len(sessions.perm_summary("Bash", {"command": "x" * 5000})[1]), 600)

    def test_settings_json(self):
        hook = json.loads(actions.perm_settings())["hooks"]["PermissionRequest"][0]["hooks"][0]
        self.assertEqual(hook["timeout"], 300)
        self.assertIn("permission.sh", hook["command"])

    def test_answer_id_is_sanitised(self):
        os.makedirs(config.PERM_DIR, exist_ok=True)
        actions.answer_permission("../../evil", True)
        self.assertTrue(os.path.exists(os.path.join(config.PERM_DIR, "evil.answer")))
