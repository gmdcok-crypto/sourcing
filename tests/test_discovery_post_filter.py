"""discovery_post_filter — depth cap + enrich_budget + deepest_win."""
from __future__ import annotations

import unittest

from app.services.discovery_post_filter import (
    apply_discovery_post_filter,
    category_path_depth,
    dedupe_deepest_win,
)


def _row(
    keyword: str,
    *,
    depth: int,
    rank: int,
    group: str,
    order: int = 0,
) -> dict:
    path = " > ".join(["카테고리"] * depth)
    return {
        "keyword": keyword,
        "source_group": group,
        "source_group_order": order,
        "source_path": path,
        "full_path": path,
        "cid_depth": depth,
        "datalab_rank": rank,
        "rank": rank,
    }


class TestDiscoveryPostFilter(unittest.TestCase):
    def test_category_path_depth_with_spaces(self) -> None:
        self.assertEqual(category_path_depth("A > B > C"), 3)
        self.assertEqual(category_path_depth("A>B"), 2)

    def test_deepest_win_keeps_deeper_cid(self) -> None:
        rows = [
            _row("dup", depth=2, rank=1, group="cid:1", order=0),
            _row("dup", depth=4, rank=5, group="cid:2", order=1),
        ]
        output = dedupe_deepest_win(rows)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["cid_depth"], 4)
        self.assertEqual(output[0]["source_group"], "cid:2")

    def test_group_depth_cap_l4(self) -> None:
        config = {
            "enabled": True,
            "by_depth": {"L1": 50, "L2": 60, "L3": 70, "L4": 80},
            "default_depth_label": "L2",
            "depth_ge5_uses": "L4",
            "enrich_budget": 400,
            "dedupe": "deepest_win",
        }
        rows = [_row(f"k{i}", depth=4, rank=i, group="cid:1") for i in range(1, 90)]
        output, stats = apply_discovery_post_filter(rows, cfg=config, log=None)
        self.assertEqual(len(output), 80)
        self.assertEqual(stats["after_group_cap"], 80)

    def test_enrich_budget_trim(self) -> None:
        config = {
            "enabled": True,
            "by_depth": {"L1": 50, "L2": 60, "L3": 70, "L4": 80},
            "default_depth_label": "L2",
            "depth_ge5_uses": "L4",
            "enrich_budget": 400,
            "dedupe": "deepest_win",
        }
        rows = []
        for group_index in range(8):
            for rank in range(1, 81):
                rows.append(
                    _row(
                        f"g{group_index}-k{rank}",
                        depth=4,
                        rank=rank,
                        group=f"cid:{group_index}",
                        order=group_index,
                    )
                )
        output, stats = apply_discovery_post_filter(rows, cfg=config, log=None)
        self.assertEqual(len(output), 400)
        self.assertEqual(stats["budget_trimmed"], 240)


if __name__ == "__main__":
    unittest.main()
