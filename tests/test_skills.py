import unittest

from klawdy.skills import skill_gear


class GearTest(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(skill_gear("", custom={}), set())
        self.assertEqual(skill_gear("engineering:debug", custom={}), {"helmet", "sword"})
        self.assertEqual(skill_gear("security-review", custom={}), {"helmet", "shield"})
        self.assertEqual(skill_gear("engineering:code-review", custom={}), {"helmet", "sword", "shield"})
        self.assertEqual(skill_gear("deep-research", custom={}), {"helmet", "sword"})   # default

    def test_custom(self):
        custom = {"deep-research": ["shield"], "plugin:thing": []}
        self.assertEqual(skill_gear("anthropic-skills:deep-research", custom=custom), {"helmet", "shield"})
        self.assertEqual(skill_gear("plugin:thing", custom=custom), {"helmet"})
