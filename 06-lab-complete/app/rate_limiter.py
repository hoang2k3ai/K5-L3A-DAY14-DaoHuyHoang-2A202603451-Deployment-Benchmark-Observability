from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Use the Redis clock for all workers and update the window in one operation.
SLIDING_WINDOW = r.register_script("""
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local key = KEYS[1]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - 60000)
if redis.call('ZCARD', key) >= tonumber(ARGV[1]) then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil((tonumber(oldest[2]) + 60000 - now) / 1000))
end
redis.call('ZADD', key, now, ARGV[2])
redis.call('PEXPIRE', key, 60000)
return 0
""")


def check_rate_limit(key: str) -> None:
    digest = sha256(key.encode()).hexdigest()
    if settings.rate_limit_per_minute <= 0:
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "60"})
    retry = SLIDING_WINDOW(
        keys=[f"agent:rate:{digest}"], args=[settings.rate_limit_per_minute, uuid4().hex]
    )
    if retry:
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(retry)})
