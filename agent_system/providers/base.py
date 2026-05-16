from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    text: str
    usage: dict
    model: str
    raw: dict


class BaseProvider:
    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str],
        timeout: int,
    ) -> LLMResponse:
        raise NotImplementedError
