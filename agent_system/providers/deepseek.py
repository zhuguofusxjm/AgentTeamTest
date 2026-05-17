import requests

from .base import BaseProvider, LLMResponse


class DeepSeekProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def chat(self, model, messages, temperature, max_tokens, response_format, timeout):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
                "prompt_cache_hit_tokens": data.get("usage", {}).get("prompt_cache_hit_tokens", 0),
                "prompt_cache_miss_tokens": data.get("usage", {}).get("prompt_cache_miss_tokens", 0),
            },
            model=model,
            raw=data,
        )
