# Input Validation Security Pattern

## Problem
Accepting raw user input without validation enables injection attacks, data corruption, and denial-of-service.

## Solution: Pydantic Validation at Service Boundary
```python
from pydantic import BaseModel, EmailStr, constr, validator

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=128)
    name: constr(min_length=1, max_length=100)

    @validator('name')
    def name_must_not_contain_script(cls, v):
        if '<script' in v.lower():
            raise ValueError('Invalid characters in name')
        return v.strip()
```

## SQL Injection Prevention
```python
# VULNERABLE
db.execute(f"SELECT * FROM users WHERE email = '{email}'")

# SAFE (parameterized)
db.execute("SELECT * FROM users WHERE email = ?", (email,))

# SAFE (SQLAlchemy ORM)
db.query(User).filter(User.email == email).first()
```

## Authentication Pattern
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

## Checklist
- [ ] All user input validated via Pydantic models
- [ ] No raw SQL string formatting
- [ ] Passwords hashed with bcrypt/argon2 (not SHA-256)
- [ ] Authentication tokens have expiration
- [ ] Rate limiting on auth endpoints
