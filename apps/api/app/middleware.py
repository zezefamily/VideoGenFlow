"""中间件(Phase 5):请求 ID + 结构化访问日志 + 限流。"""

import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.services import auth as auth_service

logger = logging.getLogger("videogenflow.access")


def _client_id(request: Request) -> str:
    """限流维度:优先用 JWT 里的 user id,否则客户端 IP。"""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        payload = auth_service.decode_token(auth[7:])
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


class RequestLogMiddleware(BaseHTTPMiddleware):
    """为每个请求生成/透传 X-Request-ID,并记录访问日志。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        t0 = time.perf_counter()
        response: Response = await call_next(request)
        ms = int((time.perf_counter() - t0) * 1000)

        response.headers["x-request-id"] = request_id
        logger.info(
            "%s %s %d %dms id=%s cid=%s",
            request.method,
            request.url.path,
            response.status_code,
            ms,
            request_id,
            _client_id(request),
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简易内存令牌桶限流(按 user/ip)。生产多 worker 应换 Redis 后端。

    settings.rate_limit 格式 "<n>/<period>",如 "60/minute"。留空或 health 路径放行。
    """

    def __init__(self, app, limit: str = ""):
        super().__init__(app)
        self.limit = limit
        self.window_sec = 60
        self.max_count = 0
        if limit:
            try:
                count, period = limit.split("/")
                self.max_count = int(count)
                self.window_sec = {"second": 1, "minute": 60, "hour": 3600}.get(
                    period, 60
                )
            except Exception:
                self.max_count = 0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if not self.max_count or request.url.path == "/api/health":
            return await call_next(request)
        # 只限写操作(POST/PATCH/PUT/DELETE):这些是昂贵/易滥用的(发消息、出图、重绘)。
        # GET 读请求(消息列表、图片轮询等)是廉价且前端会正常轮询,不计入限流。
        if request.method == "GET" or request.url.path.startswith("/api/img"):
            return await call_next(request)

        cid = _client_id(request)
        now = time.monotonic()
        dq = self._hits[cid]
        while dq and now - dq[0] > self.window_sec:
            dq.popleft()
        if len(dq) >= self.max_count:
            return Response(
                content='{"detail":"请求过于频繁,请稍后再试"}',
                status_code=429,
                media_type="application/json",
                headers={"retry-after": str(self.window_sec)},
            )
        dq.append(now)
        return await call_next(request)
