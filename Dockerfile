# Frontend output is architecture independent: build it natively on the build host.
FROM --platform=$BUILDPLATFORM node:22-alpine AS web
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --registry=$NPM_REGISTRY
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL \
    PYTHONUNBUFFERED=1 \
    HUB_DATA=/data
WORKDIR /app
COPY backend/requirements.txt backend/
# gcc covers packages without prebuilt wheels on arm64 (e.g. netifaces-plus)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
 && pip install --no-cache-dir -r backend/requirements.txt \
 && pip install --no-cache-dir --no-deps python-miio==0.5.12 \
 && apt-get purge -y gcc libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist
WORKDIR /app/backend
EXPOSE 8080
CMD ["python", "-m", "homehub"]
