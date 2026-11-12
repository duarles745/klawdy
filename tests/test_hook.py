import json
import os
import shutil
import subprocess
import unittest

from tests import ROOT

HOOK = os.path.join(ROOT, "app", "hook.sh")


@unittest.skipUnless(shutil.which("jq"), "jq not installed")
class HookTest(unittest.TestCase):
    def run_hook(self, state, payload):
        subprocess.run(["bash", HOOK, state], input=json.dumps(payload), text=True, check=True,
                       env=dict(os.environ), timeout=10, capture_output=True)

    def state(self, sid):
        with open(os.path.join(os.environ["XDG_RUNTIME_DIR"], "klawdy", sid + ".json")) as f:
            return json.load(f)

    def test_states_and_skills(self):
        self.run_hook("working", {"session_id": "s1", "hook_event_name": "UserPromptSubmit",
                                  "cwd": "/w", "prompt": "/engineering:debug it fails"})
        st = self.state("s1")
        self.assertEqual((st["state"], st["skill"], st["tag"]), ("working", "engineering:debug", "[klawdy-s1]"))
        self.assertEqual(st["title"], "/engineering:debug it fails")
        self.run_hook("working", {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Bash"})
        self.assertEqual(self.state("s1")["skill"], "engineering:debug")      # kept during the turn
        self.run_hook("working", {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "/mcp"})
        self.assertEqual(self.state("s1")["skill"], "")                       # built-in command
        self.run_hook("working", {"session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": "Skill",
                                  "tool_input": {"skill": "security-review"}})
        self.assertEqual(self.state("s1")["skill"], "security-review")
        self.run_hook("end", {"session_id": "s1"})
        self.assertFalse(os.path.exists(os.path.join(os.environ["XDG_RUNTIME_DIR"], "klawdy", "s1.json")))

    def test_session_id_is_sanitised(self):
        self.run_hook("idle", {"session_id": "../../evil", "hook_event_name": "SessionStart"})
        self.assertTrue(os.path.exists(os.path.join(os.environ["XDG_RUNTIME_DIR"], "klawdy", "evil.json")))

    def test_garbage_input_never_fails(self):
        subprocess.run(["bash", HOOK, "working"], input="not json", text=True, check=True, timeout=10,
                       capture_output=True)
