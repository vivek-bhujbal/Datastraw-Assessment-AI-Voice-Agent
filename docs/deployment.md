# Deploying

The frontend needs a Node-capable host. The backend needs an always-running ASGI process with public WebSockets; a short-lived serverless HTTP function is unsuitable. No FFmpeg or database service is needed because the browser sends valid WAV.

## Render

Render documents [public WebSocket support](https://render.com/docs/websocket), [Docker deployment and build arguments](https://render.com/docs/docker), and [Blueprint configuration](https://render.com/docs/blueprint-spec). Both Dockerfiles run as non-root users.

1. Push this project to your own GitHub repository, excluding `.env`, `.venv` and `node_modules`.
2. In Render, create a Blueprint from the repository and `render.yaml`, or create two Docker web services manually. The blueprint uses paid Starter plans; choose capacity and review pricing in your account.
3. For the backend use Docker context `backend`, Dockerfile `backend/Dockerfile`, and health check `/health`. Set `GEMINI_API_KEY`, the model/voice variables, `MAX_SESSIONS`, and `FRONTEND_ORIGINS=https://YOUR-FRONTEND.onrender.com`. Render's assigned `PORT` is read by the Docker start command.
4. For the frontend use context `frontend`, Dockerfile `frontend/Dockerfile`, and health check `/`. Set `NEXT_PUBLIC_API_URL=https://YOUR-BACKEND.onrender.com` **before building**. Render passes environment variables as build arguments, and this Dockerfile declares the public URL argument. Provider secrets are never declared as build arguments.
5. If the actual generated service names differ, update the frontend URL and backend origins, then rebuild the frontend and restart the backend. Origins include scheme and hostname, optional port, and no path. Do not use `*`.
6. Check `https://YOUR-BACKEND.onrender.com/health`: `status` must be `ok`, and `provider_configured` must be true. This is a configuration/liveness check, not an external provider availability test.
7. Open the frontend HTTPS URL in Chrome, allow the mic, run the checklist in `testing.md`, and inspect that `/ws/call` connects over WSS. Test a real spoken greeting, order lookup, and summary before recording the demo.

Start commands are the Dockerfile `CMD`s: backend runs `uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws-max-size 5000000`; frontend runs `node server.js` from the standalone Next.js build. Docker builds install requirements and run `npm ci` / `npm run build`.

For native services instead of Docker:

| Service | Root | Build | Start |
| --- | --- | --- | --- |
| Backend | `backend` | `pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --ws-max-size 5000000` |
| Frontend | `frontend` | `npm ci && npm run build` | `npm run start -- --port $PORT` |

Configure the same environment variables. For Vercel frontend hosting, use `frontend` as root and set the backend public HTTPS URL before deploying; keep FastAPI on a WebSocket-capable service such as Render. Add the Vercel production origin to the backend allowlist. Preview origins must be explicitly listed if you intend to test them.

## Hosting limits

Microphone capture requires HTTPS except on localhost. TLS must terminate at the hosting platform or your reverse proxy; the app derives WSS from the HTTPS backend URL. Reverse proxies must support WebSocket upgrades, a 5 MB frame limit, and sufficiently long read timeouts.

Instances can restart during deployments or maintenance and disconnect in-memory calls. Free services may sleep or cold-start; a free tier does not guarantee a continuous call. Provider quotas, account credit, egress and simultaneous calls also limit capacity. Use one backend worker for this demo so the configured concurrency cap is predictable. Uvicorn handles WebSocket ping/pong; the separate app idle timeout is three minutes. A disconnect produces a browser fallback rather than automatic resumption.

No Render account or deployment credential was available for this implementation. The configuration is ready to use; the account setup, public deployment and live URL checks remain with the project owner.

