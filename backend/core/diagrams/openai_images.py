"""
OpenAI-compatible image generation helper.

We use raw HTTP (httpx) instead of SDK to maximize compatibility with local gateways.
"""

from __future__ import annotations

from typing import Optional, Tuple
import base64
import logging
import json
import re

import httpx

logger = logging.getLogger(__name__)


def _guess_png(image_bytes: bytes) -> bytes:
    """
    Ensure returned bytes are PNG.
    - If already PNG, return as-is.
    - Otherwise, try converting via Pillow (if available).
    """
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return image_bytes
    try:
        from PIL import Image
        import io

        im = Image.open(io.BytesIO(image_bytes))
        out = io.BytesIO()
        im.convert("RGBA").save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        # Best-effort: return original (may not be PNG)
        return image_bytes


def _decode_data_url_to_bytes(url: str) -> Optional[bytes]:
    u = (url or "").strip()
    if not u:
        return None
    m = re.match(r"^data:image/[^;]+;base64,(.+)$", u, re.IGNORECASE)
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1))
    except Exception:
        return None


async def _extract_image_bytes_from_response(data: dict, client: httpx.AsyncClient) -> Optional[bytes]:
    if not isinstance(data, dict):
        return None

    def _decode_from_item(item: dict) -> Optional[bytes]:
        if not isinstance(item, dict):
            return None
        for key in ("b64_json", "b64", "base64", "image_base64"):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                try:
                    return base64.b64decode(val)
                except Exception:
                    continue

        image_obj = item.get("image")
        if isinstance(image_obj, dict):
            for key in ("b64_json", "b64", "base64", "image_base64"):
                val = image_obj.get(key)
                if isinstance(val, str) and val.strip():
                    try:
                        return base64.b64decode(val)
                    except Exception:
                        continue

        url_obj = item.get("image_url")
        if isinstance(url_obj, dict):
            maybe = url_obj.get("url")
            if isinstance(maybe, str):
                data_url_bytes = _decode_data_url_to_bytes(maybe)
                if data_url_bytes:
                    return data_url_bytes

        maybe_url = item.get("url")
        if isinstance(maybe_url, str) and maybe_url.strip():
            data_url_bytes = _decode_data_url_to_bytes(maybe_url)
            if data_url_bytes:
                return data_url_bytes

        text_val = item.get("text")
        if isinstance(text_val, str):
            m = re.search(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", text_val)
            if m:
                data_url_bytes = _decode_data_url_to_bytes(m.group(0))
                if data_url_bytes:
                    return data_url_bytes

        return None

    # OpenAI images schema: {"data": [ ... ]}
    items = data.get("data")
    if isinstance(items, list):
        for item in items:
            raw = _decode_from_item(item)
            if raw:
                return raw
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                try:
                    r2 = await client.get(item["url"])
                    r2.raise_for_status()
                    return r2.content
                except Exception:
                    continue

    # Chat completions schema: {"choices": [{"message": ...}]}
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            raw = _decode_from_item(message)
            if raw:
                return raw

            images = message.get("images")
            if isinstance(images, list):
                for img in images:
                    raw = _decode_from_item(img if isinstance(img, dict) else {})
                    if raw:
                        return raw

            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    raw = _decode_from_item(part if isinstance(part, dict) else {})
                    if raw:
                        return raw

            if isinstance(content, str):
                m = re.search(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", content)
                if m:
                    data_url_bytes = _decode_data_url_to_bytes(m.group(0))
                    if data_url_bytes:
                        return data_url_bytes

    return None


async def generate_image_png_via_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    size: str = "1024x1024",
    timeout_s: float = 120.0,
) -> Tuple[bytes, dict]:
    """
    Returns (png_bytes, raw_response_json).

    Preferred: POST {base_url}/images/generations.
    Fallback: POST {base_url}/chat/completions with image output modalities.
    """
    b = (base_url or "").rstrip("/")
    if not b:
        raise RuntimeError("base_url 为空")
    images_url = f"{b}/images/generations"
    chat_url = f"{b}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        image_payloads = [
            {
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": 1,
                "response_format": "b64_json",
            },
            {
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": 1,
            },
        ]

        images_error: Optional[Exception] = None
        images_unsupported = False
        for payload in image_payloads:
            try:
                resp = await client.post(images_url, headers=headers, json=payload)
                if resp.status_code == 404:
                    images_unsupported = True
                    break
                resp.raise_for_status()
                data = resp.json()
                raw_bytes = await _extract_image_bytes_from_response(data, client)
                if not raw_bytes:
                    raise RuntimeError("成图接口未返回图片数据（images/generations）")
                return _guess_png(raw_bytes), data
            except Exception as e:
                images_error = e
                continue

        chat_payloads = [
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["text", "image"],
                "image": {"size": size},
                "temperature": 0.2,
                "max_tokens": 300,
            },
            {
                "model": model,
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": prompt}]},
                ],
                "modalities": ["text", "image"],
                "image": {"size": size},
                "temperature": 0.2,
                "max_tokens": 300,
            },
        ]

        chat_error: Optional[Exception] = None
        for payload in chat_payloads:
            try:
                resp = await client.post(chat_url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                raw_bytes = await _extract_image_bytes_from_response(data, client)
                if not raw_bytes:
                    raise RuntimeError("chat/completions 未返回图片数据")
                return _guess_png(raw_bytes), data
            except Exception as e:
                chat_error = e
                continue

        if images_unsupported and chat_error is not None:
            raise RuntimeError(f"当前 base_url 不支持图片生成接口：{chat_error}")
        if chat_error is not None and images_error is not None:
            raise RuntimeError(f"图片生成失败：{images_error}; chat fallback: {chat_error}")
        if images_error is not None:
            raise RuntimeError(f"图片生成失败：{images_error}")
        if chat_error is not None:
            raise RuntimeError(f"图片生成失败：{chat_error}")
        raise RuntimeError("图片生成失败：未知错误")


def _extract_message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
        return "\n".join(chunks)
    return ""


def _extract_json_obj(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\s*", "", raw).strip()
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _normalize_review_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}

    passed = payload.get("passed")
    if not isinstance(passed, bool):
        score_raw = payload.get("score")
        try:
            score_num = int(score_raw)
        except Exception:
            score_num = 0
        passed = score_num >= 80

    try:
        score = int(payload.get("score", 0))
    except Exception:
        score = 0
    score = max(0, min(100, score))

    def _norm_list(key: str) -> list[str]:
        val = payload.get(key)
        if not isinstance(val, list):
            return []
        out = []
        for item in val:
            s = str(item or "").strip()
            if s:
                out.append(s[:160])
        return out[:8]

    summary = str(payload.get("summary") or "").strip()
    if not summary:
        summary = "图示已完成自动审核。"

    return {
        "passed": bool(passed),
        "score": score,
        "issues": _norm_list("issues"),
        "improvements": _norm_list("improvements"),
        "summary": summary[:300],
    }


async def review_image_via_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    review_prompt: str,
    image_bytes: bytes,
    timeout_s: float = 120.0,
) -> Tuple[dict, dict]:
    """
    Review a generated image via OpenAI-compatible chat completions.
    Returns (normalized_review, raw_response_json).
    """
    b = (base_url or "").rstrip("/")
    if not b:
        raise RuntimeError("base_url 为空")
    url = f"{b}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{image_b64}"

    system_text = (
        "你是科研图示审核器。请只输出 JSON，不要输出其他内容。"
        'JSON 结构：{"passed": true|false, "score": 0-100, "issues": ["..."], '
        '"improvements": ["..."], "summary": "..."}'
    )

    base_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_text},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": review_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    alt_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_text},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": review_prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    payloads = [
        {**base_payload, "response_format": {"type": "json_object"}},
        base_payload,
        alt_payload,
    ]

    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        for payload in payloads:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

                message = (((data.get("choices") or [{}])[0]).get("message") or {})
                raw_content = _extract_message_text(message.get("content"))
                parsed = _extract_json_obj(raw_content)
                if not parsed:
                    raise RuntimeError("审核模型返回内容无法解析为 JSON")

                return _normalize_review_payload(parsed), data
            except Exception as e:
                last_error = e
                continue

    raise RuntimeError(f"图示审核失败：{last_error}")
