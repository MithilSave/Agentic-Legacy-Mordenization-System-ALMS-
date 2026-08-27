"""AUTO-GENERATED STUB — replace with the real service implementation.

Service : payments-request-service
Reason  : Refactoring Agent returned zero files (LLM unavailable at generation time)
"""
from fastapi import FastAPI

app = FastAPI(title='payments-request-service', description="STUB — pending refactor")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": 'payments-request-service', "stub": True}
