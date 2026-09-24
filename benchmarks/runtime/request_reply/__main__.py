"""Second Runtime process for the Redis HTTP replica probe."""

from __future__ import annotations

import argparse
import asyncio

from benchmarks.runtime.request_reply.workload import serve_replica


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve one Runtime replica over shared Redis."
    )
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--ready-file", required=True)
    args = parser.parse_args()
    asyncio.run(serve_replica(args.redis_url, args.prefix, args.ready_file))


if __name__ == "__main__":
    main()
