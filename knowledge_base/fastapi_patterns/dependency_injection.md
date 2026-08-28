# FastAPI Dependency Injection Pattern

## Context
FastAPI uses Python type hints and `Depends()` for automatic dependency resolution. This replaces global state and enables testability.

## Pattern: Database Session
```python
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    return db.query(User).filter(User.id == user_id).first()
```

## Pattern: Authentication
```python
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(credentials = Depends(security), db = Depends(get_db)):
    token = credentials.credentials
    user = verify_token(token, db)
    if not user:
        raise HTTPException(status_code=401)
    return user

@app.get("/protected")
async def protected_route(user = Depends(get_current_user)):
    return {"message": f"Hello {user.name}"}
```

## Pattern: Environment-Based Configuration (for Docker)
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Read database URL from environment variable (set by Docker/docker-compose)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

This pattern is essential for Docker deployments where the database URL changes between environments (local SQLite, staging PostgreSQL, production managed DB).

## Best Practices
- Use `yield` for resource cleanup (database sessions, file handles)
- Chain dependencies for middleware-like behavior
- Override dependencies in tests with `app.dependency_overrides`
- Always read connection strings from environment variables — never hardcode them
- Use `os.getenv("VAR", "default")` to provide sensible defaults for local development
