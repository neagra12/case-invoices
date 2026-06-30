"""
LLM client — supports xAI Grok (primary) and OpenAI (fallback).
Set XAI_API_KEY for Grok, or OPENAI_API_KEY for GPT fallback.
"""

import os
import json
from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    xai_key = os.environ.get("XAI_API_KEY")
    oai_key = os.environ.get("OPENAI_API_KEY")

    if xai_key:
        _client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
    elif oai_key:
        _client = OpenAI(api_key=oai_key)
    else:
        raise RuntimeError(
            "No LLM API key found. Set XAI_API_KEY (Grok) or OPENAI_API_KEY in your .env file."
        )

    return _client


def get_model() -> str:
    if os.environ.get("XAI_API_KEY"):
        return "grok-3"
    return os.environ.get("OPENAI_MODEL", "gpt-4o")


def chat(messages: list[dict], json_mode: bool = False, temperature: float = 0.1) -> str:
    """Single chat completion call. Returns the assistant message content."""
    client = get_client()
    model = get_model()

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def chat_json(messages: list[dict], temperature: float = 0.1) -> dict:
    """Chat completion that always returns parsed JSON."""
    raw = chat(messages, json_mode=True, temperature=temperature)
    return json.loads(raw)
