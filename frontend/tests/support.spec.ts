import { expect, test, type Page } from "@playwright/test";

const greeting = "Hi, I’m Aria from Aura Skincare. How can I help you today?";
const api = process.env.TEST_API_URL || "http://localhost:8000";
const wsUrl = api.replace(/^http/, "ws") + "/ws/call";

async function observeAudio(page: Page) {
  await page.addInitScript(() => {
    const media = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    const store = window as typeof window & { streams: MediaStream[]; contexts: AudioContext[] };
    store.streams = []; store.contexts = [];
    navigator.mediaDevices.getUserMedia = async options => {
      const stream = await media(options);
      store.streams.push(stream);
      return stream;
    };
    const Original = window.AudioContext;
    window.AudioContext = class extends Original {
      constructor(options?: AudioContextOptions) { super(options); store.contexts.push(this); }
    };
  });
}

async function fakeCall(page: Page, seconds = 0.15) {
  const events: Record<string, unknown>[] = [];
  await page.route(`${api}/health`, route => route.fulfill({ json: { status: "ok", provider_configured: true } }));
  await page.routeWebSocket(wsUrl, ws => {
    const session = "test-session";
    const send = (type: string, data = {}) => ws.send(JSON.stringify({ type, session_id: session, ...data }));
    send("session");
    send("speech_start", { chunk_id: "greeting", sample_rate: 24000 });
    const pcm = Buffer.alloc(Math.round(24000 * seconds) * 2);
    for (let i = 0; i < pcm.length / 2; i++) pcm.writeInt16LE(Math.round(Math.sin(i / 24000 * 440 * Math.PI * 2) * 1200), i * 2);
    ws.send(pcm);
    send("speech_done", { chunk_id: "greeting" });
    ws.onMessage(raw => {
      if (typeof raw !== "string") return;
      const data = JSON.parse(raw);
      events.push(data);
      if (data.type === "played") {
        send("transcript", { entry: { speaker: "Aria", text: greeting, timestamp: new Date().toISOString(), turn_id: "greeting", playback: "played" } });
        send("state", { state: "Listening" });
      }
      if (data.type === "end") send("ended", {
        transcript: events.some(event => event.type === "played") ? [{ speaker: "Aria", text: greeting, timestamp: new Date().toISOString(), turn_id: "greeting", playback: "played" }] : [],
        outcome: { customer_intent: null, intents: [], order_id: null, order_ids: [], resolution_status: "NO_CONVERSATION", call_summary: "No customer conversation took place.", actions_taken: [], unresolved_questions: [] },
        fallback: false,
      });
    });
  });
  return events;
}

test("initial page has sample records, empty transcript and disabled end", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Good skincare. Thoughtful support." })).toBeVisible();
  for (const id of ["ORD-101", "ORD-102", "ORD-103"]) await expect(page.getByRole("heading", { name: id })).toBeVisible();
  await expect(page.getByText("BlueDart", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "End call" })).toBeDisabled();
  await expect(page.getByText("No call outcome yet")).toBeVisible();
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });
});

test("missing provider key reports a real error and releases microphone", async ({ page }) => {
  await page.route(`${api}/health`, route => route.fulfill({ json: { status: "ok", provider_configured: false } }));
  await observeAudio(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start call" }).click();
  await expect(page.getByRole("alert", { name: "Call error" })).toContainText("GEMINI_API_KEY");
  await expect(page.getByRole("button", { name: "Start call" })).toBeEnabled();
  const stopped = await page.evaluate(() => (window as typeof window & { streams: MediaStream[] }).streams.every(stream => stream.getTracks().every(track => track.readyState === "ended")));
  expect(stopped).toBe(true);
});

test("microphone denial gives an actionable error", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException("Denied", "NotAllowedError"); };
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start call" }).click();
  await expect(page.getByRole("alert", { name: "Call error" })).toContainText("Microphone permission was denied");
});

test("streamed PCM plays, acknowledgement creates transcript, new call clears it", async ({ page }) => {
  await observeAudio(page);
  const events = await fakeCall(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start call" }).click();
  await expect(page.getByText(greeting)).toBeVisible();
  expect(events.some(event => event.type === "played")).toBe(true);
  await expect(page.getByRole("button", { name: "Start call" })).toBeDisabled();
  await page.getByRole("button", { name: "End call" }).click();
  await expect(page.getByLabel("Structured call outcome")).toContainText("NO_CONVERSATION");
  await page.getByRole("button", { name: "Start call" }).click();
  await expect(page.getByText(greeting)).toHaveCount(0);
  await page.getByRole("button", { name: "End call" }).click();
});

test("end during playback closes audio and stops tracks", async ({ page }) => {
  await observeAudio(page);
  const events = await fakeCall(page, 5);
  await page.goto("/");
  await page.getByRole("button", { name: "Start call" }).click();
  await expect(page.locator(".state-speaking")).toBeVisible();
  await page.getByRole("button", { name: "End call" }).click();
  await expect(page.getByRole("button", { name: "Start call" })).toBeEnabled();
  expect(events.some(event => event.type === "playback_failed")).toBe(true);
  const result = await page.evaluate(() => {
    const store = window as typeof window & { streams: MediaStream[]; contexts: AudioContext[] };
    return { tracks: store.streams.every(stream => stream.getTracks().every(track => track.readyState === "ended")), audio: store.contexts.every(context => context.state === "closed") };
  });
  expect(result).toEqual({ tracks: true, audio: true });
  await expect(page.getByText(greeting)).toHaveCount(0);
});

test("mobile layout stays inside viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "ORD-103" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
});

