from typing import Literal

from pydantic import BaseModel, ConfigDict

EventName = Literal[
    "run.started",
    "provider.completed",
    "approval.granted",
    "approval.denied",
    "tool.completed",
    "tool.reused",
    "run.completed",
    "run.failed",
    "run.cancelled",
]


class Event(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: Literal[1] = 1
    run_id: str
    sequence: int
    name: EventName
    tool: str | None = None
    call_id: str | None = None
    argument_digest: str | None = None
    code: str | None = None
