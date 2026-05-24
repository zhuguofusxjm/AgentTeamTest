"""DeepSeek API 封装。

DeepSeek 兼容 OpenAI chat completions 协议,只需把 base_url 指过去,
所以这层非常薄。重点是 usage 字段额外暴露了 prompt cache 命中数据。
"""
import requests

from .base import BaseProvider, LLMResponse


class DeepSeekProvider(BaseProvider):
    """通过 HTTP POST 调 /chat/completions。"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")  # 去掉尾部 / 防双斜杠

    def chat(self, model, messages, temperature, max_tokens, response_format, timeout):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # JSON 模式:DeepSeek 用 response_format={"type": "json_object"},约束输出必须是合法 JSON
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()  # 4xx/5xx 抛异常,由 LLMClient 重试或上抛
        data = r.json()
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
                # DeepSeek 特有:prompt cache 命中/未命中字节数,用于计算实际成本
                "prompt_cache_hit_tokens": data.get("usage", {}).get("prompt_cache_hit_tokens", 0),
                "prompt_cache_miss_tokens": data.get("usage", {}).get("prompt_cache_miss_tokens", 0),
            },
            model=model,
            raw=data,
        )
