"""LLM 调用统一入口 — 根据 model 名前缀路由到对应 Provider。

Mate 调用 LLMClient.chat(model="deepseek-chat", ...) 即可,
不用关心是哪个 provider。新增 provider 只需扩展 PREFIX_MAP 和 self.providers。
"""
import time
from typing import Optional
from agent_system.providers.base import LLMResponse, BaseProvider

class LLMClient:
    """根据 model 名前缀分发调用,带统一的重试/超时/默认参数。"""

    # model 名前缀 → provider 名映射,新增 provider 时在这里加
    PREFIX_MAP = {
        "deepseek-": "deepseek",
        "claude-": "claude",
        "gpt-": "openai",
    }

    def __init__(self, cfg: dict, providers: dict[str, BaseProvider]):
        """providers 是 {provider_name: BaseProvider 实例} 的 dict。

        通常在 cli/start.py 里组装好后传入。
        """
        self.cfg = cfg
        self.providers = providers

    def _provider_name_for_model(self, model: str) -> str:
        """根据 model 名前缀找 provider 名。"""
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
        """发起一次 chat completion。

        - 没传的参数从 cfg.defaults 里取兜底值
        - 失败按 retry_max 自动指数退避重试(2^n 秒)
        - 重试用尽仍失败时抛出最后一次的异常
        """
        # 把 None 参数从 defaults 兜底,确保 provider 拿到完整参数
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

        # 重试循环:retry_max=2 表示最多调 3 次(初次 + 2 次重试)
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
                    # 指数退避: 1s, 2s, 4s ...
                    time.sleep(2 ** attempt)
        raise last_err
