from __future__ import annotations

from langchain_openai import ChatOpenAI

from .settings import CommonSettings, MissingConfigurationError


def build_chat_model(
    settings: CommonSettings,
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> ChatOpenAI:
    if not settings.openrouter_api_key:
        raise MissingConfigurationError("OPENROUTER_API_KEY is required for LLM nodes.")

    return ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=model or settings.openrouter_text_model,
        temperature=settings.default_temperature if temperature is None else temperature,
        default_headers={
            "HTTP-Referer": "https://github.com/openai/codex",
            "X-Title": "ResearchTool LangGraph Pipelines",
        },
    )
