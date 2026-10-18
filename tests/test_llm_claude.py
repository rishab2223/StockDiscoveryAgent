import sys
import types

import pytest
from pydantic import BaseModel

from sda.llm import claude
from sda.llm.claude import CLEAR_COMMAND, _parse, structured_batch  # the real one, before conftest patches it


class Out(BaseModel):
    conclusion: str


class FakeResult:
    def __init__(self, structured_output, subtype="success", result=""):
        self.structured_output = structured_output
        self.subtype = subtype
        self.result = result


class FakeOptions:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def sdk(monkeypatch):
    """A stand-in claude_agent_sdk; `state` records what the code did with it."""
    state = {"connects": 0, "disconnects": 0, "clears": 0, "kept": [], "one_off": [], "options": []}
    behaviour = {"fail_connect": False, "kept_fails_on": set()}

    class FakeClient:
        def __init__(self, options):
            state["options"].append(options)
            self.last = None

        async def connect(self):
            if behaviour["fail_connect"]:
                raise RuntimeError("binary would not start")
            state["connects"] += 1

        async def query(self, prompt, session_id="default"):
            self.last = prompt

        async def receive_response(self):
            if self.last == CLEAR_COMMAND:
                state["clears"] += 1
                return
            if self.last in behaviour["kept_fails_on"]:
                raise RuntimeError("process died")
            state["kept"].append(self.last)
            yield FakeResult({"conclusion": f"kept:{self.last}"})

        async def disconnect(self):
            state["disconnects"] += 1

    async def query(prompt, options):
        state["one_off"].append(prompt)
        if prompt == "bad":
            yield FakeResult(None, subtype="error_max_turns", result="gave up")
        else:
            yield FakeResult({"conclusion": f"oneoff:{prompt}"})

    fake = types.SimpleNamespace(ClaudeSDKClient=FakeClient, ClaudeAgentOptions=FakeOptions, ResultMessage=FakeResult, query=query)
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake)
    monkeypatch.setattr(claude, "_sdk_env", lambda: {})
    return state, behaviour


def test_batch_runs_on_kept_pool_in_order_and_clears_between_calls(sdk):
    state, _ = sdk
    prompts = ["a", "b", "c", "d", "e"]
    out = structured_batch("sys", prompts, Out, model="claude-opus-5-5", effort="low", pool=2)
    assert [o.conclusion for o in out] == [f"kept:{p}" for p in prompts]
    assert state["connects"] == 2 and state["disconnects"] == 2
    assert state["clears"] == 5 and state["one_off"] == []
    options = state["options"][0].kwargs
    assert options["model"] == "claude-opus-5-5" and options["effort"] == "low" and options["system_prompt"] == "sys"
    assert options["tools"] == [] and options["setting_sources"] == []
    assert options["output_format"] == {"type": "json_schema", "schema": Out.model_json_schema()}


def test_pool_never_exceeds_prompt_count_and_empty_batch_starts_nothing(sdk):
    state, _ = sdk
    assert structured_batch("sys", [], Out, pool=4) == []
    assert state["connects"] == 0
    structured_batch("sys", ["only"], Out, pool=4)
    assert state["connects"] == 1


def test_defaults_come_from_config(sdk, monkeypatch):
    state, _ = sdk
    monkeypatch.setattr(claude.config, "CLAUDE_MODEL", "sonnet")
    monkeypatch.setattr(claude.config, "CLAUDE_EFFORT", "high")
    monkeypatch.setattr(claude.config, "CLAUDE_POOL", 3)
    structured_batch("sys", ["a", "b", "c", "d"], Out)
    assert state["connects"] == 3
    assert state["options"][0].kwargs["model"] == "sonnet" and state["options"][0].kwargs["effort"] == "high"


def test_connect_failure_falls_back_to_one_off_calls(sdk):
    state, behaviour = sdk
    behaviour["fail_connect"] = True
    out = structured_batch("sys", ["a", "b"], Out, pool=1)
    assert [o.conclusion for o in out] == ["oneoff:a", "oneoff:b"]
    assert state["one_off"] == ["a", "b"] and state["disconnects"] == 1  # the half-started client


def test_broken_kept_process_is_retired_and_its_share_goes_one_off(sdk):
    state, behaviour = sdk
    behaviour["kept_fails_on"] = {"b"}
    out = structured_batch("sys", ["a", "b", "c"], Out, pool=1)
    assert [o.conclusion for o in out] == ["kept:a", "oneoff:b", "oneoff:c"]
    assert state["kept"] == ["a"] and state["one_off"] == ["b", "c"] and state["disconnects"] == 1


def test_a_failed_one_off_call_comes_back_as_an_exception(sdk):
    _, behaviour = sdk
    behaviour["fail_connect"] = True
    out = structured_batch("sys", ["good", "bad"], Out, pool=1)
    assert out[0].conclusion == "oneoff:good"
    assert isinstance(out[1], RuntimeError) and "error_max_turns" in str(out[1])


def test_parse_rejects_missing_or_unsuccessful_results():
    with pytest.raises(RuntimeError, match="no result message"):
        _parse(None, Out)
    with pytest.raises(RuntimeError, match="no structured output"):
        _parse(FakeResult(None), Out)
    assert _parse(FakeResult({"conclusion": "x"}), Out).conclusion == "x"


def test_token_lookup_skips_registry_when_env_has_it(monkeypatch):
    monkeypatch.setenv(claude.TOKEN_VAR, "from-env")
    assert claude._sdk_env() == {}
    monkeypatch.delenv(claude.TOKEN_VAR)
    monkeypatch.setattr(claude.sys, "platform", "linux")
    assert claude._sdk_env() == {}
