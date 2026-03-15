FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SIGN_APP_OPEN_BROWSER=0 \
    PORT=5000

WORKDIR /app

COPY requirements.deploy.txt .
RUN pip install --no-cache-dir -r requirements.deploy.txt

COPY app.py wsgi.py ./
COPY templates ./templates
COPY static ./static
COPY models ./models

EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 wsgi:app"]
