"""Supabase 用户验证 — 通过 Supabase Auth API 验证 token"""

import httpx
from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()


class SupabaseUser(BaseModel):
    id: str
    email: str = ""


async def get_current_user(request: Request) -> SupabaseUser:
    """
    通过 Supabase Auth API 验证 Bearer token，返回当前用户。
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证令牌")

    token = auth_header[7:]

    supabase_url = settings.supabase_url
    anon_key = settings.supabase_anon_key

    if not supabase_url or not anon_key:
        raise HTTPException(status_code=500, detail="后端未配置 Supabase URL 和 Anon Key")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": anon_key,
                },
            )

        if resp.status_code != 200:
            print(f"[Auth] token 验证失败: {resp.status_code} {resp.text[:200]}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌无效或已过期")

        user_data = resp.json()
        return SupabaseUser(
            id=user_data["id"],
            email=user_data.get("email", ""),
        )

    except httpx.RequestError as e:
        print(f"[Auth] 请求 Supabase 失败: {e}")
        raise HTTPException(status_code=503, detail="认证服务暂时不可用")
