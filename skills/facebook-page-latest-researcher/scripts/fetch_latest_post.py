from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.errors import AutofanpageError
from autofanpage.profile import load_profile
from autofanpage.sources.facebook_page_latest import fetch_latest_post_from_page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    source_cfg = profile.sources.get("facebook_page_latest", {})
    if not source_cfg.get("enabled", False):
        raise AutofanpageError("facebook_page_latest source is not enabled")

    latest_post = fetch_latest_post_from_page(source_cfg)
    artifact_path = Path(args.run_dir) / "latest_source_post.json"
    artifact_path.write_text(
        json.dumps(latest_post, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "artifact": "latest_source_post.json"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
