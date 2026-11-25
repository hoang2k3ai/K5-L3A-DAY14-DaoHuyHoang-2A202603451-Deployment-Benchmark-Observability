import redis

from .config import settings

r = redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
