import unittest

from insights import build_insights, fan_summary, num
from simulation import SCENARIOS, Params, simulate


def insights_for(key, **overrides):
    params, scenario = Params(**overrides), SCENARIOS[key]
    return build_insights(params, scenario, simulate(params, scenario))


class InsightsTest(unittest.TestCase):
    def test_number_format_uses_decimal_comma(self):
        self.assertEqual(num(74.94), "74,9")

    def test_every_scenario_has_five_cards(self):
        for key in SCENARIOS:
            self.assertEqual(len(insights_for(key)), 5, key)

    def test_status_follows_peak_temperature(self):
        self.assertEqual(insights_for("disturbance")[0]["tone"], "good")
        self.assertEqual(insights_for("step", fan=50)[0]["tone"], "warn")
        self.assertEqual(insights_for("step", fan=20)[0]["tone"], "hot")

    def test_text_changes_with_numbers(self):
        slow = insights_for("step", fan=20)[1]["text"]
        fast = insights_for("step", fan=100)[1]["text"]
        self.assertNotEqual(slow, fast)
        self.assertIn("94,3", slow)
        self.assertIn("60,0", fast)

    def test_short_simulation_is_reported_as_not_steady(self):
        titles = [card["title"] for card in insights_for("step", t_end=120, fan=20)]
        self.assertIn("Belum steady state", titles)

    def test_max_fan_has_no_upgrade_suggestion(self):
        self.assertEqual(insights_for("step", fan=100)[3]["title"], "Kipas sudah maksimal")

    def test_fan_summary_suggests_minimum_fan(self):
        text = " ".join(card["text"] for card in fan_summary(Params(fan=50)))
        self.assertIn("kipas minimal 45%", text)

    def test_fan_summary_when_fan_cannot_help(self):
        cards = fan_summary(Params(g=0.03))
        self.assertEqual(cards[3]["title"], "Kipas saja tidak cukup")


if __name__ == "__main__":
    unittest.main()
