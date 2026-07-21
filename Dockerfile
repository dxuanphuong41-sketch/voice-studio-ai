FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY requirements-tts.txt ./
RUN pip install --no-cache-dir -r requirements-tts.txt

COPY gemini_tts.py tts_web.py ./
COPY player_blur/__init__.py player_blur/config.py ./player_blur/

RUN mkdir -p /app/data/downloads /app/data/outputs /app/data/temp /app/data/config \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT', '7860') + '/health', timeout=3)" || exit 1

CMD ["sh", "-c", "uvicorn tts_web:app --host 0.0.0.0 --port ${PORT:-7860}"]
