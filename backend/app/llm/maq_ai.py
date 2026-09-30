import json
import re
from typing import Any
from openai import OpenAI
from app.core.config import settings

class MAQAIClient:
    def __init__(self):
        if not settings.maq_ai_api_key:
            raise RuntimeError("MAQ_AI_API_KEY is not configured")
        self.client = OpenAI(
            base_url=settings.maq_ai_base_url,
            api_key=settings.maq_ai_api_key,
            timeout=settings.maq_ai_timeout_seconds,
        )
        self.model = settings.maq_ai_model

    def chat(self, messages: list[dict[str, str]], temperature: float | None = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=settings.maq_ai_temperature if temperature is None else temperature,
        )
        return response.choices[0].message.content or ""

    def chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        content = self.chat(messages)
        return parse_json_object(content)


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("LLM JSON output must be an object")
        return value
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("MAQ AI response did not contain valid JSON")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("LLM JSON output must be an object")
        return value
