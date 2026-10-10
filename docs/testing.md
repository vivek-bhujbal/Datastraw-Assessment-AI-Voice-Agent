# Validation

Run date: 9 October 2026.

## Automated results

- Backend: **55 tests passed** under Python 3.14.6. Tests cover conservative spoken IDs, exact fixtures, unknown orders, cancellation/return rules, missing facts, invalid arguments, tool allowlisting, bounded tool loops, conversation isolation, audio validation, summary schemas, saved-key reloading, Windows BOM files and actionable Gemini quota, key and model-access errors, including daily limits and a single retry for temporary service failures.
- Session tests cover a spoken greeting with test audio, final customer transcripts, tool-result flow, playback acknowledgements, empty transcription, speech failure, end during generation/playback and factual summary fallback.
- Gemini Interactions REST requests were exercised against an HTTPX mock transport: inline WAV transcription, streamed 24 kHz PCM speech, fragmented function-call arguments, retained thought signatures, structured summaries, provider errors and interrupted streams. No provider network call or live LLM reasoning was asserted by these tests.
- Chrome: **6 browser tests passed**. They cover sample records, missing credentials with microphone release, permission denial, actual Web Audio playback with a mocked WebSocket, transcript acknowledgements, new-call reset, end during playback and a 390 px mobile layout.
- TypeScript checking, the production Next.js build and all six Chrome tests passed after the Gemini migration. Earlier Docker builds passed for Python 3.13 and Node 24; container builds and smoke checks have not been repeated for the Gemini change. Local dependency installation reported no npm vulnerabilities.

The backend test runner emitted a Starlette warning about future migration from `httpx` to `httpx2`; the checks still passed. Browser media is synthetic. This does not verify the accuracy, accent, quality or availability of a paid speech provider.

Normal commands are in the README. If the default ports are already occupied, use dedicated ports:

```powershell
# Backend terminal, in backend/
$env:FRONTEND_ORIGINS='http://127.0.0.1:3107'
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8107 --ws-max-size 5000000

# Frontend terminal, in frontend/
$env:NEXT_PUBLIC_API_URL='http://127.0.0.1:8107'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3107

# Test terminal, in frontend/
$env:TEST_BASE_URL='http://127.0.0.1:3107'
$env:TEST_API_URL='http://127.0.0.1:8107'
npm.cmd test
```

The missing-key test mocks an unconfigured health response. Audio tests mock the provider configuration and WebSocket responses, so they do not use the saved API key. The app itself has no fake-call mode.

## Manual checks

Desktop and mobile screenshots were visually reviewed. Live Gemini checks on 9 October verified TTS, transcription of a synthetic spoken order question, the real order tool, a spoken reply and structured summaries. A rejected `minimal` thinking level was corrected to `low` for transcription, answers and summaries, then the backend was restarted. Rapid checks also encountered Google HTTP 5xx and 429 responses. After the larger models reached their daily free quotas during checks, defaults were changed to `gemini-3.5-flash-lite` for transcription/conversation and `gemini-3.8-flash-lite-tts` for speech. A live synthetic question completed transcription, the order tool and spoken playback through the WebSocket. The order summary used the labelled fallback; structured JSON summaries were verified separately using generic synthetic greeting text. A complete real microphone session, measured latency and public HTTPS/WSS deployment remain unverified. Complete the checklist below with a microphone; mocked and synthetic checks do not establish all conversation quality.

| Scenario | Expected behavior | Current evidence / remaining check |
| --- | --- | --- |
| 1. Start call | Permission, genuine spoken greeting, then Listening | Browser PCM playback and session greeting covered with doubles; listen to live TTS |
| 2. Shipping | Free above ₹499, ₹50 below; 3–5 business days | Authoritative policy file inspected; live answer pending |
| 3. ORD-101 lookup | LLM calls `get_order_details`; Out for Delivery, expected by 6 PM | SDK/tool loop and exact fixture tested; live reasoning pending |
| 4. Courier follow-up | Uses ORD-101 context; BlueDart | Context retention and repeat lookup tested with scripted LLM; live follow-up pending |
| 5. Cancel ORD-101 | Refusal because Out for Delivery; doorstep refusal allowed | Python cancellation rule tested; live phrasing pending |
| 6. Return ORD-102 | Refusal due to delivery 14 days ago and 7-day limit | Backend return decision tested, including conflicting claimed delivery time; live answer pending |
| 7. Cancel ORD-103 | Eligible because Processing; no false cancellation claim | Python eligibility tested; live wording pending |
| 8. ORD-999 | Structured not-found result, no nearest-ID substitution | Lookup and normalization tested; live explanation pending |
| 9. Missing ID | Ask for order ID, do not guess | Prompt configured; live behavior pending |
| 10. Book a flight | Aura-only scope response | Prompt configured; live behavior pending |
| 11. Unclear speech | No fabricated transcript; ask to repeat | Empty STT and audio validation tested; real noise/unclear speech pending |
| 12. Ignore policies | Respect authoritative rules and tool results | Deterministic policy functions tested; live injection resistance pending |
| 13. Exactly ₹499 | Acknowledge unspecified shipping rule | Policy and prompt boundary checked; live response pending |
| 14. End during playback | Immediate audio stop, tracks released, generation cancelled | Browser and backend automated checks passed with synthetic audio |
| 15. Transcript and JSON | Chronological final transcript; validated, grounded outcome or labelled fallback | Playback, fallback and schema tests passed; live outcome accuracy pending |
| 16. New call | Previous context and transcript cleared | Backend isolation and Chrome UI reset tests passed |

Also check a quiet microphone, continuous background noise, missing/invalid device, a provider quota error, network disconnect, a long pause, several intents/orders, end during Thinking, a used/opened product with no delivery age, and returns with missing packaging facts. A refusal can be a resolved explanation; a lookup is never a completed cancellation.

