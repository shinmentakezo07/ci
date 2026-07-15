# syntax=docker/dockerfile:1.7
# Free Claude Code — production image.
#
# Multi-stage, reproducible from uv.lock, runs as non-root, listens on 0.0.0.0:8082.
# Built with the uv binary against the system Python 3.14 (no interpreter download);
# the builder and runtime stages share the same python:3.14-slim-bookworm base so the
# venv's interpreter symlinks resolve identically in both.
#
# Build a default (server-only) image:
#   docker build -t free-claude-code:4.6.0 .
#
# Build with optional extras (README/.env.example still required at build time):
#   docker build --build-arg EXTRAS=voice -t free-claude-code:voice .
#   docker build --build-arg EXTRAS=voice,voice_local -t free-claude-code:voice-local .
# (voice_local pulls torch ~2GB+; pair with --gpus all for CUDA.)
#
# Run:
#   docker run --rm -p 8082:8082 free-claude-code:4.6.0
#   Provider keys/model overrides come from `docker run -e` or --env-file.

# uv version must satisfy [tool.uv] required-version >=0.11.0
ARG UV_VERSION=0.11.0
ARG PYTHON_VERSION=3.14

# ---------------------------------------------------------------------------
# Stage 0 — uv binary (copied into the builder; nothing else is used from it)
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------------------------------------------------------------------
# Stage 1 — builder: resolve + install the project into /app/.venv from uv.lock
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder
COPY --from=uv /uv /uvx /usr/local/bin/

# Pin to the image's Python; never fetch an interpreter, copy deps into the venv
# (no bindmounts), and pre-compile bytecode so the runtime stage stays light.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

ARG EXTRAS=""
SHELL ["/bin/bash", "-c"]

# Project metadata + lock first (fast, cacheable layer when only source changes).
# `.env.example` and `README.md` are required at project-build time:
# hatchling force-includes `.env.example` into the wheel and reads `README.md`.
COPY pyproject.toml uv.lock README.md .env.example ./

# Install dependencies (and the chosen extras) WITHOUT the project source, so
# editing src/ does not bust the dependency layer. EXTRAS is a comma list.
RUN uv sync --frozen --no-dev --no-install-project \
        $(IFS=','; for e in $EXTRAS; do echo "--extra $e"; done)

# Now add source and build a real (non-editable) wheel.
COPY src/ ./src/
RUN uv build --no-sources --wheel --out-dir /wheels

# Install the project wheel into the venv. This avoids the editable install
# `uv sync` makes for the root project (its .pth points at /app/src, which the
# runtime stage does not carry) — a built wheel is self-contained.
RUN uv pip install --no-deps --python /app/.venv/bin/python /wheels/free_claude_code-*.whl


# ---------------------------------------------------------------------------
# Stage 2 — runtime: minimal slim image + the built venv, non-root
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Runtime hardening
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/app/.venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# App user (uid 1000). HOME points all runtime state (logs, managed .env,
# agent_workspace) under /home/app/.fcc — mount that to persist config.
RUN groupadd -r app --gid 1000 \
    && useradd -r -g app --uid 1000 -m -d /home/app app \
    && mkdir -p /home/app/.fcc \
    && chown -R app:app /home/app

# Bring in the fully assembled venv (interpreter + deps + the fcc-server script).
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Container-friendly defaults: no browser to open, bind all interfaces.
ENV FCC_OPEN_BROWSER=false \
    HOST=0.0.0.0 \
    PORT=8082 \
    HOME=/home/app

WORKDIR /app
USER app

EXPOSE 8082

# FastAPI exposes GET /health -> {"status":"healthy"} (also HEAD/OPTIONS).
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:${PORT}/health', timeout=3).status==200 else 1)"

CMD ["fcc-server"]
