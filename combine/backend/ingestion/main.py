from __future__ import annotations

import argparse
import asyncio

from ingestion.common.service import run_connectors_once, run_forever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combined tender ingestion worker")
    parser.add_argument("--once", action="store_true", help="Run a single ingestion cycle")
    parser.add_argument("--source", default="", help="Run only one named source connector")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    if args.once or not args.loop:
        await run_connectors_once(target_source=args.source or None)
    else:
        await run_forever()


if __name__ == "__main__":
    asyncio.run(_main())
