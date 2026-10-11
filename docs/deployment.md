# Deploying

The frontend needs a Node-capable host. The backend needs an always-running ASGI process with public WebSockets; a short-lived serverless HTTP function is unsuitable. No FFmpeg or database service is needed because the browser sends valid WAV.

## AntiDeploy: deploy both services as one app

Upload the **project root**, which now contains a combined `Dockerfile`; do not choose only `frontend/` as the deployment root. AntiDeploy [uses a root Dockerfile when the account supports custom Docker builds](https://antideploy.com/platform/hosting). If the build logs say the Dockerfile was skipped, this combined setup has not been built: use an eligible account or deploy the two services separately as described below.

The container starts Next.js, FastAPI and an Nginx proxy together. The frontend uses `/api`, which stays on the same public HTTPS domain. `/api/health` and `/api/orders` reach FastAPI; `/api/ws/call` upgrades to its voice WebSocket. No separate public backend URL is required. The root Dockerfile always builds the frontend with `NEXT_PUBLIC_API_URL=/api`, overriding local development URLs.

1. In AntiDeploy's environment settings, set `GEMINI_API_KEY` to your real Gemini key and `FRONTEND_ORIGINS` to the exact public frontend origin copied from your browser (scheme plus hostname; no trailing slash or path).
2. Set the three URL values if the form asks for them:

   | Variable | Combined deployment value |
   | --- | --- |
   | `NEXT_PUBLIC_API_URL` | `/api` |
   | `TEST_API_URL` | Your public frontend origin followed by `/api` |
   | `TEST_BASE_URL` | Your public frontend origin |

   The `TEST_*` values are only for browser tests. `.env.example` at the project root is the full deployment template; `frontend/.env.deploy.example` contains the three frontend URL values. Update their example origin if your actual address differs. Keep the real Gemini key in the platform's secret settings rather than committing it.
3. Redeploy the project root and check that the root Dockerfile is used. Saving a local `.env.local` file does not change an existing remote deployment. Next.js [bakes public variables into the browser build](https://nextjs.org/docs/app/guides/environment-variables), so a new build is required.
4. Open `https://YOUR-SITE.antideploy.app/api/health`. It must return JSON with `status: "ok"`; voice calls also need `provider_configured: true`. `/api/orders` must return the three sample orders. HTML or a 404 at these paths means the combined deployment is not running.
5. Open the website, allow microphone access, and start a call. The browser should connect to `wss://YOUR-SITE.antideploy.app/api/ws/call`. The proxy explicitly forwards WebSocket upgrades and allows a long read timeout.

The container listens on the platform's `PORT` (default `8080`), binds its internal services to loopback, runs as a non-root user, waits for both services before opening the public port, and exits if a service fails. The health endpoint checks configuration and liveness; it does not verify Gemini quota or model access.

### Separate frontend and backend deployments

The existing Dockerfiles in `frontend/` and `backend/` still support separate services. Deploy the backend on a WebSocket-capable host, set frontend `NEXT_PUBLIC_API_URL` to its public HTTPS base URL **before building**, and set the backend `FRONTEND_ORIGINS` to the public frontend origin. `TEST_API_URL` points to that backend and `TEST_BASE_URL` points to the frontend. A frontend-only deployment does not run FastAPI. Never use `localhost` or `127.0.0.1` as the public backend URL, because they refer to each visitor's computer.

For local development, `frontend/.env.local` retains your local URLs. Playwright loads frontend environment files, with explicitly supplied environment variables taking precedence. The backend allows the local frontend on ports 3001 and 3107.

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

