import asyncio
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient
import pytest

from app.agent import Agent, greeting
from app.main import app
from app.schemas import Entry
from app.session import Call
from app.session import call_error
from app.summary import fallback, summarise
from test_rules import wav


class Stream:
    def __init__(self, deltas):
        self.deltas = deltas
        self.closed = False

    async def __aiter__(self):
        for index, step in enumerate(self.deltas):
            yield {"event_type": "step.start", "index": index, "step": {**step, "content": []} if step["type"] == "model_output" else step}
            if step["type"] == "model_output":
                for item in step["content"]:
                    yield {"event_type": "step.delta", "index": index, "delta": item}
        yield {"event_type": "interaction.completed", "interaction": {"status": "completed"}}

    async def aclose(self):
        self.closed = True


def text(value):
    return {"type": "model_output", "content": [{"type": "text", "text": value}]}


def tool(args, name="get_order_details", call_id="lookup"):
    return {"type": "function_call", "id": call_id, "name": name, "arguments": json.loads(args)}


class FakeLLM:
    def __init__(self, *args):
        self.responses = [[tool('{"order_id":"ORD-101"}')], [text("Your order is out for delivery. "), text("BlueDart expects it by 6 PM today.")]]
        self.requests = []
        self.closed = False

    async def stream(self, messages, tools, prompt):
        self.requests.append([dict(message) for message in messages])
        return Stream(self.responses.pop(0))

    async def summary(self, messages):
        raise ValueError("Summary provider offline")

    async def close(self):
        self.closed = True


class FakeVoice:
    def __init__(self, *args):
        self.closed = False

    async def transcribe(self, data):
        return "Where is ORD-101?"

    async def speech(self, value):
        yield b"\x00\x00" * 2400

    async def close(self):
        self.closed = True


class Socket:
    def __init__(self):
        self.events = []
        self.call = None

    async def send_json(self, event):
        self.events.append(event)
        if event["type"] == "speech_done":
            await self.call.acknowledge(event["chunk_id"], "played")

    async def send_bytes(self, data):
        self.events.append({"type": "audio", "bytes": len(data)})


def test_streamed_tool_loop_and_followup_context():
    async def run():
        llm = FakeLLM()
        records = []
        async def record(name, result):
            records.append((name, result))
        agent = Agent(llm, record)
        replies = [part async for part in agent.answer("Where is ORD-101?")]
        assert len(replies) == 2
        assert records[0][1]["courier"] == "BlueDart"
        assert llm.requests[1][-1]["type"] == "function_result"
        llm.responses = [[tool('{"order_id":"ORD-101"}', call_id="followup")], [text("The courier is BlueDart.")]]
        await collect(agent.answer("Which courier?"))
        assert any(message.get("content") == [{"type": "text", "text": "Where is ORD-101?"}] for message in llm.requests[-1])
        other = Agent(FakeLLM(), record)
        assert len(other.messages) == 0
    asyncio.run(run())


async def collect(generator):
    return [part async for part in generator]


def test_tool_loop_is_bounded():
    async def run():
        llm = FakeLLM()
        llm.responses = [[tool('{"order_id":"ORD-999"}')] for _ in range(4)]
        async def record(name, result): pass
        with pytest.raises(ValueError, match="Tool limit"):
            await collect(Agent(llm, record).answer("Check an order"))
        assert len(llm.requests) == 4
    asyncio.run(run())


def test_full_session_and_factual_summary_fallback():
    async def run():
        ws = Socket()
        call = Call(ws, FakeVoice(), FakeLLM())
        ws.call = call
        await call.begin()
        await call.task
        assert call.state == "Listening"
        assert call.entries[0].text == greeting
        await call.accept_audio(wav())
        await call.task
        assert [entry.speaker for entry in call.entries] == ["Aria", "Customer", "Aria", "Aria"]
        assert all(entry.playback == "played" for entry in call.entries if entry.speaker == "Aria")
        assert call.tools[0]["name"] == "get_order_details"
        await call.stop()
        last = ws.events[-1]
        assert last["type"] == "ended" and last["fallback"] is True
        assert last["outcome"]["order_ids"] == ["ORD-101"]
        assert last["outcome"]["resolution_status"] == "UNRESOLVED"
        assert call.voice.closed and call.llm.closed
    asyncio.run(run())


