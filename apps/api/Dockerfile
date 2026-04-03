FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    RUN_MIGRATIONS=0

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).read()"

CMD ["sh", "-c", "if [ \"${RUN_MIGRATIONS}\" = \"1\" ]; then alembic upgrade head; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
