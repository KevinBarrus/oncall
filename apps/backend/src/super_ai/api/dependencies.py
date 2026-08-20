"""共享 FastAPI 依赖提供者（app 与 domain router 共用）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from super_ai.auth.repositories import UserRecord
from super_ai.auth.service import AuthError, AuthService
from super_ai.memory.repositories import MemoryRepositories

from .responses import ApiErrorException

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def auth_service(request: Request) -> AuthService:
    """返回应用状态中的认证服务。"""
    return request.app.state.auth_service


def memory_repositories(request: Request) -> MemoryRepositories:
    """返回应用状态中的存储仓库。"""
    return request.app.state.memory_repositories


def bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    """从 Bearer 凭据提取 token，缺失或非 Bearer 时报认证错误。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiErrorException("AUTH_UNAUTHENTICATED")
    return credentials.credentials


def api_error(exc: AuthError) -> ApiErrorException:
    """把认证业务错误转为统一 API 错误。"""
    return ApiErrorException(exc.code, str(exc))


async def current_user(
    request: Request,
    credentials: BearerCredentials,
) -> UserRecord:
    """当前已认证用户依赖。"""
    token = bearer_token(credentials)
    try:
        return await auth_service(request).authenticate_token(token)
    except AuthError as exc:
        raise api_error(exc) from exc
