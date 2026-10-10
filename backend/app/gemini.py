import asyncio
import json

import httpx


def response_text(result):
    return "".join(
        item.get("text", "")
        for step in result.get("steps", []) if step.get("type") == "model_output"
        for item in step.get("content", []) if item.get("type") == "text"
    )


class Gemini:
    def __init__(self, key):
        self.client = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com/v1beta/",
            headers={"x-goog-api-key": key.strip()}, timeout=45
        )

    async def create(self, data):
        for attempt in range(2):
            response = await self.client.post("interactions", json={**data, "store": False})
            if attempt == 0 and response.status_code in {500, 502, 503, 504}:
                await asyncio.sleep(0.5)
                continue
            response.raise_for_status()
            result = response.json()
            if result.get("status") not in {"completed", "requires_action"}:
                raise ValueError("Gemini did not finish the response")
            return result

    async def stream(self, data):
        for attempt in range(2):
            async with self.client.stream("POST", "interactions", json={**data, "store": False, "stream": True}) as response:
                if response.is_error:
                    await response.aread()
                    # Retry before playback starts, so audio is never repeated.
                    if attempt == 0 and response.status_code in {500, 502, 503, 504}:
                        await asyncio.sleep(0.5)
                        continue
                    response.raise_for_status()
                lines = []
                finished = False
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        lines.append(line[5:].lstrip())
                    elif not line and lines:
                        raw = "\n".join(lines)
                        lines = []
                        if raw == "[DONE]":
                            break
                        event = json.loads(raw)
                        kind = event.get("event_type")
                        if kind in {"error", "interaction.failed"}:
                            raise ValueError("Gemini stopped the response. Please try again.")
                        if kind == "interaction.completed":
                            status = event.get("interaction", {}).get("status")
                            if status not in {"completed", "requires_action"}:
                                raise ValueError("Gemini did not finish the response")
                            finished = True
                        yield event
                if not finished:
                    raise ValueError("The Gemini response was interrupted")
                return

    async def close(self):
        await self.client.aclose()
