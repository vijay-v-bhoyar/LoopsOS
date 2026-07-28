FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/authority \
    LOOPOS_REPO_ROOT=/app \
    LOOPOS_DATABASE_PATH=/data/loopos-authority.db

WORKDIR /app
COPY authority/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt \
    && groupadd --system loopos \
    && useradd --system --gid loopos --home-dir /app loopos \
    && mkdir -p /data \
    && chown loopos:loopos /data

COPY authority /app/authority
COPY runtime /app/runtime
COPY controls /app/controls
COPY probes /app/probes
COPY standards /app/standards
COPY owners /app/owners
COPY evidence /app/evidence
COPY schemas /app/schemas
COPY supabase /app/supabase

USER loopos
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health/live', timeout=3)" || exit 1
CMD ["python", "-m", "uvicorn", "loopos_authority.api:app", "--host", "0.0.0.0", "--port", "8787", "--proxy-headers", "--forwarded-allow-ips=*"]
