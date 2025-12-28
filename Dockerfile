FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    ffmpeg \
    redis-server \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Start Redis + API
CMD redis-server --daemonize yes && \
    uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
