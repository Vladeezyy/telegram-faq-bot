import unittest
from pathlib import Path

from faq_bot.matcher import FAQMatcher, normalize

DATA = Path(__file__).resolve().parent.parent / "data" / "faq.example.json"


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.m = FAQMatcher.from_file(DATA)

    def test_exact(self):
        self.assertIn("Monday", self.m.best("What are your working hours?").entry.answer)

    def test_typos_and_case(self):
        self.assertIn("Monday", self.m.best("wht are ur working hourz").entry.answer)

    def test_alias_and_extra_words(self):
        self.assertIn("Visa", self.m.best("hey guys, which payment methods do you have??").entry.answer)

    def test_word_order(self):
        self.assertIn("14 days", self.m.best("product return, is it possible?").entry.answer)

    def test_no_match_returns_none(self):
        self.assertIsNone(self.m.best("what is the capital of france"))

    def test_no_substring_false_positive(self):
        self.assertIsNone(self.m.best("what is the bitcoin price today?"))
        self.assertIsNone(self.m.best("thanks bye"))
        self.assertIsNone(self.m.best("how much is the iphone"))

    def test_empty(self):
        self.assertIsNone(self.m.best("   "))

    def test_csv(self):
        m = FAQMatcher.from_file(DATA.with_name("faq.example.csv"))
        self.assertEqual(len(m), 2)
        self.assertIn("USDT", m.best("do you accept cards").entry.answer)

    def test_normalize(self):
        self.assertEqual(normalize("  How DO I  pay?! "), "pay")


if __name__ == "__main__":
    unittest.main()
