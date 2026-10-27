"""Run from the repository root: python examples/approval.py.

A harmless in-memory side effect illustrates authorization; no files or network writes.
"""

import asyncio
from pathlib import Path

from agent_workbench.core.agent_loop import run
from agent_workbench.core.session import Session
from agent_workbench.providers.adapter import ScriptedProvider, ToolCall, Turn
from agent_workbench.tools.permissions import Approval, Policy, argument_digest
from agent_workbench.tools.registry import Tool, builtins
from agent_workbench.tools.schemas import CalculateInput, CalculateOutput


async def main() -> None:
    recorded: list[float] = []

    async def record(args: CalculateInput) -> CalculateOutput:
        value = args.left + args.right
        recorded.append(value)
        return CalculateOutput(value=value)

    registry = builtins(Path("examples/documents"))
    registry.register(
        Tool(
            "record",
            "Append to a local in-memory list.",
            CalculateInput,
            CalculateOutput,
            record,
            side_effect=True,
        )
    )
    state = Session()
    args = CalculateInput(operation="add", left=1.0, right=2.0).model_dump()
    approval = Approval(
        state.run_id,
        "record-1",
        "record",
        argument_digest(args),
        "Operator reviewed: append 1 + 2 to this example's in-memory list",
    )
    result = await run(
        ScriptedProvider(
            [
                Turn(calls=[ToolCall(id="record-1", tool="record", arguments=args)]),
                Turn(text="Recorded"),
            ]
        ),
        registry,
        Policy(frozenset({"record"}), (approval,)),
        "Record the sum",
        session=state,
    )
    assert result.status == "completed" and recorded == [3.0]
    print(result.status, recorded)


if __name__ == "__main__":
    asyncio.run(main())
