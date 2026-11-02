FROM python:3.12-slim

# zona horaria (slim no la trae)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# dependencias primero para aprovechar la caché
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY asistente_ia/ asistente_ia/

# logs sin búfer
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "asistente_ia.telegram_bot"]
