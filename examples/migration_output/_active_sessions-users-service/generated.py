"""AUTO-GENERATED STUB — replace with the real service implementation.

Service : _active_sessions-users-service
Reason  : Refactoring Agent returned zero files (LLM unavailable at generation time)
"""
from fastapi import FastAPI

app = FastAPI(title='_active_sessions-users-service', description="STUB — pending refactor")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": '_active_sessions-users-service', "stub": True}
