"""
Configuration API 路由
处理 LLM 配置和 Device Flow OAuth 认证
"""
import os
import asyncio
import re
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import httpx

from backend.core.llm.config_store import (
    get_llm_config,
    save_llm_config,
    get_provider_presets,
    LLMConfig,
    LLMProviderType,
)
from backend.core.llm.providers import reset_llm_client, get_llm_client

router = APIRouter()

# GitHub Device Flow 配置
# 使用 VSCode Copilot 的 Client ID（用于 Copilot 访问）
GITHUB_DEVICE_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "01ab8ac9400c4e429b23")

# 存储 Device Flow 状态
_device_flow_states = {}


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    provider: str  # preset key or 'custom'
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    image_model: Optional[str] = None
    temperature: Optional[float] = None


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    github_token: Optional[str] = None


def _sanitize_error_message(message: str) -> str:
    if not message:
        return message

    patterns = [
        (r"(sk-[A-Za-z0-9]{8,})", "sk-***"),
        (r"(gho_[A-Za-z0-9]{8,})", "gho_***"),
        (r"(Bearer\\s+)[A-Za-z0-9._\\-]{10,}", r"\\1***"),
        (r"(Authorization:\\s*token\\s+)[A-Za-z0-9_\\-]{10,}", r"\\1***"),
    ]
    sanitized = message
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


@router.get("/llm")
async def get_config():
    """获取当前 LLM 配置"""
    config = get_llm_config()

    # 隐藏敏感信息
    return {
        "provider": config.provider,
        "provider_name": config.provider_name,
        "base_url": config.base_url,
        "model": config.model,
        "image_model": getattr(config, "image_model", "") or "",
        "temperature": config.temperature,
        "has_api_key": bool(config.api_key),
        "has_github_token": bool(config.github_token),
        "github_user": config.github_user,
    }


@router.get("/llm/presets")
async def get_presets():
    """获取预设服务商列表"""
    presets = get_provider_presets()
    return {
        "presets": [
            {
                "id": key,
                "name": preset["provider_name"],
                "provider": preset["provider"],
                "base_url": preset["base_url"],
                "default_model": preset["model"],
                "models": preset["models"],
                "requires_oauth": preset.get("requires_oauth", False),
                "no_api_key": preset.get("no_api_key", False),
            }
            for key, preset in presets.items()
        ]
    }


