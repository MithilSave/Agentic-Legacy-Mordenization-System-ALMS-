# Pydantic Schema Design for FastAPI

## Request/Response Models
```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode

class UserList(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
```

## Validation Rules
- Use `EmailStr` for email validation
- Use `Field()` with `min_length`, `max_length`, `ge`, `le` constraints
- Use `Optional[T]` for nullable fields
- Enable `from_attributes = True` for SQLAlchemy ORM integration
- Create separate Create/Update/Response schemas (don't reuse)
