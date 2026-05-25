"""
STEP1 후보 — 노이즈 필터 이후 depth cap + enrich_budget.

테마/CID 소싱: source_group = CID, depth = full_path 세그먼트 수.
"""
from __future__ import annotations

import copy
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from app.services.keyword_noise import normalize_keyword

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "keyword_discovery_post_filter.yaml"

_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "by_depth": {"L1": 50, "L2": 60, "L3": 70, "L4": 80},
    "default_depth_label": "L2",
    "depth_ge5_uses": "L4",
    "enrich_budget": 400,
    "dedupe": "deepest_win",
}


def load_discovery_post_filter_config() -> Dict[str, Any]:
    cfg = copy.deepcopy(_DEFAULTS)
    if not _CONFIG_PATH.is_file():
        return cfg
    try:
        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        block = raw.get("discovery_post_filter")
        if isinstance(block, dict):
            if isinstance(block.get("by_depth"), dict):
                cfg["by_depth"].update(block["by_depth"])
            for key in ("enabled", "default_depth_label", "depth_ge5_uses", "enrich_budget", "dedupe"):
                if key in block:
                    cfg[key] = block[key]
    except Exception:
        pass
    return cfg


def category_path_depth(category_path: str) -> int:
    path = str(category_path or "").strip()
    if not path:
        return 0
    return len([segment for segment in path.split(">") if str(segment).strip()])


def depth_label_from_depth(depth: int, cfg: Optional[Dict[str, Any]] = None) -> str:
    config = cfg if cfg is not None else load_discovery_post_filter_config()
    value = int(depth or 0)
    if value >= 5:
        return str(config.get("depth_ge5_uses") or "L4")
    if 1 <= value <= 4:
        return f"L{value}"
    return str(config.get("default_depth_label") or "L2")


def cap_for_depth_label(label: str, cfg: Optional[Dict[str, Any]] = None) -> int:
    config = cfg if cfg is not None else load_discovery_post_filter_config()
    by_depth = config.get("by_depth") or {}
    default_label = str(config.get("default_depth_label") or "L2")
    try:
        return max(0, int(by_depth.get(str(label or "")) or by_depth.get(default_label) or 0))
    except (TypeError, ValueError):
        return 0


def cap_for_row(row: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None) -> int:
    config = cfg if cfg is not None else load_discovery_post_filter_config()
    depth = int(
        row.get("cid_depth")
        or category_path_depth(str(row.get("source_path") or row.get("full_path") or row.get("category_path") or ""))
    )
    label = depth_label_from_depth(depth, config)
    row.setdefault("depth_label", label)
    row.setdefault("cid_depth", depth)
    return cap_for_depth_label(label, config)


def _row_sort_key(row: Dict[str, Any]) -> Tuple[int, int, int]:
    return (
        -int(row.get("cid_depth") or 0),
        int(row.get("datalab_rank") or row.get("rank") or 9999),
        int(row.get("source_group_order") or 0),
    )


def _row_beats(candidate: Dict[str, Any], previous: Dict[str, Any]) -> bool:
    return _row_sort_key(candidate) < _row_sort_key(previous)


def dedupe_deepest_win(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    winners: Dict[str, Dict[str, Any]] = {}
    first_index: Dict[str, int] = {}
    for index, row in enumerate(rows):
        normalized = normalize_keyword(str(row.get("keyword") or row.get("keyword_text") or ""))
        if not normalized:
            continue
        if normalized not in first_index:
            first_index[normalized] = index
        previous = winners.get(normalized)
        if previous is None or _row_beats(row, previous):
            winners[normalized] = row
    ordered = sorted(winners.keys(), key=lambda key: first_index.get(key, 0))
    return [winners[key] for key in ordered]


def apply_discovery_post_filter(
    rows: List[Dict[str, Any]],
    *,
    cfg: Optional[Dict[str, Any]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    config = cfg if cfg is not None else load_discovery_post_filter_config()
    stats: Dict[str, Any] = {
        "enabled": bool(config.get("enabled", True)),
        "input_count": len(rows),
        "after_dedupe": 0,
        "after_group_cap": 0,
        "enrich_budget": int(config.get("enrich_budget") or 0),
        "output_count": 0,
        "budget_trimmed": 0,
        "group_summaries": [],
    }
    if not rows:
        return [], stats
    if not bool(config.get("enabled", True)):
        budget = int(config.get("enrich_budget") or 0)
        output = list(rows)
        if budget > 0 and len(output) > budget:
            stats["budget_trimmed"] = len(output) - budget
            output = output[:budget]
        stats["output_count"] = len(output)
        return output, stats

    dedupe_mode = str(config.get("dedupe") or "deepest_win").strip().lower()
    working = dedupe_deepest_win(rows) if dedupe_mode == "deepest_win" else list(rows)
    stats["after_dedupe"] = len(working)

    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    group_order: Dict[str, int] = {}
    for row in working:
        group_key = str(row.get("source_group") or row.get("cid") or "unknown")
        groups[group_key].append(row)
        group_order.setdefault(group_key, int(row.get("source_group_order") or 0))

    capped: List[Dict[str, Any]] = []
    for group_key in sorted(groups.keys(), key=lambda key: (group_order.get(key, 0), key)):
        group_rows = sorted(
            groups[group_key],
            key=lambda item: int(item.get("datalab_rank") or item.get("rank") or 9999),
        )
        if not group_rows:
            continue
        depth = int(
            group_rows[0].get("cid_depth")
            or category_path_depth(
                str(group_rows[0].get("source_path") or group_rows[0].get("full_path") or "")
            )
        )
        label = depth_label_from_depth(depth, config)
        cap = cap_for_depth_label(label, config)
        kept = group_rows[:cap] if cap > 0 else []
        capped.extend(kept)
        stats["group_summaries"].append(
            {
                "source_group": group_key,
                "depth_label": label,
                "cid_depth": depth,
                "after_filter": len(group_rows),
                "cap": cap,
                "kept": len(kept),
            }
        )
        if log:
            log(
                f"post-filter {group_key} {label}(depth={depth}) "
                f"kept={len(kept)}/{cap} pool={len(group_rows)}"
            )

    stats["after_group_cap"] = len(capped)
    capped.sort(key=_row_sort_key)

    budget = int(config.get("enrich_budget") or 0)
    output = capped
    if budget > 0 and len(output) > budget:
        stats["budget_trimmed"] = len(output) - budget
        output = output[:budget]
        if log:
            log(f"post-filter enrich_budget {stats['after_group_cap']} -> {len(output)} (budget={budget})")

    stats["output_count"] = len(output)
    if log and stats["input_count"] != stats["output_count"]:
        log(
            f"post-filter in={stats['input_count']} dedupe={stats['after_dedupe']} "
            f"group_cap={stats['after_group_cap']} out={stats['output_count']}"
        )
    return output, stats
