import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from agent_workbench.core.agent_loop import run
from agent_workbench.core.budgets import Budgets
from agent_workbench.core.session import Session
from agent_workbench.providers.adapter import ScriptedProvider, ToolCall, Turn
from agent_workbench.storage.sqlite import EventStore
from agent_workbench.tools.permissions import Approval, Policy, argument_digest
from agent_workbench.tools.registry import Tool, builtins
from agent_workbench.tools.schemas import CalculateInput, CalculateOutput


def call(id: str = "one", **changes: Any) -> ToolCall:
    return ToolCall(
        id=id,
        tool="calculate",
        arguments={"operation": "multiply", "left": 6.0, "right": 7.0, **changes},
    )


async def execute(tmp_path: Path, calls: list[ToolCall], **kwargs: Any) -> Any:
    return await run(
        ScriptedProvider([Turn(calls=calls), Turn(text="done")]),
        builtins(tmp_path),
        Policy(frozenset({"calculate", "read_document"})),
        "private prompt",
        **kwargs,
    )


async def test_tool_result_reaches_provider_and_stream(tmp_path: Path) -> None:
    seen = []

    class Provider:
        async def respond(self, messages: Any, tools: Any, max_tokens: int) -> Turn:
            assert [t["function"]["name"] for t in tools] == ["calculate"]
            if messages[-1]["role"] == "tool":
                assert json.loads(messages[-1]["content"]) == {"value": 42.0}
                return Turn(text="42")
            return Turn(calls=[call()])

    result = await run(
        Provider(),
        builtins(tmp_path),
        Policy(frozenset({"calculate"})),
        "6*7",
        on_event=seen.append,
    )
    assert result.status == "completed" and result.text == "42"
    assert tuple(seen) == result.events


@pytest.mark.parametrize(
    "arguments",
    [
        {"left": "6"},
        {"left": float("inf")},
        {"extra": True},
        {"operation": "eval"},
    ],
)
async def test_malformed(tmp_path: Path, arguments: Any) -> None:
    assert (await execute(tmp_path, [call(**arguments)])).code == "invalid_arguments"


async def test_input_approval_and_idempotency(tmp_path: Path) -> None:
    registry = builtins(tmp_path)
    effects = []

    async def effect(args: CalculateInput) -> CalculateOutput:
        effects.append(args)
        return CalculateOutput(value=42.0)

    registry.register(
        Tool("write", "Test side effect", CalculateInput, CalculateOutput, effect, side_effect=True)
    )
    request = call().model_copy(update={"tool": "write"})
    state = Session()
    # Normalize arguments exactly as runtime does, before approval.
    digest = argument_digest(CalculateInput.model_validate(request.arguments).model_dump())
    approval = Approval(state.run_id, "one", "write", digest, "Reviewed exact arguments")

    def provider() -> ScriptedProvider:
        return ScriptedProvider([Turn(calls=[request, request]), Turn(text="ok")])

    denied = await run(provider(), registry, Policy(frozenset({"write"})), "x")
    assert denied.code == "approval_required" and not effects
    assert denied.events[-2].name == "approval.denied"
    allowed = await run(
        provider(), registry, Policy(frozenset({"write"}), (approval,)), "x", session=state
    )
    assert allowed.status == "completed" and len(effects) == 1
    assert any(e.name == "tool.reused" for e in allowed.events)
    # Same approval cannot be moved into a new run.
    denied = await run(provider(), registry, Policy(frozenset({"write"}), (approval,)), "x")
    assert denied.code == "approval_required" and len(effects) == 1


async def test_changed_arguments_cannot_reuse_approval(tmp_path: Path) -> None:
    registry = builtins(tmp_path)

    async def forbidden(args: CalculateInput) -> CalculateOutput:
        pytest.fail("side effect executed")

    registry.register(Tool("write", "test", CalculateInput, CalculateOutput, forbidden, True))
    state = Session()
    original = call()
    approval = Approval(state.run_id, "one", "write", argument_digest(original.arguments), "ok")
    altered = call(left=8.0).model_copy(update={"tool": "write"})
    result = await run(
        ScriptedProvider([Turn(calls=[altered])]),
        registry,
        Policy(frozenset({"write"}), (approval,)),
        "x",
        session=state,
    )
    assert result.code == "approval_required"


