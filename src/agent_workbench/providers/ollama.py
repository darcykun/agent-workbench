import json
from typing import Any

import httpx

from agent_workbench.providers.adapter import ToolCall, Turn


class OllamaProvider:
    """Opt-in local model only; never downloads models or calls a paid API."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.sequence = 0

    async def respond(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], max_tokens: int
    ) -> Turn:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0},
        }
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            async with client.stream(
                "POST", "http://127.0.0.1:11434/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 262144:
                        raise ValueError("provider_response_too_large")
        body = json.loads(data)
        message = body["message"]
        calls = []
        for call in message.get("tool_calls", []):
            self.sequence += 1
            calls.append(
                ToolCall(
                    id=f"ollama-{self.sequence}",
                    tool=call["function"]["name"],
                    arguments=call["function"]["arguments"],
                )
            )
        return Turn(text=message.get("content", ""), calls=calls, output_tokens=body["eval_count"])
