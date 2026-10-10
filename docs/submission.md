# Assessment notes

## Architecture choices

**Why this architecture?** Next.js/TypeScript and Tailwind provide a small responsive UI, while FastAPI handles asynchronous provider requests and the WebSocket session. STT → LLM → TTS keeps order tools, policy checks and transcript evidence visible. Fixed JSON is enough for three orders; adapters are separate without adding a framework or database.

**Hardest part and solution.** The most involved part in this implementation is coordinating audio, generation and call shutdown. The browser pauses input during Aria's output, plays streamed PCM through Web Audio, and acknowledges completed segments. The server records only those segments, cancels pending work on end, and builds the summary from the recorded transcript and tool audit. Browser tests use synthetic media; the real provider experience still needs a key and human listening.

**One extra week.** First replace the RMS threshold with a stronger speech detector and measure end-of-speech-to-playback latency in quiet/noisy conditions. Then add barge-in with accurate partial transcripts and run a live adversarial conversation suite. These improve the core call experience before adding secondary features.

**1,000 conversations a day.** Measure peak concurrency and average duration before sizing instances. Move call records into a store with retention/consent controls, add authorised customer/order access, distributed rate/spend limits, provider quota planning and redacted metrics. Multiple backend workers need a shared concurrency budget; sockets remain on their chosen instance, with an explicit recovery strategy for disconnects. The JSON fixtures would become an authenticated order-service adapter. Add load tests, provider failure monitoring, prompt evaluation and deployment draining. Daily volume alone is insufficient to promise a particular machine size or cost.

## A 3–5 minute demo

- **0:00–0:35:** Introduce Aura and Aria. Show the sample order panel and real call states. Start a call, grant mic access and hear the greeting.
- **0:35–1:30:** Ask “Where is ORD-101?” then “Which courier?” Show the actual `get_order_details` event in browser WebSocket frames or the source's tool flow, and hear the follow-up without repeating the ID.
- **1:30–2:30:** Ask to cancel ORD-101; hear the refusal. Ask about ORD-103 eligibility without a completion claim. Ask about shipping at exactly ₹499, or return ORD-102 for the 7-day-window explanation.
- **2:30–3:15:** End the call. Show the chronological transcript and validated JSON outcome, including actual lookup actions and multiple intents/orders where applicable.
- **3:15–4:15:** Briefly show `voice.py`, `agent.py`, `tools.py`, `policies.py`, and `useCall.ts`: voice adapters, function-call loop, deterministic rules and cleanup. Show the test results. State any limitations honestly.

Record this only after live provider verification. Test audio and scripted provider responses are not a substitute for an actual voice demo.

## Approach note

I built a Next.js interface connected to a FastAPI WebSocket session, with Gemini audio transcription, streamed speech output and an LLM function-calling loop. Order facts come from a local lookup tool, eligibility is enforced in Python, and the transcript and summary use playback acknowledgements and confirmed tool results so the app does not claim actions it never performed.

## Submission checklist

- [ ] Public application URL, checked over HTTPS with a real voice call
- [ ] GitHub repository link
- [x] README with local setup and deployment steps
- [x] Backend and frontend `.env.example` files
- [ ] 3–5 minute demo video link
- [ ] Your LinkedIn profile link
- [x] Short approach note above

The repository URL, public URL, video and profile must be supplied by the project owner. Nothing has been emailed or submitted automatically.

