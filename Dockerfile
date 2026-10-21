FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl openssl \
    && curl --fail --silent --show-error --location \
        http://crt.sectigo.com/SectigoPublicServerAuthenticationRootR46_USERTrust.crt \
        --output /tmp/sectigo-root-r46.crt \
    && echo "92f351bf3d54164dfa8dd8f9e1139d3150349786485d2b9eecd00e2971c1e6c5  /tmp/sectigo-root-r46.crt" \
        | sha256sum --check --strict \
    && openssl x509 -inform DER -in /tmp/sectigo-root-r46.crt \
        -out /usr/local/share/ca-certificates/sectigo-root-r46.crt \
    && openssl x509 -in /usr/local/share/ca-certificates/sectigo-root-r46.crt \
        -noout -subject -fingerprint -sha256 \
    && update-ca-certificates \
    && openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt \
        /usr/local/share/ca-certificates/sectigo-root-r46.crt \
    && rm -f /tmp/sectigo-root-r46.crt \
    && rm -rf /var/lib/apt/lists/*

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_DIR=/etc/ssl/certs

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

EXPOSE 8000

HEALTHCHECK \
    --interval=60s \
    --timeout=10s \
    --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uv run uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
