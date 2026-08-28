# Dockerfile Best Practices for FastAPI Microservices

## Multi-Stage Build Pattern
Use a two-stage build to keep the final image small and secure.
```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Set ownership and switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose service port
EXPOSE 8000

# Health check — Docker will mark the container unhealthy if this fails
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Use exec form so signals (SIGTERM) are forwarded to uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

## Layer Caching Optimization
Always copy `requirements.txt` and install dependencies BEFORE copying application code. This way, Docker caches the dependency layer and only rebuilds it when requirements change.

```dockerfile
# GOOD: Dependencies cached separately from code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# BAD: Any code change invalidates the dependency cache
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
```

## .dockerignore Template
Always include a `.dockerignore` to exclude unnecessary files from the build context:
```
__pycache__/
*.pyc
*.pyo
.git/
.env
.venv/
*.md
tests/
.pytest_cache/
.mypy_cache/
```

## Security Best Practices
- Never run containers as root — always create and switch to a non-root user
- Use `--no-cache-dir` with pip to avoid storing package caches in the image
- Pin base image versions (e.g., `python:3.11.9-slim`) in production
- Do not copy `.env` files into images — use runtime environment variables
- Scan images with `docker scout` or `trivy` before deploying

## Signal Handling
Always use the exec form of CMD (`["cmd", "arg"]`) instead of shell form (`cmd arg`). The exec form ensures that process signals like SIGTERM are forwarded directly to uvicorn, enabling graceful shutdown.
