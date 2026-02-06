FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ffmpeg is required for merge/conversion
RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

RUN mkdir -p /data

ENV DOWNLOAD_DIR=/data \
    PORT=8090

EXPOSE 8090

# Default command runs the web server; compose overrides for worker/cleaner
CMD ["python", "-m", "app.main"]
