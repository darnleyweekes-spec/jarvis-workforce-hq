FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 alpha && useradd --uid 10001 --gid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin alpha \
    && mkdir -p /data && chown 10001:10001 /data
COPY --chown=10001:10001 alpha-runtime/ /app/
USER 10001:10001
EXPOSE 8080
ENV ALPHA_BIND=0.0.0.0 ALPHA_PORT=8080 ALPHA_DB_PATH=/data/alpha.sqlite3
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1
CMD ["python", "-m", "api_server"]
