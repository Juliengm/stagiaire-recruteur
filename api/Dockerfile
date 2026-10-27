FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# rendu de la lettre (WeasyPrint) : Pango et les mêmes polices que sur le poste
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY api/pyproject.toml api/README.md ./api/
COPY api/src ./api/src
RUN cd api && uv pip install --system -e .
COPY db ./db
COPY config ./config
COPY templates ./templates
ENV PYTHONPATH=/app
CMD ["uvicorn", "veille_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
