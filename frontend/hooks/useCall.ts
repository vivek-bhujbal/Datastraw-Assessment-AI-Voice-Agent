"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { CallAudio } from "@/lib/audio";
import { apiUrl, socketUrl } from "@/lib/api";
import type { Entry, Outcome, State, ToolRecord } from "@/types/call";

type View = {
  state: State; active: boolean; ending: boolean; duration: number;
  error: string | null; mic: string; entries: Entry[]; outcome: Outcome | null; fallback: boolean;
};
const initial: View = { state: "Idle", active: false, ending: false, duration: 0, error: null, mic: "Permission requested when you start", entries: [], outcome: null, fallback: false };
type Action = { type: "reset" } | { type: "patch"; value: Partial<View> } | { type: "entry"; entry: Entry };
function reducer(state: View, action: Action): View {
  if (action.type === "reset") return { ...initial, state: "Connecting", active: true, mic: "Waiting for microphone permission" };
  if (action.type === "entry") return { ...state, entries: [...state.entries, action.entry] };
  return { ...state, ...action.value };
}

function localOutcome(entries: Entry[], tools: ToolRecord[]): Outcome {
  const customer = entries.filter(entry => entry.speaker === "Customer");
  const ids = [...new Set(tools.map(tool => tool.result.order_id).filter((id): id is string => typeof id === "string"))];
  return {
    customer_intent: null, intents: [], order_id: ids.length === 1 ? ids[0] : null, order_ids: ids,
    resolution_status: customer.length ? "UNRESOLVED" : "NO_CONVERSATION",
    call_summary: `Recorded ${customer.length} customer turn(s). The connection ended before the server summary arrived. No resolution was inferred.`,
    actions_taken: tools.filter(tool => tool.name === "get_order_details" && typeof tool.result.order_id === "string")
      .map(tool => `Looked up ${tool.result.order_id}: ${tool.result.found ? "found" : "not found"}.`),
    unresolved_questions: customer.slice(-3).map(entry => entry.text),
  };
}

