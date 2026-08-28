# Docker Compose Patterns for Microservice Deployments

## Service Networking
Use a custom bridge network so services can communicate by container name. Docker's built-in DNS resolves service names automatically.

```yaml
services:
  user-service:
    build: ./user-service
    networks:
      - microservices
    environment:
      - DATABASE_URL=sqlite:///./data/app.db
      - SERVICE_NAME=user-service

  order-service:
    build: ./order-service
    networks:
      - microservices
    environment:
      - DATABASE_URL=sqlite:///./data/app.db
      - USER_SERVICE_URL=http://user-service:8000

networks:
  microservices:
    driver: bridge
```

## Health Checks and Dependency Ordering
Use `healthcheck` and `depends_on` with `condition: service_healthy` so services start in the correct order.

```yaml
services:
  user-service:
    build: ./user-service
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s

  order-service:
    build: ./order-service
    depends_on:
      user-service:
        condition: service_healthy
```

## Environment Variable Configuration
Use `.env` files for local development and environment variables for production. Never hardcode secrets.

```yaml
services:
  user-service:
    build: ./user-service
    env_file:
      - .env
    environment:
      - SERVICE_NAME=user-service
      - LOG_LEVEL=INFO
```

## Resource Limits
Set memory and CPU limits to prevent a single service from consuming all host resources.

```yaml
services:
  user-service:
    build: ./user-service
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
        reservations:
          memory: 128M
```

## Logging Configuration
Use structured JSON logging so log aggregators can parse service output.

```yaml
services:
  user-service:
    build: ./user-service
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## Volume Mounts for Persistent Data
Use named volumes for data that must survive container restarts.

```yaml
services:
  user-service:
    build: ./user-service
    volumes:
      - user-data:/app/data

volumes:
  user-data:
```

## Anti-Patterns to Avoid
- Don't expose all service ports to the host — only expose the API gateway
- Don't use `links:` (deprecated) — use networks instead
- Don't hardcode container IPs — use service names for DNS resolution
- Don't skip health checks — they are essential for dependency ordering
- Don't mount source code volumes in production (only use for local development)
