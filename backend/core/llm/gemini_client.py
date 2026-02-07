import os
import json
import httpx
import logging
from typing import Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Direct client for Google Gemini API.
    Uses HTTP REST API to avoid conflict with other SDK versions.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        # Fallback to main LLM key if it looks like a Gemini key (starts with AIza)
        if not self.api_key and settings.LLM_API_KEY.startswith("AIza"):
            self.api_key = settings.LLM_API_KEY

        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "models/gemini-1.5-pro" # Use 1.5 Pro for better context understanding

    async def generate_json(self, prompt: str, system_instruction: str = "") -> Dict[str, Any]:
        """
        Generate structured JSON from text using Gemini.
        """
        if not self.api_key:
            raise ValueError("Gemini API Key is missing. Please configure GEMINI_API_KEY.")

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

        headers = {
            "Content-Type": "application/json"
        }

        # Construct payload with system instruction and JSON enforcement
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # Extract text from response
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Gemini returned no candidates")

                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if not text:
                    raise RuntimeError("Gemini returned empty text")

                # Parse JSON
                return json.loads(text)

            except httpx.HTTPStatusError as e:
                logger.error(f"Gemini API Error: {e.response.text}")
                raise RuntimeError(f"Gemini API Error: {e.response.status_code}")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Gemini JSON: {text}")
                raise RuntimeError("Gemini output was not valid JSON")
            except Exception as e:
                logger.error(f"Gemini Client Error: {str(e)}")
                raise

    async def generate_text(self, prompt: str) -> str:
        """
        Generate raw text content using Gemini.
        """
        if not self.api_key:
            raise ValueError("Gemini API Key is missing.")

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3}
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("candidates", [])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            except Exception as e:
                logger.error(f"Gemini Text Generation Error: {str(e)}")
                raise
