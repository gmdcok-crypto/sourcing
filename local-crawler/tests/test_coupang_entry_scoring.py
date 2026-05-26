import unittest

from services.coupang_entry_scoring import (
    CoupangEntryScoringEngine,
    calc_delivery_score,
    calc_review_entry_score,
    calc_rocket_ratio,
    decide_entry,
    load_scoring_config,
    normalize_top10_products,
)


def _sample_items() -> list:
    rows = []
    for rank in range(1, 11):
        rows.append(
            {
                "rank": rank,
                "title": f"item-{rank}",
                "price": 10000 + rank,
                "review_count": 200 if rank <= 7 else 900,
                "rating": 4.8,
                "delivery_type": "general" if rank <= 6 else "rocket",
            }
        )
    return rows


class CoupangEntryScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CoupangEntryScoringEngine()
        self.config = load_scoring_config()

    def test_review_entry_score_table(self) -> None:
        products = normalize_top10_products(_sample_items(), config=self.config)
        under_count, score, grade = calc_review_entry_score(products, self.config)
        self.assertEqual(under_count, 7)
        self.assertEqual(score, 100.0)
        self.assertEqual(grade, "진입우선")

    def test_delivery_score_formula(self) -> None:
        products = normalize_top10_products(_sample_items(), config=self.config)
        # 6*90 + 4*30 = 660 / 10 = 66
        self.assertEqual(calc_delivery_score(products, self.config), 66.0)

    def test_rocket_ratio(self) -> None:
        products = normalize_top10_products(_sample_items(), config=self.config)
        self.assertEqual(calc_rocket_ratio(products, self.config), 40.0)

    def test_final_score_and_grade(self) -> None:
        result = self.engine.score_keyword("테스트키워드", _sample_items())
        self.assertTrue(result["scoring_ready"])
        self.assertEqual(result["keyword"], "테스트키워드")
        self.assertEqual(result["coupang_review_score"], 100.0)
        self.assertGreaterEqual(result["final_score"], 0)
        self.assertLessEqual(result["final_score"], 100)
        self.assertIn(result["final_grade"], {"S", "A", "B", "C", "D"})
        self.assertEqual(len(result["review_distribution"]), 10)

    def test_entry_decision_recommend(self) -> None:
        decision = decide_entry(
            final_score=85,
            rocket_ratio=40,
            keyword_tier="raw_gem",
            config=self.config,
        )
        self.assertEqual(decision, "recommend")

    def test_entry_decision_hold_premium(self) -> None:
        decision = decide_entry(
            final_score=90,
            rocket_ratio=20,
            keyword_tier="premium",
            config=self.config,
        )
        self.assertEqual(decision, "hold")

    def test_empty_items_fallback(self) -> None:
        result = self.engine.score_keyword("empty", [])
        self.assertFalse(result["scoring_ready"])
        self.assertEqual(result["entry_decision"], "hold")

    def test_partial_top10_incomplete_flag(self) -> None:
        partial = _sample_items()[:5]
        result = self.engine.score_keyword("partial", partial)
        self.assertTrue(result["top10_incomplete"])
        self.assertEqual(result["top10_count"], 5)


if __name__ == "__main__":
    unittest.main()
