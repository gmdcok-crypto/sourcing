import unittest

from app.services.keyword_scoring import (
    score_ctr_bands,
    score_keyword_final,
    score_monthly_search_volume,
)


class KeywordScoringTests(unittest.TestCase):
    def test_search_volume_anchor_points(self) -> None:
        cases = [
            (100, 40.0),
            (500, 60.0),
            (3_000, 75.0),
            (10_000, 80.0),
            (20_000, 70.0),
            (30_000, 100.0),
            (100_000, 70.0),
        ]
        for volume, expected in cases:
            with self.subTest(volume=volume):
                self.assertEqual(score_monthly_search_volume(volume), expected)

    def test_search_volume_interpolation(self) -> None:
        self.assertEqual(score_monthly_search_volume(300), 50.0)
        self.assertAlmostEqual(score_monthly_search_volume(50_000), 91.43, places=2)

    def test_search_volume_clamps(self) -> None:
        self.assertEqual(score_monthly_search_volume(0), 40.0)
        self.assertEqual(score_monthly_search_volume(200_000), 70.0)

    def test_ctr_bands(self) -> None:
        cases = [
            (0.0, 30.0),
            (1.0, 30.0),
            (1.01, 40.0),
            (1.5, 40.0),
            (2.0, 60.0),
            (3.0, 60.0),
            (4.0, 80.0),
            (5.0, 80.0),
            (5.1, 100.0),
            (9.0, 100.0),
        ]
        for ctr, expected in cases:
            with self.subTest(ctr=ctr):
                self.assertEqual(score_ctr_bands(ctr), expected)

    def test_none_inputs(self) -> None:
        self.assertIsNone(score_monthly_search_volume(None))
        self.assertIsNone(score_ctr_bands(None))

    def test_final_score_average(self) -> None:
        self.assertEqual(score_keyword_final(80.0, 60.0), 70.0)
        self.assertEqual(score_keyword_final(100.0, 100.0), 100.0)
        self.assertIsNone(score_keyword_final(None, 60.0))
        self.assertIsNone(score_keyword_final(80.0, None))


if __name__ == "__main__":
    unittest.main()
