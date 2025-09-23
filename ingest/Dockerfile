FROM python:3.12-slim
WORKDIR /app

# Optional but helpful for logs & speed
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Exec/JSON form so signals are handled correctly
ENTRYPOINT ["/usr/local/bin/python", "-u"]
# leave CMD empty; you’ll pass script/args in `docker run`
