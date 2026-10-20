FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pipeline/pyproject.toml pipeline/README.md ./pipeline/
COPY pipeline/src ./pipeline/src
RUN cd pipeline && uv pip install --system -e .
COPY db ./db
COPY sources.yaml ./sources.yaml
COPY config ./config
ENV PYTHONPATH=/app DAGSTER_HOME=/opt/dagster/home
RUN mkdir -p $DAGSTER_HOME
COPY dagster.yaml workspace.yaml $DAGSTER_HOME/