@router.post("/llm")
async def update_config(request: ConfigUpdateRequest):
    """更新 LLM 配置"""
    presets = get_provider_presets()
    current_config = get_llm_config()

    if request.provider in presets:
        preset = presets[request.provider]
        new_base_url = request.base_url or preset["base_url"]
        new_provider = preset["provider"]
        new_provider_name = preset["provider_name"]
        same_provider = (
            current_config.provider == new_provider
            and (current_config.base_url or "") == (new_base_url or "")
            and (current_config.provider_name or "") == (new_provider_name or "")
        )

        # 避免“切换服务商但复用旧 key”导致错误显示/误用：只有在服务商 + base_url 未变化时才保留旧 key
        if request.api_key is None:
            api_key = current_config.api_key if same_provider else ""
        else:
            # 允许显式清空（传空字符串）
            api_key = request.api_key

        if request.image_model is None:
            image_model = getattr(current_config, "image_model", "") if same_provider else ""
        else:
            image_model = request.image_model or ""

        new_config = LLMConfig(
            provider=new_provider,
            provider_name=new_provider_name,
            api_key=api_key,
            base_url=new_base_url,
            model=request.model or preset["model"],
            image_model=image_model,
            temperature=request.temperature if request.temperature is not None else current_config.temperature,
            github_token=current_config.github_token,
            github_user=current_config.github_user,
        )
    else:
        # 自定义配置
        new_base_url = request.base_url or current_config.base_url
        new_provider = LLMProviderType.OPENAI_COMPATIBLE
        new_provider_name = "Custom"
        same_provider = (
            current_config.provider == new_provider
            and (current_config.base_url or "") == (new_base_url or "")
            and (current_config.provider_name or "") == (new_provider_name or "")
        )

        if request.api_key is None:
            api_key = current_config.api_key if same_provider else ""
        else:
            api_key = request.api_key

        if request.image_model is None:
            image_model = getattr(current_config, "image_model", "") if same_provider else ""
        else:
            image_model = request.image_model or ""

        new_config = LLMConfig(
            provider=new_provider,
            provider_name=new_provider_name,
            api_key=api_key,
            base_url=new_base_url,
            model=request.model or current_config.model,
            image_model=image_model,
            temperature=request.temperature if request.temperature is not None else current_config.temperature,
            github_token=current_config.github_token,
            github_user=current_config.github_user,
        )

    if save_llm_config(new_config):
        reset_llm_client()
        return {"success": True, "message": "Configuration updated"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")


@router.post("/llm/test")
async def test_connection(request: TestConnectionRequest):
    """测试 LLM 连接"""
    presets = get_provider_presets()
    current_config = get_llm_config()

    try:
        if request.provider in presets:
            preset = presets[request.provider]
            base_url = request.base_url or preset["base_url"]
            model = request.model or preset["model"]

            # 支持使用已保存的 API key（前端不回显 key，刷新后测试仍可用）
            if request.api_key in (None, "use_saved"):
                api_key = (
                    current_config.api_key
                    if (
                        current_config.provider == preset["provider"]
                        and (current_config.base_url or "") == (base_url or "")
                        and (current_config.provider_name or "") == (preset["provider_name"] or "")
                    )
                    else ""
                )
            else:
                api_key = request.api_key

            config = LLMConfig(
                provider=preset["provider"],
                provider_name=preset["provider_name"],
                api_key=api_key or "",
                base_url=base_url,
                model=model,
                github_token=current_config.github_token if request.github_token == "use_saved" else request.github_token,
            )
        else:
            base_url = request.base_url or ""
            model = request.model or ""
            api_key = request.api_key
            if api_key in (None, "use_saved"):
                api_key = current_config.api_key if (current_config.base_url or "") == (base_url or "") else ""

            config = LLMConfig(
                provider=LLMProviderType.OPENAI_COMPATIBLE,
                api_key=api_key or "",
                base_url=base_url,
                model=model,
                github_token=current_config.github_token if request.github_token == "use_saved" else request.github_token,
            )

        client = get_llm_client(config)
        response = await client.chat([
            {"role": "user", "content": "Say 'Connection successful!' in exactly 3 words."}
        ], max_tokens=20)

        return {
            "success": True,
            "message": "Connection successful",
            "response": response[:100],
        }
    except Exception as e:
        return {
            "success": False,
            "message": _sanitize_error_message(str(e)),
        }


# ========== GitHub Device Flow OAuth ==========

@router.post("/github/device-code")
async def github_device_code():
    """
    开始 GitHub Device Flow 认证
    返回 device_code, user_code, verification_uri
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/device/code",
                data={
                    "client_id": GITHUB_DEVICE_CLIENT_ID,
                    # 显式请求基础用户信息权限，避免拿到“无权限 token”导致后续调用失败
                    "scope": "read:user user:email",
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise HTTPException(status_code=400, detail=data.get("error_description", data["error"]))

            # 保存状态用于轮询
            device_code = data["device_code"]
            _device_flow_states[device_code] = {
                "interval": data.get("interval", 5),
                "expires_in": data.get("expires_in", 900),
            }

            return {
                "device_code": device_code,
                "user_code": data["user_code"],
                "verification_uri": data["verification_uri"],
                "expires_in": data.get("expires_in", 900),
                "interval": data.get("interval", 5),
            }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"GitHub API error: {str(e)}")


@router.post("/github/device-poll")
async def github_device_poll(device_code: str = Query(...)):
    """
    轮询 GitHub Device Flow 认证状态
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_DEVICE_CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
            data = response.json()

            if "error" in data:
                error = data["error"]
                if error == "authorization_pending":
                    return {"status": "pending", "message": "Waiting for user authorization..."}
                elif error == "slow_down":
                    return {"status": "slow_down", "message": "Please wait before polling again"}
                elif error == "expired_token":
                    return {"status": "expired", "message": "Device code expired, please restart"}
                elif error == "access_denied":
                    return {"status": "denied", "message": "User denied the authorization"}
                else:
                    return {"status": "error", "message": data.get("error_description", error)}

            # 成功获取 token
            access_token = data.get("access_token")
            if access_token:
                # 获取用户信息
                user_response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"token {access_token}"},
                )
                user_response.raise_for_status()
                user_data = user_response.json()

                # 保存到配置
                config = get_llm_config()
                config.github_token = access_token
                config.github_user = user_data.get("login")
                save_llm_config(config)
                reset_llm_client()

                # 清理状态
                if device_code in _device_flow_states:
                    del _device_flow_states[device_code]

                return {
                    "status": "success",
                    "message": "GitHub connected successfully!",
                    "user": user_data.get("login"),
                }

            return {"status": "error", "message": "No access token received"}

    except httpx.HTTPError as e:
        return {"status": "error", "message": f"GitHub API error: {str(e)}"}


@router.post("/github/logout")
async def github_logout():
    """退出 GitHub 登录"""
    config = get_llm_config()
    config.github_token = None
    config.github_user = None
    save_llm_config(config)
    reset_llm_client()
    return {"success": True}


@router.get("/github/status")
async def github_status():
    """获取 GitHub 登录状态"""
    config = get_llm_config()
    return {
        "connected": bool(config.github_token),
        "user": config.github_user,
    }
