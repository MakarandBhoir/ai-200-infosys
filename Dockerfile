# Day 1 demo image. The app listens on port 5000 (not 80 or 8080) on purpose,
# so you can show why App Service needs the WEBSITES_PORT app setting.
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ARG GIT_SHA=local
ENV GIT_SHA=${GIT_SHA} \
    APP_VERSION=1.0.0 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 5000
# CMD can be overridden by the App Service startup command.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:app"]
