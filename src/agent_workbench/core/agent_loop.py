import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from agent_workbench.core.budgets import Budgets
from agent_workbench.core.events import Event, EventName
from agent_workbench.core.session import Session
from agent_workbench.providers.adapter import Provider
from agent_workbench.storage.sqlite import EventStore
from agent_workbench.tools.permissions import Policy, argument_digest
from agent_workbench.tools.registry import Registry


class RunError(Exception):
    pass


@dataclass(frozen=True)
class Result:
    run_id: str
    status: str
    text: str
    code: str | None
    events: tuple[Event, ...]


async def run(
    provider: Provider,
    registry: Registry,
    policy: Policy,
    prompt: str,
    budgets: Budgets | None = None,
    session: Session | None = None,
    store: EventStore | None = None,
    on_event: Callable[[Event], None] | None = None,
) -> Result:
    budget = budgets or Budgets()
    state = session or Session()
    if state.started:
        raise ValueError("session_already_started")
    state.started = True

    def emit(
        name: EventName,
        *,
        tool: str | None = None,
        call_id: str | None = None,
        digest: str | None = None,
        code: str | None = None,
    ) -> None:
        event = Event(
            run_id=state.run_id,
            sequence=len(state.events),
            name=name,
            tool=tool,
            call_id=(hashlib.sha256(call_id.encode()).hexdigest() if call_id else None),
            argument_digest=digest,
            code=code,
        )
        if store:
            store.append(event)
        state.events.append(event)
        if on_event:
            on_event(event)

    async def execute() -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        # Scoped to this session. No automatic retries or cross-process exactly-once claim.
        cache: dict[str, tuple[str, str, str]] = {}
        used = 0
        for _ in range(budget.max_steps):
            if state.cancelled.is_set():
                raise RunError("cancelled")
            remaining = budget.max_output_tokens - used
            if remaining <= 0:
                raise RunError("token_budget")
            turn = await provider.respond(
                messages, registry.schemas(policy.allowed_tools), remaining
            )
            used += turn.output_tokens
            if used > budget.max_output_tokens:
                raise RunError("token_budget")
            emit("provider.completed")
            if not turn.calls:
                return turn.text
            messages.append(
                {
                    "role": "assistant",
                    "content": turn.text,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.tool, "arguments": c.arguments},
                        }
                        for c in turn.calls
                    ],
                }
            )
            for call in turn.calls:
                if state.cancelled.is_set():
                    raise RunError("cancelled")
                if call.tool not in policy.allowed_tools:
                    raise RunError("tool_forbidden")
                tool = registry.tools.get(call.tool)
                if tool is None:
                    raise RunError("unknown_tool")
                try:
                    args = tool.input_model.model_validate(call.arguments)
                    digest = argument_digest(args.model_dump())
                except (ValidationError, ValueError):
                    raise RunError("invalid_arguments") from None
                cached = cache.get(call.id)
                if cached:
                    if cached[:2] != (call.tool, digest):
                        raise RunError("idempotency_conflict")
                    encoded = cached[2]
                    emit("tool.reused", tool=call.tool, call_id=call.id, digest=digest)
                else:
                    if tool.side_effect:
                        approved = policy.approved(state.run_id, call.id, call.tool, digest)
                        emit(
                            "approval.granted" if approved else "approval.denied",
                            tool=call.tool,
                            call_id=call.id,
                            digest=digest,
                            code="operator_approved" if approved else "approval_required",
                        )
                        if not approved:
                            raise RunError("approval_required")
                    try:
                        raw = await tool.execute(args)
                        output = tool.output_model.model_validate(raw.model_dump())
                        encoded = json.dumps(output.model_dump(), allow_nan=False)
                    except ValidationError:
                        raise RunError("invalid_output") from None
                    except Exception:
                        raise RunError("tool_failed") from None
                    if len(encoded.encode()) > budget.max_result_bytes:
                        raise RunError("result_budget")
                    cache[call.id] = (call.tool, digest, encoded)
                    emit("tool.completed", tool=call.tool, call_id=call.id, digest=digest)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "tool_name": call.tool,
                        "content": encoded,
                    }
                )
        raise RunError("step_budget")

    emit("run.started")
    worker = asyncio.create_task(execute())
    cancellation = asyncio.create_task(state.cancelled.wait())
    try:
        async with asyncio.timeout(budget.timeout_seconds):
            done, _ = await asyncio.wait(
                {worker, cancellation}, return_when=asyncio.FIRST_COMPLETED
            )
            if cancellation in done:
                raise RunError("cancelled")
            answer = await worker
        emit("run.completed")
        return Result(state.run_id, "completed", answer, None, tuple(state.events))
    except asyncio.CancelledError:
        emit("run.cancelled", code="cancelled")
        raise
    except Exception as error:
        code = (
            str(error)
            if isinstance(error, RunError)
            else "timeout"
            if isinstance(error, TimeoutError)
            else "provider_failed"
        )
        emit("run.cancelled" if code == "cancelled" else "run.failed", code=code)
        return Result(
            state.run_id,
            "cancelled" if code == "cancelled" else "failed",
            "",
            code,
            tuple(state.events),
        )
    finally:
        worker.cancel()
        cancellation.cancel()
        await asyncio.gather(worker, cancellation, return_exceptions=True)
