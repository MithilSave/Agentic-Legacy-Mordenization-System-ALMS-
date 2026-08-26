import os
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()

# Database setup
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

# OAuth2 password bearer for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)
    role = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(String)
    updated_at = Column(String)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))


# Pydantic models
class UserInDB(User):
    pass


class TokenData(BaseModel):
    email: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "user"


class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]
    role: Optional[str]


class UserResponse(UserInDB):
    token: str


# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Utility functions
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(hashed_password: str, password: str) -> bool:
    try:
        salt, stored_hash = hashed_password.split(":")
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return computed_hash == stored_hash
    except (ValueError, AttributeError):
        return False


def authenticate(email: str, password: str, db: Session) -> Optional[UserInDB]:
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        logger.warning(f"Authentication failed: user not found for {email}")
        return None

    if verify_password(password, user.hashed_password):
        token = secrets.token_urlsafe(32)
        db_user = UserInDB.from_orm(user)
        _log_action(db_user.id, "LOGIN", f"User {db_user.email} logged in")
        logger.info(f"User authenticated: {email}")
        return {"user": db_user.to_dict(), "token": token}

    logger.warning(f"Authentication failed: bad password for {email}")
    return None


def validate_session(token: str, db: Session) -> Optional[dict]:
    user = authenticate(None, None, db)
    if user and user["token"] == token:
        return user
    return None


def logout(token: str, db: Session) -> bool:
    session = validate_session(token, db)
    if session:
        _log_action(session["user_id"], "LOGOUT", "User logged out")
        del _active_sessions[token]
        return True
    return False


# CRUD operations
def create_user(user_data: UserCreate, db: Session) -> UserResponse:
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with email already exists")

    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        name=user_data.name,
        hashed_password=hashed_password,
        role=user_data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create profile inside user creation — mixed responsibilities
    profile = UserProfile(user_id=new_user.id)
    db.add(profile)
    db.commit()

    _log_action(new_user.id, "USER_CREATED", f"New user: {new_user.email}")
    logger.info(f"User created: {new_user.email} (id={new_user.id})")

    return UserResponse.from_orm(new_user)


def get_user(user_id: int, db: Session) -> Optional[UserResponse]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    return UserResponse.from_orm(user)


def get_user_by_email(email: str, db: Session) -> Optional[UserResponse]:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    return UserResponse.from_orm(user)


def list_users(db: Session, page: int = 1, per_page: int = 20) -> dict:
    offset = (page - 1) * per_page
    rows = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(per_page)
    total_rows = db.query(User).count()
    total = total_rows if total_rows else 0

    return {
        "users": [UserResponse.from_orm(user) for user in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def update_user(user_id: int, user_data: UserUpdate, db: Session) -> Optional[UserResponse]:
    allowed_fields = {"name", "email", "role", "is_active"}
    updates = {k: v for k, v in user_data.dict().items() if k in allowed_fields}

    if not updates:
        return get_user(user_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [user_id]

    db.execute(
        f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values
    )
    db.commit()

    _log_action(user_id, "USER_UPDATED", f"Updated fields: {list(updates.keys())}")
    return get_user(user_id)


def delete_user(user_id: int, db: Session) -> bool:
    db.query(User).filter(User.id == user_id).update(
        {"is_active": False}, synchronize_session=False
    )
    db.commit()
    _log_action(user_id, "USER_DELETED", "User deactivated")
    return True


def change_password(user_id: int, old_password: str, new_password: str, db: Session) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hashed = hash_password(new_password)
    db.query(User).filter(User.id == user_id).update(
        {"hashed_password": new_hashed}, synchronize_session=False
    )
    db.commit()
    return True


# FastAPI app setup
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

app = FastAPI()


@app.post("/token", response_model=UserResponse)
async def login_for_access_token(email: str, password: str, db: Session = Depends(get_db)):
    user = authenticate(email, password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserResponse.from_orm(user)


@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(user, db)


@app.get("/users/{user_id}", response_model=UserResponse)
async def read_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user(user_id, db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/", response_model=dict)
async def list_users(db: Session = Depends(get_db), page: int = 1, per_page: int = 20):
    return list_users(db, page, per_page)


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    return update_user(user_id, user_data, db)


@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    if not delete_user(user_id, db):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}


@app.put("/users/{user_id}/password", response_model=UserResponse)
async def change_password(
    user_id: int, old_password: str, new_password: str, db: Session = Depends(get_db)
):
    if not change_password(user_id, old_password, new_password, db):
        raise HTTPException(status_code=400, detail="Password update failed")
    return {"message": "Password changed"}


# Dependency for current user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    session = validate_session(token, db)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return UserResponse.from_orm(UserInDB(**session))


@app.get("/protected", response_model=dict)
async def protected_route(user: UserResponse = Depends(get_current_user)):
    return {"message": f"Hello {user.name}"}


# Error handling
from fastapi import HTTPException, Request


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"{exc.detail}", exc_info=True)
    return {"detail": exc.detail, "status_code": exc.status_code}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).microseconds
    logger.info(f"Request {request.method} to {request.url.path} took {process_time} microseconds")
    return response


# Logging setup
import logging

logger = logging.getLogger("user_management")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
