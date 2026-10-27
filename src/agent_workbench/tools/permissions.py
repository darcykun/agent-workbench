import hashlib
import json
from dataclasses import dataclass
from typing import Any


def argument_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class Approval:
    """Constructed by a trusted operator, never by a provider response."""

    run_id: str
    call_id: str
    tool: str
    digest: str
    reason: str


@dataclass(frozen=True)
class Policy:
    allowed_tools: frozenset[str]
    approvals: tuple[Approval, ...] = ()

    def approved(self, run_id: str, call_id: str, tool: str, digest: str) -> bool:
        return any(
            a.run_id == run_id
            and a.call_id == call_id
            and a.tool == tool
            and a.digest == digest
            and bool(a.reason.strip())
            for a in self.approvals
        )
