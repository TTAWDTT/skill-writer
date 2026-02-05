"""
OpenAI-compatible image generation helper.

We use raw HTTP (httpx) instead of SDK to maximize compatibility with local gateways.
"""

from __future__ import annotations

from typing import Optional, Tuple
import base64
import logging

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

    Uses POST {base_url}/images/generations with response_format=b64_json (preferred).
    Falls back to URL download when only URL is returned.
    """
    b = (base_url or "").rstrip("/")
    if not b:
        raise RuntimeError("base_url 为空")
    url = f"{b}/images/generations"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
        "response_format": "b64_json",
    }

    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        resp = await client.post(url, headers=headers, json=payload)
        # Common on incompatible gateways: 404 on /images/generations
        if resp.status_code == 404:
            raise RuntimeError("当前 base_url 不支持 /images/generations（成图接口）")
        resp.raise_for_status()
        data = resp.json()

        try:
            item = (data.get("data") or [])[0]
        except Exception:
            item = None

        raw_bytes: Optional[bytes] = None
        if isinstance(item, dict):
            for key in ("b64_json", "b64", "base64", "image_base64"):
                if key in item and item.get(key):
                    raw_bytes = base64.b64decode(item[key])
                    break

        if raw_bytes is None and isinstance(item, dict) and item.get("url"):
            im_url = str(item.get("url"))
            r2 = await client.get(im_url)
            r2.raise_for_status()
            raw_bytes = r2.content

        if not raw_bytes:
            raise RuntimeError("成图接口未返回图片数据（b64_json/url）")

        png_bytes = _guess_png(raw_bytes)
        return png_bytes, data

