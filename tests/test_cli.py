from pathlib import Path

from typer.testing import CliRunner

from agent_workbench.cli import app


def test_demo_and_replay(tmp_path: Path) -> None:
    import json

    runner = CliRunner()
    database = str(tmp_path / "trace.db")
    result = runner.invoke(app, ["demo", "--offline", "--database", database])
    assert result.exit_code == 0, result.output
    assert "6 × 7 = 42" in result.output
    run_id = json.loads(result.output.splitlines()[0])["run_id"]
    replay = runner.invoke(app, ["replay", run_id, "--database", database])
    assert replay.exit_code == 0 and "tool.completed" in replay.output
    assert "6 × 7" not in replay.output


def test_unknown_replay(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["replay", "unknown", "--database", str(tmp_path / "absent")])
    assert result.exit_code != 0
