FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Both services are reached through the public proxy; no public backend URL is needed.
ENV NEXT_PUBLIC_API_URL=/api NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends nginx libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY --from=frontend-build /build/frontend/.next/standalone ./frontend
COPY --from=frontend-build /build/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-build /build/frontend/public ./frontend/public
COPY deployment/ ./deployment
RUN useradd --create-home support && chown -R support:support /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
USER support
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/health', timeout=4)"
CMD ["python", "deployment/start.py"]
