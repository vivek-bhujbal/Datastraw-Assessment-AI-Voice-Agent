import asyncio
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from .config import get_settings
from .llm import GeminiLLM
from .session import Call
from .tools import get_order_details, orders
from .voice import GeminiVoice

settings = get_settings()
app = FastAPI(title="Aura voice support")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET"], allow_headers=["Content-Type"])
active_calls = set()


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["end", "played", "playback_failed"]
    session_id: str = Field(max_length=80)
    chunk_id: str | None = Field(default=None, max_length=80)


@app.get("/health")
def health():
    return {"status": "ok", "provider_configured": get_settings().ready}


@app.get("/orders")
def sample_orders():
    return {"orders": [get_order_details(order_id) for order_id in orders], "fixture_notice": "Sample records. Relative delivery times are assessment fixtures."}


@app.websocket("/ws/call")
async def conversation(ws: WebSocket):
    config = get_settings()
    if ws.headers.get("origin", "").rstrip("/") not in config.origins:
        await ws.close(code=1008)
        return
    await ws.accept()
    if not config.ready or len(active_calls) >= config.max_sessions:
        message = "Set GEMINI_API_KEY in backend/.env to enable voice calls." if not config.ready else "All demo call slots are in use. Please try again shortly."
        await ws.send_json({"type": "error", "message": message, "fatal": True})
        await ws.close(code=1013)
        return
    call = Call(ws, GeminiVoice(config), GeminiLLM(config))
    active_calls.add(call.id)
    start = time.monotonic()
    try:
        await call.begin()
        while not call.ended:
            remaining = 900 - (time.monotonic() - start)
            if remaining <= 0:
                await call.send("error", message="The 15-minute demo call limit was reached.", fatal=True)
                await call.stop()
                break
            packet = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 180))
            if packet["type"] == "websocket.disconnect":
                break
            if packet.get("bytes") is not None:
                await call.accept_audio(packet["bytes"])
            elif packet.get("text") is not None:
                raw = packet["text"]
                if len(raw) > 2000:
                    await call.send("error", message="Message too large.", fatal=False)
                    continue
                try:
                    event = Event.model_validate_json(raw)
                except ValidationError:
                    await call.send("error", message="Invalid call event.", fatal=False)
                    continue
                if event.session_id != call.id:
                    await ws.close(code=1008)
                    break
                if event.type == "end":
                    await call.stop()
                    break
                if event.chunk_id:
                    await call.acknowledge(event.chunk_id, "played" if event.type == "played" else "interrupted")
    except (WebSocketDisconnect, TimeoutError, RuntimeError):
        pass
    finally:
        active_calls.discard(call.id)
        if not call.ended:
            await call.stop(notify=False)
        try:
            await ws.close()
        except RuntimeError:
            pass