async def test_idempotency_conflict(tmp_path: Path) -> None:
    result = await execute(tmp_path, [call(), call(left=4.0)])
    assert result.code == "idempotency_conflict"


async def test_step_budget(tmp_path: Path) -> None:
    result = await run(
        ScriptedProvider([Turn(calls=[call()])] * 5),
        builtins(tmp_path),
        Policy(frozenset({"calculate"})),
        "loop",
        Budgets(max_steps=2),
    )
    assert result.code == "step_budget"


async def test_token_budget_prevents_tool_execution(tmp_path: Path) -> None:
    result = await run(
        ScriptedProvider([Turn(calls=[call()], output_tokens=11)]),
        builtins(tmp_path),
        Policy(frozenset({"calculate"})),
        "x",
        Budgets(max_output_tokens=10),
    )
    assert result.code == "token_budget"
    assert not any(e.name == "tool.completed" for e in result.events)


class SlowProvider:
    async def respond(self, *args: Any) -> Turn:
        await asyncio.sleep(10)
        return Turn(text="late")


async def test_timeout(tmp_path: Path) -> None:
    result = await run(
        SlowProvider(), builtins(tmp_path), Policy(frozenset()), "x", Budgets(timeout_seconds=0.01)
    )
    assert result.code == "timeout"


async def test_cancellation_during_provider(tmp_path: Path) -> None:
    state = Session()
    task = asyncio.create_task(
        run(SlowProvider(), builtins(tmp_path), Policy(frozenset()), "x", session=state)
    )
    await asyncio.sleep(0.01)
    state.cancel()
    result = await asyncio.wait_for(task, 1)
    assert result.status == "cancelled"


async def test_external_task_cancellation(tmp_path: Path) -> None:
    state = Session()
    task = asyncio.create_task(
        run(SlowProvider(), builtins(tmp_path), Policy(frozenset()), "x", session=state)
    )
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert state.events[-1].name == "run.cancelled"


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "a/../../secret", "a\\b", "./a"])
async def test_read_scope(tmp_path: Path, path: str) -> None:
    result = await execute(
        tmp_path, [ToolCall(id="r", tool="read_document", arguments={"path": path})]
    )
    assert result.code == "tool_failed"


async def test_symlink_and_document_limit(tmp_path: Path) -> None:
    (tmp_path / "escape").symlink_to("/etc/passwd")
    (tmp_path / "folder").symlink_to("/etc", target_is_directory=True)
    (tmp_path / "large").write_text("x" * 8193)
    for name in ["escape", "folder/passwd", "large"]:
        assert (
            await execute(
                tmp_path, [ToolCall(id="r", tool="read_document", arguments={"path": name})]
            )
        ).code == "tool_failed"


async def test_document_and_replay_private(tmp_path: Path) -> None:
    (tmp_path / "doc").write_text("PRIVATE document contents")
    with EventStore(tmp_path / "events.db") as store:
        result = await execute(
            tmp_path,
            [ToolCall(id="r", tool="read_document", arguments={"path": "doc"})],
            store=store,
        )
        assert result.status == "completed"
        assert store.replay(result.run_id) == list(result.events)
        assert store.replay("' OR 1=1 --") == []
    data = (tmp_path / "events.db").read_bytes()
    assert b"PRIVATE" not in data and b"private prompt" not in data


async def test_permissions(tmp_path: Path) -> None:
    result = await run(
        ScriptedProvider([Turn(calls=[call()])]), builtins(tmp_path), Policy(frozenset()), "x"
    )
    assert result.code == "tool_forbidden"


async def test_schema_validation_of_output(tmp_path: Path) -> None:
    registry = builtins(tmp_path)

    async def broken(args: CalculateInput) -> BaseModel:
        return CalculateInput(operation="add", left=0.0, right=0.0)

    registry.tools["calculate"] = Tool("calculate", "bad", CalculateInput, CalculateOutput, broken)
    result = await run(
        ScriptedProvider([Turn(calls=[call()])]), registry, Policy(frozenset({"calculate"})), "x"
    )
    assert result.code == "invalid_output"


