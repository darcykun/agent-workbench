import json
from typing import Any

import httpx
import pytest

from agent_workbench.providers.ollama import OllamaProvider


async def test_ollama_contract(monkeypatch: Any) -> None:
    observed = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        body = json.loads(request.content)
        assert body["options"]["num_predict"] == 12
        assert body["stream"] is False
        observed.append(body)
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "calculate",
                                "arguments": {"operation": "add", "left": 1.0, "right": 2.0},
                            }
                        }
                    ],
                },
                "eval_count": 9,
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    provider = OllamaProvider("configured-local-model")
    first = await provider.respond([{"role": "user", "content": "add"}], [], 12)
    second = await provider.respond([], [], 12)
    assert first.output_tokens == 9 and first.calls[0].tool == "calculate"
    assert first.calls[0].id != second.calls[0].id
    assert observed[0]["model"] == "configured-local-model"


@pytest.mark.parametrize("payload,status", [(b"x" * 262145, 200), (b"{}", 503)])
async def test_ollama_boundaries(monkeypatch: Any, payload: bytes, status: int) -> None:
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(status, content=payload))
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=transport)
    )
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        await OllamaProvider("local").respond([], [], 10)