def test_end_during_playback_keeps_unheard_text_out():
    async def run():
        ws = Socket()
        ws.call = NS(acknowledge=lambda *args: asyncio.sleep(0))
        call = Call(ws, FakeVoice(), FakeLLM())
        await call.begin()
        for _ in range(10):
            if call.pending: break
            await asyncio.sleep(0)
        await call.stop()
        assert all(entry.text != greeting for entry in call.entries)
        assert call.entries[0].playback == "interrupted"
        assert call.task.cancelled()
    asyncio.run(run())


def test_end_during_thinking_cancels_provider_task():
    async def run():
        class SlowVoice(FakeVoice):
            async def transcribe(self, data):
                await asyncio.sleep(60)
        ws = Socket()
        call = Call(ws, SlowVoice(), FakeLLM())
        ws.call = call
        await call.begin()
        await call.task
        await call.accept_audio(wav())
        await asyncio.sleep(0)
        await call.stop()
        assert call.task.cancelled()
        assert len(call.entries) == 1
    asyncio.run(run())


def test_failed_speech_is_not_transcribed():
    async def run():
        class BrokenVoice(FakeVoice):
            async def speech(self, text):
                raise ValueError("Provider unavailable")
                yield b""
        ws = Socket()
        call = Call(ws, BrokenVoice(), FakeLLM())
        ws.call = call
        await call.begin()
        await call.task
        assert call.state == "Error" and call.entries == []
        await call.stop(notify=False)
    asyncio.run(run())


def test_empty_transcription_asks_to_repeat():
    async def run():
        class QuietVoice(FakeVoice):
            async def transcribe(self, data): return ""
        ws = Socket()
        call = Call(ws, QuietVoice(), FakeLLM())
        ws.call = call
        await call.begin()
        await call.task
        await call.accept_audio(wav())
        await call.task
        assert "repeat" in call.entries[-1].text
        assert not any(entry.speaker == "Customer" for entry in call.entries)
        assert not call.llm.requests
        await call.stop(notify=False)
    asyncio.run(run())


def test_health_orders_origin_and_no_credentials(monkeypatch):
    import app.main as main
    from app.config import Settings
    config = Settings(gemini_api_key="", frontend_origins="http://localhost:3000")
    monkeypatch.setattr(main, "get_settings", lambda: config)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "provider_configured": False}
        assert len(client.get("/orders").json()["orders"]) == 3
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/call", headers={"origin": "https://untrusted.example"}): pass
        with client.websocket_connect("/ws/call", headers={"origin": "http://localhost:3000"}) as ws:
            event = ws.receive_json()
            assert event["type"] == "error" and "GEMINI_API_KEY" in event["message"]


def test_websocket_real_protocol_with_test_providers(monkeypatch):
    import app.main as main
    from app.config import Settings
    config = Settings(gemini_api_key="test-only", frontend_origins="http://localhost:3000")
    monkeypatch.setattr(main, "get_settings", lambda: config)
    monkeypatch.setattr(main, "GeminiVoice", FakeVoice)
    monkeypatch.setattr(main, "GeminiLLM", FakeLLM)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/call", headers={"origin": "http://localhost:3000"}) as ws:
            session = ws.receive_json()["session_id"]
            chunk = ws.receive_json()["chunk_id"]
            assert ws.receive_json()["state"] == "Speaking"
            assert ws.receive_bytes()
            assert ws.receive_json()["type"] == "speech_done"
            ws.send_json({"type": "played", "session_id": session, "chunk_id": chunk})
            assert ws.receive_json()["entry"]["text"] == greeting
            assert ws.receive_json()["state"] == "Thinking"
            assert ws.receive_json()["state"] == "Listening"
            ws.send_json({"type": "end", "session_id": session})
            assert ws.receive_json()["state"] == "Ended"
            assert ws.receive_json()["type"] == "summary_pending"
            assert ws.receive_json()["outcome"]["resolution_status"] == "NO_CONVERSATION"


def test_quota_error_is_not_reported_as_missing_key():
    import httpx
    response = httpx.Response(429, request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/interactions"))
    error = httpx.HTTPStatusError("Request failed", request=response.request, response=response)
    message = call_error(error, "Generic failure")
    assert "key was loaded" in message
    assert "quota" in message
    assert "billing" in message

