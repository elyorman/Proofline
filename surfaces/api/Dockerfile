# The live API: the product's question path behind uvicorn (surfaces/api/app.py). The demo
# match's feed is generated at build time by the engine's CLI, the way `make m01` does;
# product code never imports the engine, and the sealed suites are not in the build context.
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY . .
RUN uv sync --locked \
 && uv run --no-sync proofline-engine generate --script engine/scripts/planted/m01.yaml --out data/m01/

ENV PYTHONPATH=/app PROOFLINE_DATA=/app/data
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "surfaces.api.app:create", "--factory", "--host", "0.0.0.0", "--port", "8000"]
