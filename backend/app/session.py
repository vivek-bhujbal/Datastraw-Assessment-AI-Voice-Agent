import asyncio
from contextlib import aclosing
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from .agent import Agent, greeting
from .schemas import Entry
from .summary import summarise
from .voice import validate_audio


def call_error(error, default):
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "Gemini took too long to respond. Please try again."
    if isinstance(error, httpx.RequestError):
        return "Could not reach Gemini. Check your connection and try again."
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 429:
            try:
                message = error.response.json().get("error", {}).get("message", "").lower()
            except (ValueError, AttributeError):
                message = ""
            if "per day" in message or "daily" in message:
                return "Gemini's daily request allowance for this model is used up. Wait for the daily reset or check usage and billing in Google AI Studio. Your API key does not need to be replaced."
            return "Your Gemini key was loaded, but Google blocked the request because of a rate or quota limit. Check usage and billing in Google AI Studio, then try again."
        if status in {400, 401}:
            try:
                body = error.response.json().get("error", {})
                invalid_key = "API key not valid" in body.get("message", "") or any(item.get("reason") == "API_KEY_INVALID" for item in body.get("details", []))
            except (ValueError, AttributeError):
                invalid_key = False
            if status == 401 or invalid_key:
                return "Gemini rejected the API key. Check GEMINI_API_KEY in backend/.env and start a new call."
            return "Gemini rejected the request. Check that the configured models support audio, tools and structured output."
        if status in {403, 404}:
            return "Gemini denied access to the configured model. Check your Google AI Studio project, key restrictions and model names."
        if status >= 500:
            return "Gemini is temporarily unavailable. Please try again shortly."
    return default


class Call:
    def __init__(self, ws, voice, llm):
        self.ws, self.voice, self.llm = ws, voice, llm
        self.id = str(uuid4())
        self.entries = []
        self.tools = []
        self.agent = Agent(llm, self.record_tool)
        self.state = "Connecting"
        self.task = None
        self.pending = None
        self.ack = None
        self.ended = False
        self.had_error = False
        self.turns = 0
        self.failures = 0

    async def send(self, event, **data):
        await self.ws.send_json({"type": event, "session_id": self.id, **data})

    async def set_state(self, state):
        self.state = state
        await self.send("state", state=state)

    async def add_entry(self, speaker, text, turn_id, playback=None):
        entry = Entry(speaker=speaker, text=text, timestamp=datetime.now(timezone.utc).isoformat(), turn_id=turn_id, playback=playback)
        self.entries.append(entry)
        await self.send("transcript", entry=entry.model_dump())

    async def record_tool(self, name, result):
        record = {"name": name, "result": result}
        self.tools.append(record)
        await self.send("tool", **record)

    async def say(self, text, turn_id):
        chunk_id = str(uuid4())
        self.pending = {"chunk_id": chunk_id, "text": text, "turn_id": turn_id}
        self.ack = asyncio.get_running_loop().create_future()
        await self.send("speech_start", chunk_id=chunk_id, sample_rate=24000)
        byte_count = 0
        async for data in self.voice.speech(text):
            if self.ended:
                return
            byte_count += len(data)
            if byte_count > 4_000_000:
                raise ValueError("Speech response is too large")
            if self.state != "Speaking":
                await self.set_state("Speaking")
            await self.ws.send_bytes(data)
        if not byte_count:
            raise ValueError("Speech provider returned no audio")
        await self.send("speech_done", chunk_id=chunk_id)
        if not await asyncio.wait_for(self.ack, timeout=60):
            raise ValueError("Audio playback stopped")
        self.pending = None
        await self.set_state("Thinking")

    async def acknowledge(self, chunk_id, status):
        if not self.pending or self.pending["chunk_id"] != chunk_id or not self.ack or self.ack.done():
            return
        item = self.pending
        if status == "played":
            await self.add_entry("Aria", item["text"], item["turn_id"], "played")
            self.ack.set_result(True)
        else:
            self.had_error = True
            await self.add_entry("Aria", "[Audio interrupted before this segment finished.]", item["turn_id"], "interrupted")
            self.ack.set_result(False)

    async def begin(self):
        await self.send("session")
        self.task = asyncio.create_task(self.opening())

    async def opening(self):
        try:
            await self.say(greeting, "greeting")
            self.agent.remember("assistant", greeting)
            await self.set_state("Listening")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            message = call_error(error, "The spoken greeting could not be played. Check provider access and browser audio, then start a new call.")
            await self.fail(message, fatal=True)

    async def fail(self, message, fatal=False):
        self.had_error = True
        self.failures += 1
        self.pending = None
        fatal = fatal or self.failures >= 3
        await self.send("error", message=message, fatal=fatal)
        await self.set_state("Error" if fatal else "Listening")

    async def turn(self, data):
        turn_id = str(uuid4())
        checkpoint = len(self.agent.messages)
        try:
            async with asyncio.timeout(120):
                text = await self.voice.transcribe(data)
                if not text:
                    await self.say("I couldn’t hear that clearly. Could you repeat it, please?", turn_id)
                    await self.set_state("Listening")
                    return
                if len(text) > 4000:
                    raise ValueError("Please ask a shorter question")
                await self.add_entry("Customer", text, turn_id)
                async with aclosing(self.agent.answer(text)) as reply:
                    async for sentence in reply:
                        await self.say(sentence, turn_id)
                self.failures = 0
                await self.set_state("Listening")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # A failed response should not become something Aria thinks she said.
            self.agent.messages = self.agent.messages[:checkpoint]
            for entry in self.entries:
                if entry.turn_id == turn_id and entry.playback != "interrupted":
                    self.agent.remember("user" if entry.speaker == "Customer" else "assistant", entry.text)
            message = call_error(error, "This turn could not be completed. The speech or AI provider may be unavailable. Please repeat your question, or end the call.")
            await self.fail(message)

    async def accept_audio(self, data):
        if self.ended or self.state != "Listening" or self.task and not self.task.done():
            return
        try:
            validate_audio(data)
        except ValueError as exc:
            await self.send("error", message=str(exc), fatal=False)
            return
        self.turns += 1
        if self.turns > 80:
            await self.fail("The call has reached the 80-turn limit. Please end it and start a new call.", fatal=True)
            return
        await self.set_state("Thinking")
        self.task = asyncio.create_task(self.turn(data))

    async def stop(self, notify=True):
        self.ended = True
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        if self.pending:
            self.had_error = True
            entry = Entry(speaker="Aria", text="[Audio interrupted before this segment finished.]", timestamp=datetime.now(timezone.utc).isoformat(), turn_id=self.pending["turn_id"], playback="interrupted")
            if not any(e.turn_id == entry.turn_id and e.playback == "interrupted" for e in self.entries):
                self.entries.append(entry)
            self.pending = None
        if notify:
            try:
                await self.set_state("Ended")
                await self.send("summary_pending")
                outcome, used_fallback = await summarise(self.llm, self.entries, self.tools, self.had_error)
                await self.send("ended", transcript=[e.model_dump() for e in self.entries], outcome=outcome.model_dump(), fallback=used_fallback)
            finally:
                await self.voice.close()
                await self.llm.close()
        else:
            await self.voice.close()
            await self.llm.close()

