FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src ./src
USER app
CMD ["python", "-c", "from src.telemetry.logging_tracing import configure_logging; configure_logging(); print('quant-engine ready')"]
