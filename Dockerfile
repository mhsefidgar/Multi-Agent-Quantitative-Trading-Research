FROM python:3.11-slim AS builder
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
COPY src ./src
RUN pip install --prefix=/install .

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app
WORKDIR /app

COPY --from=builder /install /usr/local
COPY src ./src

USER app

# The image is intentionally a runtime base. Override CMD with the real
# worker entry point when deploying the event-processing service.
CMD ["python", "-m", "src.worker"]
