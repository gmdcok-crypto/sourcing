import unittest

from services.gemini_trend_scoring import (
    _extract_json_object,
    _is_retryable_gemini_error,
    compute_weighted_total,
    normalize_trend_payload,
    score_to_tier,
    shorten_ai_error_message,
)


class GeminiTrendScoringTests(unittest.TestCase):
    def test_extract_json_object(self) -> None:
        raw = '```json\n{"keyword": "랜턴", "total_score": 80}\n```'
        payload = _extract_json_object(raw)
        self.assertEqual(payload["keyword"], "랜턴")

    def test_weighted_total(self) -> None:
        config = {
            "weights": {
                "velocity": 0.30,
                "viral": 0.30,
                "conversion": 0.20,
                "seasonality": 0.20,
            }
        }
        breakdown = {
            "velocity": 90,
            "viral": 80,
            "conversion": 85,
            "seasonality": 85,
        }
        self.assertEqual(compute_weighted_total(breakdown, config), 85.0)

    def test_normalize_payload(self) -> None:
        config = {
            "weights": {
                "velocity": 0.30,
                "viral": 0.30,
                "conversion": 0.20,
                "seasonality": 0.20,
            },
            "tiers": [
                {"min_score": 85, "label": "GOLD"},
                {"min_score": 0, "label": "WATCH"},
            ],
        }
        result = normalize_trend_payload(
            "캠핑 무선 랜턴",
            {
                "keyword": "캠핑 무선 랜턴",
                "total_score": 99,
                "breakdown": {
                    "velocity": 90,
                    "viral": 80,
                    "conversion": 85,
                    "seasonality": 85,
                },
                "tier": "GOLD",
                "brief_reason": "시즌 부합",
            },
            config,
        )
        self.assertEqual(result["ai_score"], 85.0)
        self.assertEqual(result["ai_tier"], "GOLD")
        self.assertTrue(result["ai_scoring_ready"])

    def test_shorten_503_error(self) -> None:
        message = "503 UNAVAILABLE. {'error': {'code': 503}}"
        self.assertIn("503", shorten_ai_error_message(message))

    def test_retryable_error_detection(self) -> None:
        self.assertTrue(_is_retryable_gemini_error(Exception("503 UNAVAILABLE")))

    def test_score_to_tier(self) -> None:
        config = {
            "tiers": [
                {"min_score": 85, "label": "GOLD"},
                {"min_score": 70, "label": "SILVER"},
                {"min_score": 0, "label": "WATCH"},
            ]
        }
        self.assertEqual(score_to_tier(88, config), "GOLD")
        self.assertEqual(score_to_tier(72, config), "SILVER")


if __name__ == "__main__":
    unittest.main()
