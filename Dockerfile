# ==========================
#  Etapa 1: Build
# ==========================
FROM python:3.14.2-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==========================
#  Etapa 2: Runtime
# ==========================
FROM python:3.14.2-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

ENV PORT=80

CMD ["gunicorn", "src.Application.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:80", "--workers", "4"]
