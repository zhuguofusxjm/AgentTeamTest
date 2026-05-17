import json
import pytest
from agent_system.mates.base import BaseMate
from agent_system.providers.base import LLMResponse

def test_render_prompt_replaces_placeholders(tmp_path):
    prompts_dir = tmp_path / "prompts"
    shared = prompts_dir / "_shared"
    shared.mkdir(parents=True)
    (shared / "output_schema.md").write_text("SCHEMA")
    (shared / "data_pack_format.md").write_text("DATAFMT")
    (shared / "role_persona.md").write_text("PERSONA")
    (prompts_dir / "test_mate.md").write_text(
        "{{ role_persona }}\n{{ data_pack_format }}\n{{ output_schema }}\n{{ data_pack_json }}\n"
    )

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{"view":"多","confidence":50,"evidence":["e"]}',
                               usage={"total_tokens": 1}, model="deepseek-chat", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "temperature": 0.2, "max_tokens": 1000, "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    rendered = mate.render_prompt({"symbol": "ETH", "tags": []})
    assert "PERSONA" in rendered
    assert "DATAFMT" in rendered
    assert "SCHEMA" in rendered
    assert '"symbol": "ETH"' in rendered

def test_run_returns_parsed_json(tmp_path):
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("{{ data_pack_json }}")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{"view":"多","confidence":75,"evidence":["a"]}',
                               usage={"total_tokens": 1}, model="deepseek-chat", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "temperature": 0.2, "max_tokens": 1000, "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    result = mate.run({"symbol": "ETH"})
    assert result["view"] == "多"
    assert result["confidence"] == 75
    assert result["mate"] == "test_mate"

def test_run_handles_invalid_json(tmp_path):
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("X")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text="not json", usage={}, model="deepseek-chat", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    result = mate.run({"symbol": "ETH"})
    assert result["view"] == "观望"
    assert result["confidence"] == 0
    assert "_error" in result

def test_run_handles_llm_exception(tmp_path):
    """LLM 调用抛异常时, 应降级为 fallback dict 且不向上抛异常"""
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("X")

    class FailingLLM:
        def chat(self, **kw):
            raise ConnectionError("boom")

    mate = BaseMate(
        name="test_mate",
        llm_client=FailingLLM(),
        mate_cfg={"model": "deepseek-chat", "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    result = mate.run({"symbol": "ETH"})
    assert result["mate"] == "test_mate"
    assert result["view"] == "观望"
    assert result["confidence"] == 0
    assert "_error" in result
    assert "boom" in result["_error"]

def test_run_writes_audit_when_logger_provided(tmp_path):
    """audit_logger + audit_id 都给时,应调 log_call"""
    from unittest.mock import MagicMock
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("X")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{"view":"多","confidence":50,"evidence":["e"]}',
                               usage={"total_tokens": 10}, model="deepseek-chat", raw={})

    audit = MagicMock()
    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    mate.run({"symbol": "ETH"}, audit_logger=audit, audit_id="aid-1", round_num=2)
    audit.log_call.assert_called_once()
    call_kwargs = audit.log_call.call_args.kwargs
    assert call_kwargs["audit_id"] == "aid-1"
    assert call_kwargs["round_num"] == 2
    assert call_kwargs["mate"] == "test_mate"

def test_run_handles_render_exception(tmp_path):
    """prompt_file 不存在时, render 异常应降级"""
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{}', usage={}, model="x", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "prompt_file": "prompts/nonexistent.md"},
        prompts_dir=str(prompts_dir),
    )
    result = mate.run({"symbol": "ETH"})
    assert result["mate"] == "test_mate"
    assert result["view"] == "观望"
    assert result["confidence"] == 0
    assert "_error" in result
    assert "render failed" in result["_error"]


def _make_mate(tmp_path, cls=BaseMate):
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("DATA={{ data_pack_json }}")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{"view":"多","confidence":50,"evidence":["e"]}',
                               usage={"total_tokens": 1}, model="deepseek-chat", raw={})

    return cls(name="test_mate", llm_client=MockLLM(),
               mate_cfg={"model": "deepseek-chat", "prompt_file": "prompts/test_mate.md"},
               prompts_dir=str(prompts_dir))


def test_select_fields_default_returns_full_pack(tmp_path):
    mate = _make_mate(tmp_path)
    pack = {"symbol": "ETH", "tags": [], "klines": {"1h": [{"close": 1}]},
            "funding": {"current": 0.001}, "huge_field": list(range(100))}
    rendered = mate.render_prompt(pack)
    assert "huge_field" in rendered
    assert "klines" in rendered


def test_select_fields_override_drops_unwanted(tmp_path):
    """子类只挑自己要的字段,渲染出的 prompt 只含切片后的内容"""
    class SlimMate(BaseMate):
        def select_fields(self, data_pack):
            return {"symbol": data_pack.get("symbol"),
                    "funding": data_pack.get("funding")}

    mate = _make_mate(tmp_path, cls=SlimMate)
    pack = {"symbol": "ETH", "tags": ["t1"],
            "klines": {"1h": [{"close": 1}]},
            "funding": {"current": 0.001},
            "huge_field": list(range(100))}
    rendered = mate.render_prompt(pack)
    assert '"symbol": "ETH"' in rendered
    assert "funding" in rendered
    # 切片后的字段不应出现
    assert "huge_field" not in rendered
    assert "klines" not in rendered


def test_render_uses_sort_keys_for_cache_stability(tmp_path):
    """同样的 data_pack 不同顺序传入,渲染结果应一致 (有利于 prompt cache)"""
    mate = _make_mate(tmp_path)
    pack_a = {"symbol": "ETH", "funding": {"a": 1, "b": 2}, "tags": ["x"]}
    pack_b = {"tags": ["x"], "symbol": "ETH", "funding": {"b": 2, "a": 1}}
    assert mate.render_prompt(pack_a) == mate.render_prompt(pack_b)
