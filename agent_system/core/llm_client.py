import time
from typing import Optional
from agent_system.providers.base import LLMResponse, BaseProvider

class LLMClient:
    PREFIX_MAP = {
        "deepseek-": "deepseek",
        "claude-": "claude",
        "gpt-": "openai",
    }

    def __init__(self, cfg: dict, providers: dict[str, BaseProvider]):
        self.cfg = cfg
        self.providers = providers

    def _provider_name_for_model(self, model: str) -> str:
        for prefix, name in self.PREFIX_MAP.items():
            if model.startswith(prefix):
                return name
        raise ValueError(f"No provider matches model '{model}'")

    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = None,
        max_tokens: int = None,
        response_format: Optional[str] = None,
        timeout: int = None,
    ) -> LLMResponse:
        defaults = self.cfg.get("defaults", {})
        if temperature is None:
            temperature = defaults.get("temperature", 0.3)
        if max_tokens is None:
            max_tokens = defaults.get("max_tokens", 2000)
        if timeout is None:
            timeout = defaults.get("timeout_sec", 30)
        retry_max = defaults.get("retry_max", 2)

        provider_name = self._provider_name_for_model(model)
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Provider '{provider_name}' not initialized")

        last_err = None
        for attempt in range(retry_max + 1):
            try:
                return provider.chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout=timeout,
                )
            except Exception as e:
                last_err = e
                if attempt < retry_max:
                    time.sleep(2 ** attempt)
        raise last_err
