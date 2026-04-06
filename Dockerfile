# HeartMuLa Studio - Docker Image
# RTX 5080 (Blackwell sm_120) için PyTorch 2.7 + CUDA 12.8

# =============================================================================
# Stage 1: Build Frontend
# =============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Final Image
# =============================================================================
FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    ffmpeg \
    libsndfile1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /app

RUN useradd -m -u 1000 heartmula && \
    mkdir -p /app/backend/models /app/backend/generated_audio /app/backend/ref_audio /app/backend/db && \
    chown -R heartmula:heartmula /app

# pip yükselt
RUN pip3 install --no-cache-dir --upgrade pip

# PyTorch 2.7 + CUDA 12.8 — TEK SEFERDE (RTX 5080 sm_120 desteği)
RUN pip3 install --no-cache-dir \
    torch==2.7.0 \
    torchvision==0.22.0 \
    torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu128

# Diğer bağımlılıklar (torch hariç)
COPY --chown=heartmula:heartmula backend/requirements.txt /app/backend/
RUN pip3 install --no-cache-dir \
    bitsandbytes \
    accelerate \
    -r /app/backend/requirements.txt

# Kod kopyala
COPY --chown=heartmula:heartmula backend/ /app/backend/
COPY --from=frontend-builder --chown=heartmula:heartmula /app/frontend/dist /app/frontend/dist
COPY --chown=heartmula:heartmula start.sh /app/

ENV PYTHONUNBUFFERED=1 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    HEARTMULA_4BIT=auto \
    HEARTMULA_SEQUENTIAL_OFFLOAD=auto \
    HF_HOME=/app/backend/models \
    TORCHINDUCTOR_CACHE_DIR=/app/backend/models/.torch_cache

EXPOSE 8000
USER heartmula

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python3", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
