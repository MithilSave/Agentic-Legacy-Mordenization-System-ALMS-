"""AUTO-GENERATED STUB — replace with the real service implementation.

Service : order-orders-service
Reason  : Refactoring Agent returned zero files (LLM unavailable at generation time)
"""
from fastapi import FastAPI

app = FastAPI(title='order-orders-service', description="STUB — pending refactor")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": 'order-orders-service', "stub": True}
