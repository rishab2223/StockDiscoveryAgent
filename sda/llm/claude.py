"""Structured one-turn calls to Claude through the Claude Agent SDK.

The SDK drives the Claude Code binary it bundles, which signs in the way Claude
Code does: your Claude login, or CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`.
No API key. Same approach as OpportunityExplorerAgent/src/llm_claude.py, whose
measurements (SDK 0.2.148, Oct 2026) drive the design here: a one-off query()
takes ~17 s, nearly all of it the binary starting, while a kept client starts
in ~2 s and then answers in 2-3 s. So a batch runs on a small pool of kept
processes, and anything that goes wrong with one falls back to a one-off call.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from sda import config

T = TypeVar("T", bound=BaseModel)

TOKEN_VAR = "CLAUDE_CODE_OAUTH_TOKEN"
# A fresh session_id per call does not start a fresh conversation; "/clear" does,
# so each prompt is answered on its own (measured in OpportunityExplorerAgent).
CLEAR_COMMAND = "/clear"
CONNECT_TIMEOUT_S = 90
CALL_TIMEOUT_S = 600


def _sdk_env() -> dict[str, str]:
    """The sign-in token for the bundled Claude Code when this process started
    without it. Windows gives a new user variable only to programs started after
    it was set, so a terminal opened earlier misses it and the SDK falls back to
    a saved login that may have expired. Read the user's own setting from where
    Windows keeps it; nothing is stored or logged."""
    if os.environ.get(TOKEN_VAR) or sys.platform != "win32":
        return {}
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            token, _ = winreg.QueryValueEx(key, TOKEN_VAR)
    except OSError:
        return {}
    return {TOKEN_VAR: str(token)} if token else {}


def _neutral_cwd() -> str:
    """An empty folder, so Claude Code does not pick up this repo's .claude settings."""
    path = Path(tempfile.gettempdir()) / "sda_claude_cwd"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _options(system: str, schema: type[BaseModel], model: str, effort: str):
    from claude_agent_sdk import ClaudeAgentOptions

    return ClaudeAgentOptions(
        model=model,
        system_prompt=system,
        tools=[],  # keeps the built-in tool definitions out of every prompt
        allowed_tools=[],
        cwd=_neutral_cwd(),
        setting_sources=[],
        # Structured output arrives through an internal tool call, which can take
        # more than one turn.
        max_turns=4,
        effort=effort,
        output_format={"type": "json_schema", "schema": schema.model_json_schema()},
        env=_sdk_env(),
    )


def _parse(result: Any, schema: type[T]) -> T:
    if result is None:
        raise RuntimeError("Claude Agent SDK returned no result message")
    if result.subtype != "success":
        raise RuntimeError(f"Claude Agent SDK ended with {result.subtype}: {result.result!r}"[:800])
    if not result.structured_output:
        raise RuntimeError(f"Claude Agent SDK returned no structured output: {result.result!r}"[:800])
    return schema.model_validate(result.structured_output)


async def _one_off(prompt: str, options: Any, schema: type[T]) -> T:
    from claude_agent_sdk import ResultMessage, query

    async def collect():
        result = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message
        return result

    return _parse(await asyncio.wait_for(collect(), CALL_TIMEOUT_S), schema)


async def _ask(client: Any, prompt: str) -> Any:
    from claude_agent_sdk import ResultMessage

    session_id = uuid.uuid4().hex
    await client.query(prompt, session_id=session_id)
    result = None
    async for message in client.receive_response():
        if isinstance(message, ResultMessage):
            result = message
    await client.query(CLEAR_COMMAND, session_id=session_id)
    async for _message in client.receive_response():
        pass
    return result


async def _disconnect(client: Any) -> None:
    try:
        await client.disconnect()
    except Exception:
        pass


async def _worker(queue: asyncio.Queue, results: list, options: Any, schema: type[BaseModel]) -> None:
    """One kept Claude Code process answering prompts from the queue. The SDK
    wants connect and disconnect in the same task, so this task owns it."""
    from claude_agent_sdk import ClaudeSDKClient

    client = ClaudeSDKClient(options=options)
    try:
        await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT_S)
    except Exception:
        await _disconnect(client)  # a half-started process too
        client = None
    try:
        while True:
            try:
                index, prompt = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if client is not None:
                try:
                    results[index] = _parse(await asyncio.wait_for(_ask(client, prompt), CALL_TIMEOUT_S), schema)
                    continue
                except Exception:
                    # The process may be in any state now: retire it and answer
                    # this and the rest of this worker's share one-off.
                    await _disconnect(client)
                    client = None
            try:
                results[index] = await _one_off(prompt, options, schema)
            except Exception as exc:
                results[index] = exc
    finally:
        if client is not None:
            await _disconnect(client)


def structured_batch(
    system: str,
    prompts: list[str],
    schema: type[T],
    *,
    model: str | None = None,
    effort: str | None = None,
    pool: int | None = None,
) -> list[T | Exception]:
    """One answer per prompt, in order: a validated `schema` instance, or the
    exception that call ended with. Defaults come from CLAUDE_MODEL,
    CLAUDE_EFFORT and CLAUDE_POOL."""
    if not prompts:
        return []
    options = _options(system, schema, model or config.CLAUDE_MODEL, effort or config.CLAUDE_EFFORT)
    workers = max(1, min(pool or config.CLAUDE_POOL, len(prompts)))

    async def run() -> list:
        queue: asyncio.Queue = asyncio.Queue()
        for item in enumerate(prompts):
            queue.put_nowait(item)
        results: list = [None] * len(prompts)
        await asyncio.gather(*(_worker(queue, results, options, schema) for _ in range(workers)))
        return results

    return asyncio.run(run())
