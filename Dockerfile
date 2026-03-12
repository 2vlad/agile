FROM python:3.12-slim
WORKDIR /app
RUN useradd -r -s /bin/false appuser
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Optional: download custom CA cert for managed databases (e.g. Yandex Cloud)
ARG DB_CA_URL=""
RUN if [ -n "$DB_CA_URL" ]; then \
        apt-get update && apt-get install -y --no-install-recommends curl \
        && curl -sSLo /usr/local/share/ca-certificates/CustomCA.crt "$DB_CA_URL" \
        && update-ca-certificates \
        && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*; \
    fi

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 8080
CMD uvicorn bot.main:app --host 0.0.0.0 --port ${PORT:-8080}
