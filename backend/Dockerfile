# backend/Dockerfile
FROM python:3.12-slim
WORKDIR /app

# quality-of-life
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code
COPY . .

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/uvicorn"]

CMD ["main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*", "--access-log", "--log-level", "info"]
