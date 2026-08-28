# CORS Middleware for FastAPI Microservices

## Problem
When microservices run in separate Docker containers (each on a different port or domain), browsers block cross-origin requests by default. CORS (Cross-Origin Resource Sharing) middleware must be configured to allow inter-service and frontend-to-backend communication.

## Solution
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="User Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Production Configuration
In production, replace `allow_origins=["*"]` with explicit origins:
```python
import os

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
```

## Best Practices
- Never use `allow_origins=["*"]` with `allow_credentials=True` in production
- Configure CORS at the API gateway level when using Nginx
- Use environment variables for allowed origins so they can change per deployment
- Only allow the HTTP methods your API actually uses
