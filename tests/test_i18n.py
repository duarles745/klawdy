import re
import unittest

from klawdy import i18n
from klawdy.strings_en import EN
from tests.i18n_keys import keys

PLACEHOLDER = re.compile(r"\{(\w+)\}")


class I18nTest(unittest.TestCase):
    def test_every_string_has_english(self):
        missing = [k for k in keys() if k not in EN]
        self.assertEqual(missing, [], "add these to strings_en.py")

    def test_placeholders_match(self):
        for pt, en in EN.items():
            self.assertEqual(set(PLACEHOLDER.findall(pt)), set(PLACEHOLDER.findall(en)), pt)

    def test_switch_language(self):
        i18n._lang[0] = "en"
        self.assertEqual(i18n._("Tamanho: {size}px", size=10), "Size: 10px")
        i18n._lang[0] = "pt"
        self.assertEqual(i18n._("Tamanho: {size}px", size=10), "Tamanho: 10px")
        i18n.reset()
