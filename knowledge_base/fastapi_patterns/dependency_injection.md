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

## Best Practices
- Use `yield` for resource cleanup (database sessions, file handles)
- Chain dependencies for middleware-like behavior
- Override dependencies in tests with `app.dependency_overrides`