export function useCall() {
  const [view, dispatch] = useReducer(reducer, initial);
  const socket = useRef<WebSocket | null>(null);
  const audio = useRef<CallAudio | null>(null);
  const id = useRef<string | null>(null);
  const version = useRef(0);
  const busy = useRef(false);
  const ending = useRef(false);
  const finalised = useRef(false);
  const entries = useRef<Entry[]>([]);
  const tools = useRef<ToolRecord[]>([]);
  const started = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const meter = useRef<HTMLMeterElement | null>(null);
  const patch = (value: Partial<View>) => dispatch({ type: "patch", value });

  const send = useCallback((type: string, chunk_id?: string) => {
    if (socket.current?.readyState === WebSocket.OPEN && id.current) {
      socket.current.send(JSON.stringify({ type, session_id: id.current, ...(chunk_id ? { chunk_id } : {}) }));
    }
  }, []);

  const stopMedia = useCallback(() => {
    audio.current?.stop();
    audio.current = null;
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    if (meter.current) meter.current.value = 0;
  }, []);

  const finishLocally = useCallback((message?: string) => {
    if (finalised.current) return;
    finalised.current = true;
    ending.current = true;
    stopMedia();
    if (timeout.current) clearTimeout(timeout.current);
    socket.current?.close();
    busy.current = false;
    patch({ state: message ? "Error" : "Ended", active: false, ending: false, mic: "Microphone released", outcome: localOutcome(entries.current, tools.current), fallback: true, ...(message ? { error: message } : {}) });
  }, [stopMedia]);

  const end = useCallback(() => {
    if (!busy.current || ending.current) return;
    ending.current = true;
    stopMedia();
    patch({ state: "Ended", ending: true, mic: "Microphone released" });
    if (id.current && socket.current?.readyState === WebSocket.OPEN) {
      send("end");
      timeout.current = setTimeout(() => finishLocally("The server summary timed out. A factual fallback is shown."), 30000);
    } else finishLocally();
  }, [finishLocally, send, stopMedia]);

  const start = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    ending.current = finalised.current = false;
    const current = ++version.current;
    entries.current = []; tools.current = []; id.current = null;
    dispatch({ type: "reset" });
    const valid = () => current === version.current && !ending.current;
    try {
      const media = new CallAudio(
        data => {
          if (!valid() || socket.current?.readyState !== WebSocket.OPEN) return;
          patch({ state: "Thinking", error: null });
          socket.current.send(data);
        },
        (chunk, success) => { if (current === version.current && !finalised.current) send(success ? "played" : "playback_failed", chunk); },
        level => { if (meter.current) meter.current.value = level; },
        () => { if (valid()) patch({ state: "Speaking" }); },
        message => { if (valid()) { patch({ state: "Error", error: message }); end(); } },
      );
      audio.current = media;
      await media.start();
      if (!valid()) { media.stop(); return; }
      patch({ mic: "Microphone allowed", state: "Connecting" });
      const health = await fetch(`${apiUrl}/health`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
      if (!health.ok) throw new Error("The support server is unavailable. Check the backend URL and try again.");
      const status = await health.json();
      if (!status.provider_configured) throw new Error("Voice calls need a Gemini API key. Set GEMINI_API_KEY in backend/.env, then start a new call.");
      if (!valid()) return;
      const ws = new WebSocket(socketUrl());
      ws.binaryType = "arraybuffer";
      socket.current = ws;
      timeout.current = setTimeout(() => { if (valid() && !id.current) finishLocally("The call connection timed out. Check the backend and try again."); }, 10000);
      ws.onmessage = event => {
        if (current !== version.current || finalised.current) return;
        if (event.data instanceof ArrayBuffer) { if (!ending.current) audio.current?.play(event.data); return; }
        const data = JSON.parse(event.data);
        if (data.type === "session") {
          if (ending.current) { ws.close(); return; }
          id.current = data.session_id;
          if (timeout.current) clearTimeout(timeout.current);
          started.current = Date.now();
          timer.current = setInterval(() => patch({ duration: Math.floor((Date.now() - started.current) / 1000) }), 1000);
        }
        if (data.session_id && id.current && data.session_id !== id.current) return;
        if (data.type === "transcript") {
          entries.current.push(data.entry);
          dispatch({ type: "entry", entry: data.entry });
        } else if (data.type === "tool") {
          tools.current.push({ name: data.name, result: data.result });
        } else if (data.type === "ended") {
          finalised.current = true;
          stopMedia();
          if (timeout.current) clearTimeout(timeout.current);
          busy.current = false;
          patch({ active: false, ending: false, state: "Ended", entries: data.transcript, outcome: data.outcome, fallback: data.fallback, mic: "Microphone released" });
          ws.close();
        } else if (data.type === "error") {
          audio.current?.stopPlayback();
          patch({ error: data.message, ...(data.fatal ? { state: "Error" } : {}) });
          if (data.fatal) end();
        } else if (!ending.current && data.type === "state") {
          patch({ state: data.state });
          audio.current?.setListening(data.state === "Listening");
        } else if (!ending.current && data.type === "speech_start") {
          audio.current?.beginSpeech(data.chunk_id);
        } else if (!ending.current && data.type === "speech_done") {
          audio.current?.finishSpeech(data.chunk_id);
          patch({ state: "Speaking" });
        }
      };
      ws.onerror = () => { if (valid()) finishLocally("Could not connect to voice support. Check the backend URL and allowed frontend origin."); };
      ws.onclose = () => { if (current === version.current && !finalised.current) finishLocally("The call connection closed. Recorded messages are preserved below."); };
    } catch (error) {
      if (!valid()) return;
      const name = error instanceof Error ? error.name : "";
      const message = name === "NotAllowedError" ? "Microphone permission was denied. Allow it in your browser’s site settings and try again."
        : name === "NotFoundError" ? "No microphone was found. Connect one and try again."
        : name === "NotReadableError" ? "Your microphone is busy or unavailable. Close other apps using it and try again."
        : error instanceof TypeError ? "The support server could not be reached. Start the backend and check NEXT_PUBLIC_API_URL."
        : error instanceof Error ? error.message : "The call could not start. Please try again.";
      finishLocally(message);
    }
  }, [end, finishLocally, send, stopMedia]);

  useEffect(() => () => {
    version.current++;
    finalised.current = true;
    stopMedia();
    socket.current?.close();
    if (timeout.current) clearTimeout(timeout.current);
  }, [stopMedia]);

  return { ...view, start, end, meter };
}

