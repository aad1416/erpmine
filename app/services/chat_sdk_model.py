"""Heuristics for when the chat message path uses OpenAI Agents SDK vs legacy ChatService."""

from __future__ import annotations


def supports_openai_agents_sdk(model_name: str) -> bool:
    """
    OpenAI Agents SDK path is built around OpenAI models.
    Other providers continue to use LangChain via legacy ChatService.
    """
    if not model_name:
        return False
    n = model_name.strip().lower()
    return n.startswith("gpt-") or n.startswith("o1") or n.startswith("o3") or n.startswith("o4")
