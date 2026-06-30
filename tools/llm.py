"""
LLM client — supports xAI Grok (primary) and OpenAI (fallback).
Set XAI_API_KEY for Grok, or OPENAI_API_KEY for GPT fallback.
"""

import os
import json
from openai import OpenAI

_client: OpenAI | None = None


def _get_secret(key: str) -> str | None:
    """Read from env first, then Streamlit secrets (for cloud deployment)."""
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


def get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client

    xai_key = _get_secret("XAI_API_KEY")
    oai_key = _get_secret("OPENAI_API_KEY")

    if xai_key:
        _client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
    elif oai_key:
        _client = OpenAI(api_key=oai_key)
    else:
        raise RuntimeError(
            "No LLM API key found. Set XAI_API_KEY in your .env file or Streamlit secrets."
        )

    return _client


def get_model() -> str:
    if _get_secret("XAI_API_KEY"):
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
