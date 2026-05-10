FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY apps ./apps
COPY libs ./libs
COPY tools ./tools
COPY docs ./docs

RUN uv sync --frozen --package idp-config-registry --no-dev

CMD ["idp-config-registry", "serve"]
