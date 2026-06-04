FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DB_PATH=/data/pelada.db

WORKDIR /app

# Dependências primeiro (cache de build)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Diretório do banco (montar um volume aqui para persistir)
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

# Healthcheck simples na raiz (porta fixa 8000 dentro do container)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
