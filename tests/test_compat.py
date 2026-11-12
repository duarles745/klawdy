import json
import os
import stat
import tempfile
import unittest

from klawdy import compat

MCP_LIST = """Checking MCP server health…

claude.ai Google Drive: https://drivemcp.googleapis.com/mcp/v1 - ✔ Connected
claude.ai n8n: https://automa.example/mcp-server/http - ! Needs authentication
plugin:engineering:slack: https://mcp.slack.com/mcp (HTTP) - ! Needs authentication
plugin:engineering:gmail:  (HTTP) - - Not configured
broken: thing - ✗ Failed to connect
"""


class McpTest(unittest.TestCase):
    def test_parse_list(self):
        s = compat.parse_mcp_list(MCP_LIST)
        self.assertEqual([x["name"] for x in s], ["claude.ai Google Drive", "claude.ai n8n",
                                                  "plugin:engineering:slack", "plugin:engineering:gmail", "broken"])
        kinds = [compat.mcp_status_kind(x["status"]) for x in s]
        self.assertEqual(kinds, ["ok", "auth", "auth", "unconfigured", "error"])

    def test_parse_garbage(self):
        self.assertEqual(compat.parse_mcp_list("No MCP servers configured."), [])
        self.assertEqual(compat.parse_mcp_list(None), [])

    def test_toggle_keeps_everything_else(self):
        data = {"numStartups": 3, "projects": {compat.config.HOME: {"allowedTools": ["x"]},
                                               "/other": {"disabledMcpServers": ["a"]}}}
        with open(compat.CLAUDE_JSON, "w") as f:
            json.dump(data, f)
        os.chmod(compat.CLAUDE_JSON, 0o600)
        self.assertTrue(compat.mcp_set_enabled("srv", False))
        self.assertEqual(compat.mcp_disabled(), {"srv"})
        with open(compat.CLAUDE_JSON) as f:
            d = json.load(f)
        self.assertEqual(d["numStartups"], 3)
        self.assertEqual(d["projects"][compat.config.HOME]["allowedTools"], ["x"])
        self.assertEqual(d["projects"]["/other"]["disabledMcpServers"], ["a", "srv"])
        self.assertEqual(stat.S_IMODE(os.stat(compat.CLAUDE_JSON).st_mode), 0o600)
        self.assertTrue(compat.mcp_set_enabled("srv", True))
        self.assertEqual(compat.mcp_disabled(), set())

    def test_unexpected_json_never_raises(self):
        with open(compat.CLAUDE_JSON, "w") as f:
            f.write("[1, 2]")
        self.assertEqual(compat.mcp_disabled(), set())
        self.assertFalse(compat.mcp_set_enabled("srv", False))
        os.remove(compat.CLAUDE_JSON)


class FilesTest(unittest.TestCase):
    def test_frontmatter(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write('---\nname: debug\ndescription: >\n  Structured debugging\n  session.\n'
                    'argument-hint: "<error>"\n---\n# body\n')
        fm = compat.read_frontmatter(f.name)
        self.assertEqual(fm, {"name": "debug", "description": "Structured debugging session.",
                              "argument-hint": "<error>"})

    def test_transcript_title_and_info(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "user", "cwd": "/w", "message": {"content": "<command>x</command>"}}) + "\n")
            f.write(json.dumps({"type": "user", "cwd": "/w", "message": {"content": [
                {"type": "text", "text": "organize my   downloads"}]}}) + "\n")
            f.write("not json\n")
        self.assertEqual(compat.transcript_info(f.name), ("/w", "organize my downloads"))
        self.assertEqual(compat.transcript_title(f.name), "organize my downloads")
        with open(f.name, "a") as g:
            g.write(json.dumps({"type": "ai-title", "aiTitle": "Downloads cleanup"}) + "\n")
        compat._title_cache.clear()
        self.assertEqual(compat.transcript_title(f.name), "Downloads cleanup")
        self.assertEqual(compat.transcript_title("/does/not/exist"), "")

    def test_diagnose_never_raises(self):
        self.assertTrue(all(len(row) == 3 for row in compat.diagnose()))
