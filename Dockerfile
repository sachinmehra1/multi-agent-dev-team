FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends docker-cli \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bake the public embedding model into the image; clean startup needs no host cache.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"
COPY agents agents
COPY tools tools
COPY orchestration orchestration
COPY main.py project_main.py team_main.py production_main.py ./
COPY tests/fixtures tests/fixtures
# Verify dependency integrity before publishing the deployment image.
RUN pip check && python -c "import typing_extensions, chromadb, langgraph, pydantic; assert hasattr(typing_extensions, 'TypeAlias')"
ENV PYTHONUNBUFFERED=1 WORKSPACE_DIR=/data/workspace CHROMA_DIR=/data/chroma OUTPUT_ROOT=/app/docs
ENTRYPOINT ["python", "production_main.py"]
