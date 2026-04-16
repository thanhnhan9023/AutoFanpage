"""Telegram reporter entrypoint."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from autofanpage.telegram import format_message  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--status", required=True,
                        choices=["success", "error", "partial", "info"])
    parser.add_argument("--page", required=True)
    parser.add_argument("--details", required=True,
                        help="JSON object with status-specific keys")
    args = parser.parse_args(argv)

    details = json.loads(args.details)
    msg = format_message(status=args.status, page=args.page, details=details)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "telegram_sent.log").open("a") as fh:
        fh.write(msg + "\n---\n")

    print(msg)
    print(json.dumps({"status": args.status, "page": args.page, "sent": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
