import asyncio
from dataclasses import dataclass, field
from uuid import uuid4

from agent_workbench.core.events import Event


@dataclass
class Session:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    events: list[Event] = field(default_factory=list)
    started: bool = False

    def cancel(self) -> None:
        self.cancelled.set()
