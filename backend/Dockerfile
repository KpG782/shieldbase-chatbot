FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PORT=8000
ENV CHROMA_PERSIST_DIR=/data/vectorstore
ENV HF_HOME=/data/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/data/sentence-transformers

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY __init__.py /app/__init__.py
COPY env.py /app/env.py
COPY graph.py /app/graph.py
COPY main.py /app/main.py
COPY state.py /app/state.py
COPY nodes /app/nodes
COPY services /app/services
COPY knowledge_base /app/knowledge_base

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/health', timeout=3)"

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
