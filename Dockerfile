FROM python:3.12-slim
# Docker CLI launches separate sandbox containers; never executes code in this image.
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agents agents
COPY tools tools
COPY orchestration orchestration
COPY main.py .
ENV PYTHONUNBUFFERED=1 WORKSPACE_DIR=/data/workspace CHROMA_DIR=/data/chroma
ENTRYPOINT ["python", "main.py"]
CMD ["Write a Python addition function with assertions and execute it."]
