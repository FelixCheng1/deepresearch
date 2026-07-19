"""CloudBase access-token validation for protected HTTP endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

import requests
from fastapi import HTTPException, Request

from config import Configuration


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str


_TOKEN_CACHE: dict[str, tuple[float, AuthenticatedUser]] = {}


def require_user(request: Request, config: Configuration) -> AuthenticatedUser:
    """Return the authenticated CloudBase subject or reject the request."""

    if not config.auth_required:
        return AuthenticatedUser(id="local-dev")
    if not config.cloudbase_env_id:
        raise HTTPException(status_code=503, detail="服务端登录校验尚未配置")

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="请先登录")

    cached = _TOKEN_CACHE.get(token)
    now = monotonic()
    if cached and cached[0] > now:
        return cached[1]

    url = (
        f"https://{config.cloudbase_env_id}.api.tcloudbasegateway.com"
        "/auth/v1/token/introspect"
    )
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="登录校验服务暂时不可用") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    try:
        subject = str(response.json().get("sub") or "").strip()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="登录校验响应无效") from exc
    if not subject:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    user = AuthenticatedUser(id=subject)
    _TOKEN_CACHE[token] = (now + 30, user)
    if len(_TOKEN_CACHE) > 512:
        for key, value in list(_TOKEN_CACHE.items()):
            if value[0] <= now:
                _TOKEN_CACHE.pop(key, None)
    return user
