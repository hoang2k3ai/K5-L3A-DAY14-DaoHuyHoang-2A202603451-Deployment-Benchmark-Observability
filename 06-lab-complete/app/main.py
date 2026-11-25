import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from time import perf_counter

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis import RedisError

from utils.mock_llm import MOCK_RESPONSES, ask as llm_ask

from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, estimate_tokens, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logger = logging.getLogger("agent")
logger.setLevel(settings.log_level.upper())
logger.addHandler(logging.StreamHandler())
logger.propagate = False
MAX_OUTPUT_TOKENS = max(estimate_tokens(answer) for group in MOCK_RESPONSES.values() for answer in group)


def log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "lvl": "INFO",
        "event": event,
        **fields,
    }))


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup", environment=settings.environment)
    try:
        yield
    finally:
        # Uvicorn drains active requests before it runs lifespan cleanup.
        r.close()
        log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log_event("request", method=request.method, path=request.url.path,
                  status=status, ms=round((perf_counter() - start) * 1000, 2))


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    return JSONResponse(status_code=503, content={"detail": "Redis unavailable"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        return JSONResponse(status_code=503, content={"status": "not ready"})
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    input_tokens = estimate_tokens(body.question)
    reservation = check_budget(api_key, input_tokens, MAX_OUTPUT_TOKENS)
    try:
        answer = llm_ask(body.question)
    except Exception:
        record_cost(reservation, 0, 0)
        raise
    record_cost(reservation, input_tokens, estimate_tokens(answer))
    return {"question": body.question, "answer": answer}
