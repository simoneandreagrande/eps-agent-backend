# Python 3.11 evita problemi con pandas/numpy
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Strumenti di build minimi (leggero ma utile)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Dipendenze (versioni già testate)
RUN pip install --upgrade pip setuptools wheel
RUN pip install fastapi==0.115.0 uvicorn==0.30.6 yfinance==0.2.43 pandas==2.2.2 numpy==1.26.4 pydantic==2.9.2

# Copia il codice
WORKDIR /app
COPY app /app/app

# Avvio (PORT letto dall'ambiente; default 8080)
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
