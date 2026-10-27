import os
import stat
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agent_workbench.tools.schemas import (
    CalculateInput,
    CalculateOutput,
    ReadInput,
    ReadOutput,
)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    execute: Callable[[Any], Awaitable[BaseModel]]
    side_effect: bool = False


class Registry:
    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError("duplicate_tool")
        self.tools[tool.name] = tool

    def schemas(self, allowed: frozenset[str]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_model.model_json_schema(),
                },
            }
            for t in self.tools.values()
            if t.name in allowed
        ]


async def calculate(args: CalculateInput) -> CalculateOutput:
    match args.operation:
        case "add":
            value = args.left + args.right
        case "subtract":
            value = args.left - args.right
        case "multiply":
            value = args.left * args.right
        case "divide":
            value = args.left / args.right
    return CalculateOutput(value=value)


def confined_read(root: Path, relative: str) -> str:
    """Open each path component relative to an FD; reject symlinks, including races.

    POSIX only. The caller controls the root; all descendant components are untrusted.
    """
    parts = relative.split("/")
    if any(p in ("", ".", "..") for p in parts) or "\\" in relative:
        raise ValueError("read_scope")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[:-1]:
            child = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("read_scope")
            data = stream.read(8193)
            if len(data) > 8192:
                raise ValueError("document_too_large")
            return data.decode("utf-8")
    finally:
        os.close(directory)


def builtins(root: Path) -> Registry:
    registry = Registry()
    registry.register(
        Tool(
            "calculate",
            "Arithmetic on two bounded numbers.",
            CalculateInput,
            CalculateOutput,
            calculate,
        )
    )

    async def read(args: ReadInput) -> ReadOutput:
        return ReadOutput(text=confined_read(root, args.path))

    registry.register(
        Tool(
            "read_document",
            "Read at most 8 KiB inside the document root.",
            ReadInput,
            ReadOutput,
            read,
        )
    )
    return registry
