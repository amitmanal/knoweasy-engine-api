"""
providers/base.py

Track-B: Provider abstraction (Gemini now, OpenAI/Claude later).
This is intentionally lightweight to keep Phase-1 stable.

Public contract:
- Provider.generate_json(prompt, timeout_s) -> dict
- Provider.name (str)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Protocol


class Provider(Protocol):
    name: str
    def generate_json(self, prompt: str, timeout_s: int) -> Dict[str, Any]:
        ...


@dataclass(frozen=True)
class ProviderError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message
