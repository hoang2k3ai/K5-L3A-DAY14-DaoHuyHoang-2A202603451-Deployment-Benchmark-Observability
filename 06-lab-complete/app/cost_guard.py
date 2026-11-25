from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Integer nanodollars keep the budget comparison exact.
NANODOLLARS = 1_000_000_000
INPUT_PER_TOKEN = 150
OUTPUT_PER_TOKEN = 600

RESERVE = r.register_script("""
for i, key in ipairs(KEYS) do
    local current = tonumber(redis.call('GET', key) or '0')
    if current + tonumber(ARGV[1]) > tonumber(ARGV[2 * i]) then return 0 end
end
for i, key in ipairs(KEYS) do
    redis.call('INCRBY', key, ARGV[1])
    redis.call('EXPIREAT', key, ARGV[2 * i + 1])
end
return 1
""")

REFUND = r.register_script("""
for _, key in ipairs(KEYS) do
    if redis.call('EXISTS', key) == 1 then
        redis.call('DECRBY', key, ARGV[1])
    end
end
""")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def check_budget(api_key: str, input_tokens: int, max_output_tokens: int) -> tuple[list[str], int]:
    now = datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)
    next_month = (month + timedelta(days=32)).replace(day=1)
    digest = sha256(api_key.encode()).hexdigest()
    reserved = input_tokens * INPUT_PER_TOKEN + max_output_tokens * OUTPUT_PER_TOKEN
    keys = [f"agent:cost:{digest}:{month:%Y-%m}"]
    args = [reserved, int(settings.monthly_budget_usd * NANODOLLARS), int(next_month.timestamp())]
    if settings.daily_budget_usd is not None:
        keys.append(f"agent:cost:{digest}:{day:%Y-%m-%d}")
        args.extend([int(settings.daily_budget_usd * NANODOLLARS), int((day + timedelta(days=1)).timestamp())])
    if not RESERVE(keys=keys, args=args):
        raise HTTPException(402, "LLM budget exceeded")
    return keys, reserved


def record_cost(reservation: tuple[list[str], int], input_tokens: int, output_tokens: int) -> None:
    keys, reserved = reservation
    actual = input_tokens * INPUT_PER_TOKEN + output_tokens * OUTPUT_PER_TOKEN
    if actual != reserved:
        REFUND(keys=keys, args=[reserved - actual])
