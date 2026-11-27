# One image for the API, the ingestion worker and the migration Job (M12.1, D038).
# The medcpt extra (torch/transformers, ~1 GB) is left out on purpose: /rag and
# vector indexing need it and fail fast without it; questions, jobs and probes do not.
FROM ghcr.io/astral-sh/uv:0.11.29 AS uv

FROM python:3.14-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first so code edits do not invalidate the dependency layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --locked --no-dev

FROM python:3.14-slim-trixie
RUN useradd --system --uid 10001 --no-create-home evidenceops
WORKDIR /app
# health.py locates migrations relative to the source tree, so keep /app layout.
COPY --from=build --chown=root:root /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "evidenceops.main:app", "--host", "0.0.0.0", "--port", "8000"]
