"""认证域路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from super_ai.api.dependencies import (
    BearerCredentials,
    api_error,
    auth_service,
    bearer_token,
    current_user,
)
from super_ai.api.responses import success_response
from super_ai.auth.repositories import UserRecord
from super_ai.auth.service import AuthError, AuthResult

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    """注册请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    email: str
    display_name: str = Field(alias="displayName")
    password: str


class LoginRequest(BaseModel):
    """登录请求体。"""

    email: str
    password: str


def _user_payload(user: UserRecord) -> dict[str, str]:
    """序列化用户信息。"""
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "createdAt": user.created_at.isoformat(),
    }


def _auth_result_payload(result: AuthResult) -> dict[str, object]:
    """序列化认证结果。"""
    return {
        "user": _user_payload(result.user),
        "accessToken": result.access_token,
        "tokenType": result.token_type,
    }


@router.post("/register")
async def register(request: Request, body: RegisterRequest) -> object:
    """注册新用户。"""
    service = auth_service(request)
    try:
        result = await service.register(
            email=body.email,
            display_name=body.display_name,
            password=body.password,
        )
    except AuthError as exc:
        raise api_error(exc) from exc
    return success_response(request, _auth_result_payload(result), status_code=201)


@router.post("/login")
async def login(request: Request, body: LoginRequest) -> object:
    """用户登录。"""
    service = auth_service(request)
    try:
        result = await service.login(email=body.email, password=body.password)
    except AuthError as exc:
        raise api_error(exc) from exc
    return success_response(request, _auth_result_payload(result))


@router.post("/logout")
async def logout(
    request: Request,
    credentials: BearerCredentials,
) -> object:
    """注销当前 token。"""
    token = bearer_token(credentials)
    try:
        await auth_service(request).logout(token)
    except AuthError as exc:
        raise api_error(exc) from exc
    return success_response(request, {"revoked": True})


@router.get("/me")
async def me(
    request: Request,
    user: Annotated[UserRecord, Depends(current_user)],
) -> object:
    """返回当前用户信息。"""
    return success_response(request, _user_payload(user))
