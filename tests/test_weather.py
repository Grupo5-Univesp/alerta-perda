import unittest

from weather import get_climate_recommendation


class ClimateRecommendationTest(unittest.TestCase):
    def test_recommends_attention_after_three_hot_days(self):
        recommendation = get_climate_recommendation({
            "time": ["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13"],
            "temperature_2m_max": [31.5, 32.0, 34.0, 33.0],
        })

        self.assertEqual(recommendation["nivel"], "warning")
        self.assertEqual(len(recommendation["dias_quentes"]), 3)

    def test_keeps_regular_recommendation_below_threshold(self):
        recommendation = get_climate_recommendation({
            "time": ["2026-10-10", "2026-10-11", "2026-10-12"],
            "temperature_2m_max": [29.0, 31.9, 32.0],
        })

        self.assertEqual(recommendation["nivel"], "success")
        self.assertEqual(len(recommendation["dias_quentes"]), 1)

    def test_recommendation_adapts_to_active_categories(self):
        recommendation = get_climate_recommendation({
            "time": ["2026-10-10", "2026-10-11", "2026-10-12"],
            "temperature_2m_max": [32.0, 33.0, 34.0],
        }, ["Laticínios e Frios"])

        self.assertTrue(any("Laticínios" in action for action in recommendation["acoes"]))
        self.assertFalse(any("Carnes" in action for action in recommendation["acoes"]))
