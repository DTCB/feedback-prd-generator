"""Verify the production Lua limiter using disposable keys, never live counters."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.feedback_prd.quota import QUOTA_SCRIPT


def verify() -> dict:
    url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
    if not url.startswith("https://") or not token:
        raise ValueError("Set the Redis HTTPS REST URL and a writable REST token first.")
    prefix = f"lens:verify:{uuid.uuid4().hex}:"
    keys = [prefix + name for name in ("day", "month", "month-limit")]
    visitors = [prefix + f"visitor:{index}" for index in range(24)]
    owned = keys + visitors
    with httpx.Client(timeout=15, headers={"Authorization": f"Bearer {token}"}) as client:
        def command(*args):
            response = client.post(url, json=list(args))
            response.raise_for_status()
            body = response.json()
            if body.get("error") or "result" not in body:
                raise RuntimeError("Redis command rejected")
            return body["result"]

        def reserve(day, month):
            result = command("EVAL", QUOTA_SCRIPT, 2, day, month, 3, 200, 300, 300)
            if type(result) is not int or result not in (0, 1, 2):
                raise RuntimeError("Unexpected limiter response")
            return result

        try:
            if command("PING") != "PONG":
                raise RuntimeError("Redis health check failed")
            with ThreadPoolExecutor(max_workers=12) as pool:
                daily = list(pool.map(lambda _: reserve(keys[0], keys[1]), range(40)))
            if daily.count(0) != 3 or daily.count(1) != 37:
                raise RuntimeError("Concurrent daily limit is incorrect")
            if [command("GET", key) for key in keys[:2]] != ["3", "3"]:
                raise RuntimeError("Rejected requests changed the counters")
            if not all(0 < command("TTL", key) <= 300 for key in keys[:2]):
                raise RuntimeError("Counter expiry is missing")
            command("SET", keys[2], 199, "EX", 300)
            with ThreadPoolExecutor(max_workers=12) as pool:
                monthly = list(pool.map(lambda day: reserve(day, keys[2]), visitors))
            if monthly.count(0) != 1 or monthly.count(2) != 23 or command("GET", keys[2]) != "200":
                raise RuntimeError("Shared monthly limit is incorrect")
            return {"success": True, "redis_ping": True, "concurrent_daily_allowed": 3,
                    "monthly_stops_at": 200, "counter_expiry_checked": True,
                    "production_counters_touched": False}
        finally:
            # No KEYS/SCAN/FLUSH: only delete this run's explicitly owned UUID keys.
            command("DEL", *owned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env", help="Ignored local configuration file")
    args = parser.parse_args()
    load_dotenv(args.env_file)
    try:
        print(json.dumps(verify()))
        return 0
    except Exception as exception:
        # HTTP exception strings can contain credential-bearing URLs. Never print them.
        print(json.dumps({"success": False, "error_type": type(exception).__name__,
                          "reason": "Redis verification failed; check local configuration, connectivity and writable token."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
