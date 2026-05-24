"""LLM Provider 抽象层。

子类(DeepSeekProvider / ClaudeProvider / OpenAIProvider)各自封装具体厂商的 HTTP API,
LLMClient 根据 model 名前缀分发到对应 provider。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """LLM 调用统一返回结构。

    text: 模型输出的文本(已从 choices[0] 抽出)
    usage: token 消耗 dict(prompt/completion/total/cache 等,各 provider 字段不一样,但 key 名统一)
    model: 实际使用的 model 名(可能与请求的不同,例如 alias)
    raw: 原始 API 响应,留作调试/审计
    """
    text: str
    usage: dict
    model: str
    raw: dict


class BaseProvider:
    """Provider 接口。子类必须实现 chat()。"""

    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str],
        timeout: int,
    ) -> LLMResponse:
        """发起一次 chat completion。

        参数和 OpenAI/DeepSeek 风格对齐。各 provider 自行翻译为本地 API 字段。
        response_format='json' 表示要求 JSON 模式输出(强制约束,不再需要 prompt 兜 JSON)。
        """
        raise NotImplementedError
