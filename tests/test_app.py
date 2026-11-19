import unittest

from app import app


class AppTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_every_page_renders(self):
        for path in ("/", "/simulator", "/kipas", "/model"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("CPU Temp Lab", response.get_data(as_text=True))

    def test_unknown_page_shows_404(self):
        response = self.client.get("/tidak-ada")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Halaman tidak ditemukan", response.get_data(as_text=True))

    def test_footer_has_no_personal_info(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("301240010", html)

    def test_simulator_has_one_active_scenario(self):
        html = self.client.get("/simulator").get_data(as_text=True)
        self.assertEqual(html.count('aria-pressed="true"'), 1)

    def test_navigation_marks_current_page(self):
        html = self.client.get("/kipas").get_data(as_text=True)
        self.assertIn('class="active" aria-current="page"', html)

    def test_simulate_returns_chart_data_and_insights(self):
        response = self.client.post("/api/simulate", json={"scenario": "step", "params": {"fan": 80}})
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["insights"]), 5)
        self.assertIn("status_label", data["metrics"])

    def test_fans_api_returns_bars_and_summary(self):
        response = self.client.post("/api/fans", json={"params": {"fan": 80}})
        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row["current"] and row["fan"] == 80 for row in data["fans"]))
        self.assertEqual(len(data["summary"]), 4)

    def test_fans_api_rejects_invalid_parameter(self):
        response = self.client.post("/api/fans", json={"params": {"g": 5}})
        self.assertEqual(response.status_code, 400)

    def test_unknown_scenario_is_rejected(self):
        response = self.client.post("/api/simulate", json={"scenario": "xyz"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_parameter_is_rejected(self):
        response = self.client.post("/api/simulate", json={"scenario": "step", "params": {"fan": 999}})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
