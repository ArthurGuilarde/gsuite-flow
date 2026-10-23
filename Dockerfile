FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_PROFILE=production
WORKDIR /app
COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
COPY alembic.ini ./
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"]
# The CLI enforces the production guards (no owner credential, no reload) before starting Uvicorn.
CMD ["python", "-m", "src", "serve", "--profile", "production", "--host", "0.0.0.0", "--port", "8000"]
