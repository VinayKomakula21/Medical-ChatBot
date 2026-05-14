# Backend image — FastAPI + Uvicorn.
# Multi-stage so the runtime image doesn't carry build toolchain.
# Final image target: ~250 MB (sentence-transformers + torch are the bulk).
#
# Port: binds to $PORT, default 7860 to match Hugging Face Spaces convention.
# Local compose sets PORT=8000. Render / Cloud Run / Fly inject their own
# $PORT — all work unmodified.

FROM python:3.11-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps needed to compile a few wheels (faiss/grpc on some arches).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

# libgomp is needed by torch/onnxruntime on slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring in the user-site site-packages from the build stage.
COPY --from=build /root/.local /root/.local

# App code.
COPY app ./app
COPY run_dev.py ./
COPY pyproject.toml ./

# Uploads dir for runtime document upload feature.
RUN mkdir -p uploads

ENV PORT=7860
EXPOSE 7860

# Shell form so $PORT is expanded at container start. Tune workers in compose.
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
