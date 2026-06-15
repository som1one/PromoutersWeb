# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# system deps (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    build-essential \
    curl \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
