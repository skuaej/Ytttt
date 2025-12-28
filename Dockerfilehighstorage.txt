# Dockerfile — yt-dlp + EJS (Deno, no Node)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (required for EJS)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:${PATH}"

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Run FastAPI
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port $PORT"]
