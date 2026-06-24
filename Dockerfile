FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app/ ./app/
# Install CPU-only torch first — the app runs on CPU, so this avoids ~5GB of
# unused CUDA wheels that the default torch build (a transitive dep) would pull.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -e "."

EXPOSE 8090

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8090"]
