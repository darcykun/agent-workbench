import sqlite3
from pathlib import Path
from types import TracebackType

from agent_workbench.core.events import Event


class EventStore:
    """Metadata-only event journal. Replaying reads events; it never calls tools."""

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS events (run_id TEXT, sequence INTEGER, payload TEXT, "
            "PRIMARY KEY (run_id, sequence))"
        )
        self.connection.commit()

    def append(self, event: Event) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO events VALUES (?, ?, ?)",
                (event.run_id, event.sequence, event.model_dump_json()),
            )

    def replay(self, run_id: str) -> list[Event]:
        rows = self.connection.execute(
            "SELECT payload FROM events WHERE run_id = ? ORDER BY sequence", (run_id,)
        )
        return [Event.model_validate_json(row[0]) for row in rows]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "EventStore":
        return self

    def __exit__(
        self, typ: type[BaseException] | None, error: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()
