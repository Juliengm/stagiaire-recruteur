FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY api/pyproject.toml api/README.md ./api/
COPY api/src ./api/src
RUN cd api && uv pip install --system -e .
COPY db ./db
COPY config ./config
ENV PYTHONPATH=/app
CMD ["uvicorn", "veille_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
