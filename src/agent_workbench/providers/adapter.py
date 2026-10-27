from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=128)
    tool: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any]


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str = Field(default="", max_length=32768)
    calls: list[ToolCall] = Field(default_factory=list, max_length=16)
    output_tokens: int = Field(default=0, ge=0)


class Provider(Protocol):
    async def respond(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], max_tokens: int
    ) -> Turn: ...


class ScriptedProvider:
    """Deterministic offline fixture; each run should get its own instance."""

    def __init__(self, turns: list[Turn]) -> None:
        self.turns = iter(turns)

    async def respond(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], max_tokens: int
    ) -> Turn:
        return next(self.turns, Turn(text="Done."))