async def test_no_exception_payload_leak(tmp_path: Path) -> None:
    class Broken:
        async def respond(self, *args: Any) -> Turn:
            raise RuntimeError("SECRET provider exception")

    result = await run(Broken(), builtins(tmp_path), Policy(frozenset()), "SECRET input")
    assert result.code == "provider_failed"
    assert "SECRET" not in str(result)


async def test_concurrent_isolation(tmp_path: Path) -> None:
    results = await asyncio.gather(*[execute(tmp_path, [call()]) for _ in range(5)])
    assert len({r.run_id for r in results}) == 5
    assert all(r.status == "completed" for r in results)
    assert all(sum(e.name == "tool.completed" for e in r.events) == 1 for r in results)


async def test_session_reuse_rejected(tmp_path: Path) -> None:
    state = Session()
    await execute(tmp_path, [], session=state)
    with pytest.raises(ValueError, match="session_already_started"):
        await execute(tmp_path, [], session=state)


async def test_cancellation_during_tool(tmp_path: Path) -> None:
    registry = builtins(tmp_path)
    entered = asyncio.Event()
    stopped = asyncio.Event()

    async def slow(args: CalculateInput) -> CalculateOutput:
        entered.set()
        try:
            await asyncio.sleep(30)
        finally:
            stopped.set()
        return CalculateOutput(value=0.0)

    registry.tools["calculate"] = Tool("calculate", "slow", CalculateInput, CalculateOutput, slow)
    state = Session()
    task = asyncio.create_task(
        run(
            ScriptedProvider([Turn(calls=[call()])]),
            registry,
            Policy(frozenset({"calculate"})),
            "x",
            session=state,
        )
    )
    await asyncio.wait_for(entered.wait(), 1)
    state.cancel()
    assert (await asyncio.wait_for(task, 1)).status == "cancelled"
    assert stopped.is_set()


async def test_result_size_budget(tmp_path: Path) -> None:
    (tmp_path / "doc").write_text("a" * 256)
    result = await execute(
        tmp_path,
        [ToolCall(id="r", tool="read_document", arguments={"path": "doc"})],
        budgets=Budgets(max_result_bytes=128),
    )
    assert result.code == "result_budget"


async def test_empty_token_budget_before_next_turn(tmp_path: Path) -> None:
    result = await run(
        ScriptedProvider([Turn(calls=[call()], output_tokens=10)]),
        builtins(tmp_path),
        Policy(frozenset({"calculate"})),
        "x",
        Budgets(max_output_tokens=10),
    )
    assert result.code == "token_budget"


async def test_unknown_tool(tmp_path: Path) -> None:
    result = await run(
        ScriptedProvider([Turn(calls=[call().model_copy(update={"tool": "unknown"})])]),
        builtins(tmp_path),
        Policy(frozenset({"unknown"})),
        "x",
    )
    assert result.code == "unknown_tool"


@pytest.mark.parametrize(
    "operation,left,right,expected",
    [("add", 4.0, 2.0, 6.0), ("subtract", 4.0, 2.0, 2.0), ("divide", 4.0, 2.0, 2.0)],
)
async def test_arithmetic(
    tmp_path: Path, operation: str, left: float, right: float, expected: float
) -> None:
    tool = builtins(tmp_path).tools["calculate"]
    result = await tool.execute(CalculateInput(operation=operation, left=left, right=right))
    assert result.value == expected


async def test_division_zero(tmp_path: Path) -> None:
    assert (await execute(tmp_path, [call(operation="divide", right=0.0)])).code == "tool_failed"


async def test_model_call_id_not_logged_verbatim(tmp_path: Path) -> None:
    result = await execute(tmp_path, [call(id="PRIVATE provider-chosen identifier")])
    assert result.status == "completed"
    assert "PRIVATE" not in str(result.events)
