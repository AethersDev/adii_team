"""The real swap for judge.py's fake_model_provider — an OpenAI-backed JudgeProvider.

judge_repair() only requires a callable str -> str (see judge.JudgeProvider).
This module is that callable, backed by a real model instead of canned text.
Nothing in judge.py or scoring.py changes to use it.

Not wired into anything yet: no other module in this directory calls
make_openai_provider(), on purpose. It exists as a proven, ready swap
point for the day a real judge call is actually needed — verified once by
hand against a real API key — kept here so nobody has to rebuild it from
scratch, not because anything currently depends on it.
"""
from __future__ import annotations

import os

from openai import OpenAI

DEFAULT_MODEL = "gpt-4o-mini"


def make_openai_provider(model: str = DEFAULT_MODEL, api_key: str | None = None):
    """Return a JudgeProvider (str -> str) backed by the OpenAI API.

    Reads OPENAI_API_KEY from the environment if api_key is not given.
    """
    client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    def provider(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content

    return provider
