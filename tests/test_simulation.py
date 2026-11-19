import unittest

from simulation import SCENARIOS, Params, fan_curve, min_fan_for, parse_params, simulate, status_of


class SimulationTest(unittest.TestCase):
    def test_k_follows_fan_speed(self):
        self.assertAlmostEqual(Params(fan=50).k, 0.03)
        self.assertGreater(Params(fan=100).k, Params(fan=20).k)

    def test_first_euler_step(self):
        # T(1) = 70 + (-0.03 * (70 - 30)) * 1 = 68.8
        result = simulate(Params(), SCENARIOS["steady"])
        self.assertAlmostEqual(result["temperature"][1], 68.8)

    def test_idle_cooling_approaches_ambient(self):
        result = simulate(Params(), SCENARIOS["steady"])
        self.assertAlmostEqual(result["temperature"][-1], 30.0, places=1)

    def test_step_goes_to_theoretical_steady_state(self):
        result = simulate(Params(t_end=600), SCENARIOS["step"])
        self.assertAlmostEqual(result["steady"], 75.0)
        self.assertAlmostEqual(result["temperature"][-1], 75.0, places=1)

    def test_faster_fan_gives_cooler_cpu(self):
        slow = simulate(Params(fan=20), SCENARIOS["step"])["steady"]
        fast = simulate(Params(fan=100), SCENARIOS["step"])["steady"]
        self.assertLess(fast, slow)

    def test_disturbance_raises_steady_state(self):
        result = simulate(Params(), SCENARIOS["disturbance"])
        self.assertAlmostEqual(result["steady"], 40.0)
        self.assertAlmostEqual(result["temperature"][-1], 40.0, places=1)

    def test_peak_metric_and_events(self):
        result = simulate(Params(), SCENARIOS["impulse"])
        self.assertEqual(result["metrics"]["t_peak"], 25)
        self.assertEqual([e["t"] for e in result["events"]], [20, 25])

    def test_status_thresholds(self):
        self.assertEqual([status_of(t) for t in (40, 60, 80)], ["aman", "hangat", "panas"])

    def test_fan_curve_marks_current_fan(self):
        rows = fan_curve(Params(fan=35))
        self.assertEqual([r["fan"] for r in rows if r["current"]], [35])
        self.assertEqual([r["steady"] for r in rows], sorted((r["steady"] for r in rows), reverse=True))

    def test_min_fan_for_hot_limit(self):
        self.assertEqual(min_fan_for(Params(), 80), 45)
        self.assertIsNone(min_fan_for(Params(g=0.03), 80))

    def test_out_of_range_parameter_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_params({"fan": 500})


if __name__ == "__main__":
    unittest.main()
