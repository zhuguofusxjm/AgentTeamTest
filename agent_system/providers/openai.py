from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("OpenAI provider 第一阶段不接")
