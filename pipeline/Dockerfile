FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pipeline/pyproject.toml pipeline/README.md ./pipeline/
COPY pipeline/src ./pipeline/src
# torch en version CPU (l'image par défaut embarque CUDA, ~3 Go de plus)
RUN uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu
RUN cd pipeline && uv pip install --system -e '.[embeddings]'
COPY db ./db
COPY sources.yaml ./sources.yaml
COPY config ./config
ENV PYTHONPATH=/app DAGSTER_HOME=/opt/dagster/home
RUN mkdir -p $DAGSTER_HOME
COPY dagster.yaml workspace.yaml $DAGSTER_HOME/
