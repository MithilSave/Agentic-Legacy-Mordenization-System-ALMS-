"""AUTO-GENERATED STUB — replace with the real service implementation.

Service : models-service
Reason  : Refactoring Agent returned zero files (LLM unavailable at generation time)
"""
from fastapi import FastAPI

app = FastAPI(title='models-service', description="STUB — pending refactor")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": 'models-service', "stub": True}
