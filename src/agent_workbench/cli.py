import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from agent_workbench.core.agent_loop import run
from agent_workbench.core.budgets import Budgets
from agent_workbench.providers.adapter import ScriptedProvider, ToolCall, Turn
from agent_workbench.providers.ollama import OllamaProvider
from agent_workbench.storage.sqlite import EventStore
from agent_workbench.tools.permissions import Policy
from agent_workbench.tools.registry import builtins

app = typer.Typer(no_args_is_help=True)


@app.command()
def demo(
    offline: Annotated[bool, typer.Option(help="Run the zero-cost deterministic fixture.")],
    database: Path = Path("trace.sqlite3"),
) -> None:
    """Execute arithmetic, persist metadata and print the observed result."""
    if not offline:
        raise typer.BadParameter("Use --offline; live models require the separate local command.")

    class DemoProvider(ScriptedProvider):
        async def respond(
            self, messages: list[dict[str, object]], tools: list[dict[str, object]], max_tokens: int
        ) -> Turn:
            if messages[-1]["role"] == "tool":
                result = json.loads(str(messages[-1]["content"]))
                return Turn(text=f"6 × 7 = {result['value']:g}", output_tokens=8)
            return Turn(
                calls=[
                    ToolCall(
                        id="multiply-1",
                        tool="calculate",
                        arguments={"operation": "multiply", "left": 6.0, "right": 7.0},
                    )
                ],
                output_tokens=16,
            )

    with EventStore(database) as store:
        result = asyncio.run(
            run(
                DemoProvider([]),
                builtins(Path.cwd()),
                Policy(frozenset({"calculate"})),
                "What is 6 × 7?",
                store=store,
                on_event=lambda event: typer.echo(event.model_dump_json()),
            )
        )
    typer.echo(result.text or result.code)
    raise typer.Exit(0 if result.status == "completed" else 1)


@app.command()
def local(prompt: str, model: str, documents: Path = Path("."), max_steps: int = 8) -> None:
    """Use an already-installed Ollama model on loopback; no model downloads."""
    result = asyncio.run(
        run(
            OllamaProvider(model),
            builtins(documents),
            Policy(frozenset({"calculate", "read_document"})),
            prompt,
            Budgets(max_steps=max_steps),
        )
    )
    typer.echo(result.text or result.code)
    raise typer.Exit(0 if result.status == "completed" else 1)


@app.command()
def replay(run_id: str, database: Path = Path("trace.sqlite3")) -> None:
    """Print stored metadata in sequence without invoking a provider or tool."""
    if not database.is_file():
        raise typer.BadParameter("Trace database does not exist.")
    with EventStore(database) as store:
        events = store.replay(run_id)
    if not events:
        raise typer.BadParameter("Unknown run ID.")
    for event in events:
        typer.echo(event.model_dump_json())
