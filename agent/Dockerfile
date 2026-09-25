FROM python:3.12-slim
# sounddevice (dependency livekit-agents) butuh PortAudio saat import
RUN apt-get update && apt-get install -y --no-install-recommends libportaudio2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml .
COPY src ./src
# livekit-agents dipin ke versi yang sudah diuji
RUN pip install --no-cache-dir ".[worker]" "livekit-agents==1.8.2"
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "deskcall.worker", "start"]
