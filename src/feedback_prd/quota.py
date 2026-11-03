"""Atomic Redis quotas. No feedback bodies or raw IP addresses are stored."""
from __future__ import annotations

import hashlib
import hmac
import os
import threading
from datetime import datetime, timedelta, timezone

import httpx

QUOTA_SCRIPT = """
local daily = tonumber(redis.call('GET', KEYS[1]) or '0')
local monthly = tonumber(redis.call('GET', KEYS[2]) or '0')
if daily >= tonumber(ARGV[1]) then return 1 end
if monthly >= tonumber(ARGV[2]) then return 2 end
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], ARGV[4])
return 0
"""
_lock = threading.Lock()
_local: dict[str, int] = {}


class QuotaError(Exception):
    def __init__(self, message: str, status: int = 429):
        self.message, self.status = message, status


def configured() -> bool:
    return bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN") and os.getenv("QUOTA_HASH_SECRET"))


def reserve(ip: str, *, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    salt = os.getenv("QUOTA_HASH_SECRET", "local-only")
    anonymous = hmac.new(salt.encode(), (now.strftime("%Y-%m-%d") + ip).encode(), hashlib.sha256).hexdigest()
    keys = [f"lens:day:{now:%Y-%m-%d}:{anonymous}", f"lens:month:{now:%Y-%m}"]
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    args = [3, 200, int((tomorrow - now).total_seconds()) + 60, int((next_month - now).total_seconds()) + 60]
    if configured():
        try:
            with httpx.Client(timeout=8) as client:
                response = client.post(os.environ["UPSTASH_REDIS_REST_URL"],
                    headers={"Authorization": f"Bearer {os.environ['UPSTASH_REDIS_REST_TOKEN']}"},
                    json=["EVAL", QUOTA_SCRIPT, 2, *keys, *args])
                response.raise_for_status()
                body = response.json()
                if body.get("error") or body.get("result") not in (0, 1, 2):
                    raise ValueError("invalid quota result")
                result = body["result"]
        except Exception:
            raise QuotaError("实时额度服务暂不可用，请继续体验案例或稍后重试。", 503) from None
    elif os.getenv("VERCEL"):
        raise QuotaError("实时 AI 尚未开放，案例体验与模板生成仍可使用。", 503)
    else:
        with _lock:
            result = 1 if _local.get(keys[0], 0) >= 3 else 2 if _local.get(keys[1], 0) >= 200 else 0
            if not result:
                for key in keys:
                    _local[key] = _local.get(key, 0) + 1
            # Keep local development memory bounded across many dates.
            for key in list(_local):
                if not key.startswith((f"lens:day:{now:%Y-%m-%d}:", f"lens:month:{now:%Y-%m}")):
                    del _local[key]
    if result:
        raise QuotaError("今天的实时体验次数已用完，明天可再试。" if result == 1 else "本月实时体验额度已用完，案例与模板仍可使用。")
