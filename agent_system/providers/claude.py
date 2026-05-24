"""Claude provider 占位 — 第一阶段不接,实例化即抛 NotImplementedError。"""
from .base import BaseProvider


class ClaudeProvider(BaseProvider):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Claude provider 第一阶段不接")
