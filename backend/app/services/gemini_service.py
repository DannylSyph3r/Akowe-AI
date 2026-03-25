import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("akoweai")


class GeminiFlashClient:
    """
    Thin wrapper around Gemini Flash for intent classification.
    Single-turn: one prompt in, one JSON response out.
    Includes retry logic (max 2 retries) on transient errors.
    """

    def __init__(self):
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = "gemini-2.0-flash"

    def _classify_sync(self, text: str, system_prompt: str) -> dict:
        last_error = None
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=text,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                    ),
                )
                raw = response.text.strip()
                # Strip markdown code fences if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                return json.loads(raw.strip())
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    continue
        logger.warning("GeminiFlash classify failed after retries: %s", last_error)
        return {}

    async def classify_intent(self, text: str, system_prompt: str) -> dict:
        """Async wrapper — runs sync SDK call in a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(self._classify_sync, text, system_prompt)


class GeminiProClient:
    """
    Thin wrapper around Gemini Pro for financial summaries and coop insights.
    Single-turn: context string in, prose response out.
    """

    def __init__(self):
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = "gemini-2.0-pro-exp"

    def _summarise_sync(self, context: str, system_prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=context,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            logger.warning("GeminiPro generate_summary failed: %s", exc)
            return "Summary temporarily unavailable."

    async def generate_summary(self, context: str, system_prompt: str) -> str:
        """Async wrapper — runs sync SDK call in a thread."""
        return await asyncio.to_thread(self._summarise_sync, context, system_prompt)