# FastAPI Health Check Endpoints

## Why Health Checks Matter
Docker, Kubernetes, and load balancers use health check endpoints to determine if a service is alive and ready to handle traffic. Without them, containers may receive traffic before they're ready, or continue receiving traffic after a failure.

## Liveness Check (`/health`)
Returns 200 if the service process is running. Used by Docker `HEALTHCHECK`.

```python
@app.get("/health")
async def health_check():
    """Liveness probe — is the process alive?"""
    return {"status": "healthy", "service": "user-service"}
```

## Readiness Check (`/ready`)
Returns 200 only if the service can actually handle requests (e.g., database is reachable).

```python
@app.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe — can we handle requests?"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )
```

## Best Practices
- `/health` should be lightweight — no database calls, no authentication
- `/ready` should verify external dependencies (database, cache, downstream services)
- Always include the service name in the response for debugging in logs
- Register health endpoints first so they respond even during app initialization
- Do not require authentication on health endpoints — orchestrators need unauthenticated access
