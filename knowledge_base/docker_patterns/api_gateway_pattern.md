# API Gateway Pattern for Microservices

## Problem
When multiple microservices each run on separate ports, clients need a single entry point. Exposing individual service ports creates coupling, makes CORS harder, and lacks centralized rate limiting.

## Solution: Nginx Reverse Proxy
Use Nginx as an API gateway that routes requests to the correct backend service by path prefix.

```nginx
upstream user-service {
    server user-service:8000;
}

upstream order-service {
    server order-service:8000;
}

server {
    listen 80;
    server_name localhost;

    # Health check for the gateway itself
    location /health {
        return 200 '{"status": "healthy", "service": "api-gateway"}';
        add_header Content-Type application/json;
    }

    # Route to User Service
    location /api/users {
        proxy_pass http://user-service;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Route to Order Service
    location /api/orders {
        proxy_pass http://order-service;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Docker Compose Integration
```yaml
services:
  api-gateway:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      user-service:
        condition: service_healthy
    networks:
      - microservices

  user-service:
    build: ./user-service
    expose:
      - "8000"
    networks:
      - microservices
```

## Key Principles
- Only the gateway exposes ports to the host (`ports:`)
- Backend services use `expose:` (internal only) — not `ports:`
- Use `proxy_set_header` to forward client IP and protocol info
- Add rate limiting with `limit_req_zone` for public endpoints
- Centralize CORS headers at the gateway level when possible
