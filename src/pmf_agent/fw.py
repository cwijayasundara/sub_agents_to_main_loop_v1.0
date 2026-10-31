"""Fireworks model wiring for the folded single-loop agent."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

MODEL_ID = "accounts/fireworks/models/glm-5p3-flash"
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
FIREWORKS_KEY_ENV = "FIREWORKS_API_KEY"

# PLACEHOLDER prices per million tokens — verify against Fireworks pricing
# before trusting cost numbers in eval reports (decision_harness convention).
PRICE_PER_M_INPUT = 0.10
PRICE_PER_M_OUTPUT = 0.50


def chat_model(**overrides) -> ChatOpenAI:
    """ChatOpenAI pointed at the Fireworks OpenAI-compatible endpoint."""
    api_key = os.environ.get(FIREWORKS_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"{FIREWORKS_KEY_ENV} is not set; export it or load it into the environment"
        )
    return ChatOpenAI(
        model=MODEL_ID,
        base_url=FIREWORKS_BASE_URL,
        api_key=api_key,
        **overrides,
    )


def estimate_cost_usd(tokens_in: int, tokens_out: int) -> float:
    """Placeholder cost estimate from the placeholder prices above."""
    return tokens_in / 1e6 * PRICE_PER_M_INPUT + tokens_out / 1e6 * PRICE_PER_M_OUTPUT
