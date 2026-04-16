"""Hacker News researcher entry point.

Usage (from OpenClaw):
    python fetch_hn.py --run-dir <path> --profile <path>

Writes:
    <run_dir>/hackernews_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

# Ensure autofanpage package is importable
_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.profile import load_profile  # noqa: E402
from autofanpage.run_dir import RunDir  # noqa: E402
from autofanpage.schemas import validate  # noqa: E402
from autofanpage.sources.hackernews import filter_and_rank, to_result  # noqa: E402


HN_BASE = "https://hacker-news.firebaseio.com/v0"


def _fetch_top_ids(top_n: int) -> list[int]:
    r = requests.get(f"{HN_BASE}/topstories.json", timeout=10)
    r.raise_for_status()
    return r.json()[:top_n]


def _fetch_item(item_id: int) -> dict:
    r = requests.get(f"{HN_BASE}/item/{item_id}.json", timeout=10)
    r.raise_for_status()
    return r.json()


def run(*, topic: str, min_points: int, limit: int, top_n: int = 200) -> list[dict]:
    ids = _fetch_top_ids(top_n)
    with ThreadPoolExecutor(max_workers=20) as pool:
        items = list(pool.map(_fetch_item, ids))
    filtered = filter_and_rank(
        items, topic=topic, min_points=min_points, limit=limit,
    )
    return [to_result(i) for i in filtered]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    rd = RunDir(path=Path(args.run_dir))

    hn_cfg = profile.sources.get("hackernews", {})
    if not hn_cfg.get("enabled", False):
        rd.write_json("hackernews_results", [])
        print(json.dumps({"skipped": True, "count": 0}))
        return 0

    results = run(
        topic=profile.topic,
        min_points=hn_cfg.get("min_points", 50),
        limit=10,
    )
    validate("hackernews_results", results)
    rd.write_json("hackernews_results", results)
    print(json.dumps({"count": len(results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
