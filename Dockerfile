# -------- Base image --------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# -------- System dependencies --------
# ffmpeg is NOT used for merging
# but yt-dlp requires it for metadata + some formats
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -------- Install Deno (EJS solver) --------
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:${PATH}"

# -------- Python dependencies --------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------- App files --------
COPY . .

# -------- Run API --------
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
