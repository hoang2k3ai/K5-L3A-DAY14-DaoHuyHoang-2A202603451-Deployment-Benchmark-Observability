import os
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_api_key: str = os.getenv("AGENT_API_KEY", "")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    monthly_budget_usd: Decimal = Decimal(os.getenv("MONTHLY_BUDGET_USD", "10"))
    daily_budget_usd: Decimal | None = (
        Decimal(value) if (value := os.getenv("DAILY_BUDGET_USD")) else None
    )
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
