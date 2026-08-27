"""AUTO-GENERATED STUB — replace with the real service implementation.

Service : sqlite3-cursor-service
Reason  : Refactoring Agent returned zero files (LLM unavailable at generation time)
"""
from fastapi import FastAPI

app = FastAPI(title='sqlite3-cursor-service', description="STUB — pending refactor")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": 'sqlite3-cursor-service', "stub": True}
