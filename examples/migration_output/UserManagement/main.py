import logging
import os
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
SERVICE_NAME = os.getenv("SERVICE_NAME", "UserManagement")

# Database setup
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ORM models
class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)
    role = Column(String)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProfileORM(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    # Add more profile fields as needed


# Pydantic schemas
class UserBase(BaseModel):
    email: str
    name: str
    role: str = "user"
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(UserBase):
    pass


class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# App setup
app = FastAPI(title=SERVICE_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get("/ready")
async def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logging.error(f"Database connection failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database not available")


# Authentication functions
def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password, hashed_password):
    try:
        salt, stored_hash = hashed_password.split(":")
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return computed_hash == stored_hash
    except (ValueError, AttributeError):
        return False


def authenticate(email: str, password: str, db: Session):
    user_orm = db.query(UserORM).filter_by(email=email, is_active=1).first()
    if not user_orm:
        logging.warning(f"Authentication failed: user not found for {email}")
        return None

    if verify_password(password, user_orm.hashed_password):
        token = secrets.token_urlsafe(32)
        # Store session token in a secure way (e.g., Redis or JWT)
        _log_action(user_orm.id, "LOGIN", f"User {email} logged in")
        logging.info(f"User authenticated: {email}")
        return {"user": User.from_orm(user_orm), "token": token}

    logging.warning(f"Authentication failed: bad password for {email}")
    return None


def validate_session(token):
    # Validate session token from secure storage
    pass


def logout(token):
    # Invalidate session token in secure storage
    pass


# User CRUD endpoints
@app.post("/users/", response_model=User)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(UserORM).filter_by(email=user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    hashed_password = hash_password(user.password)
    new_user_orm = UserORM(
        email=user.email, name=user.name, hashed_password=hashed_password, role=user.role
    )
    db.add(new_user_orm)
    db.commit()
    db.refresh(new_user_orm)

    # Create profile inside user creation — mixed responsibilities
    new_profile_orm = UserProfileORM(user_id=new_user_orm.id)
    db.add(new_profile_orm)
    db.commit()

    _log_action(new_user_orm.id, "USER_CREATED", f"New user: {user.email}")
    logging.info(f"User created: {user.email} (id={new_user_orm.id})")

    return User.from_orm(new_user_orm)


@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user_orm = db.query(UserORM).filter_by(id=user_id).first()
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")
    return User.from_orm(user_orm)


@app.get("/users/email/{email}", response_model=User)
async def get_user_by_email(email: str, db: Session = Depends(get_db)):
    user_orm = db.query(UserORM).filter_by(email=email).first()
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")
    return User.from_orm(user_orm)


@app.get("/users/", response_model=dict)
async def list_users(page: int = 1, per_page: int = 20, db: Session = Depends(get_db)):
    offset = (page - 1) * per_page
    users_orm = (
        db.query(UserORM).order_by(UserORM.created_at.desc()).limit(per_page).offset(offset).all()
    )
    total_rows = db.query(UserORM).count()

    return {
        "users": [User.from_orm(u) for u in users_orm],
        "total": total_rows,
        "page": page,
        "per_page": per_page,
    }


@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    allowed_fields = {"name", "email", "role", "is_active"}
    updates = {k: v for k, v in user_update.dict().items() if k in allowed_fields}

    if not updates:
        return get_user(user_id)

    user_orm = db.query(UserORM).filter_by(id=user_id).first()
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")

    for key, value in updates.items():
        setattr(user_orm, key, value)
    user_orm.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user_orm)

    _log_action(user_id, "USER_UPDATED", f"Updated fields: {list(updates.keys())}")
    logging.info(f"User updated: {user_id}")

    return User.from_orm(user_orm)


@app.delete("/users/{user_id}", response_model=bool)
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    user_orm = db.query(UserORM).filter_by(id=user_id).first()
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")

    user_orm.is_active = 0
    user_orm.updated_at = datetime.utcnow()

    db.commit()

    _log_action(user_id, "USER_DELETED", "User deactivated")
    logging.info(f"User deleted: {user_id}")

    return True


@app.post("/users/{user_id}/change-password/", response_model=bool)
async def change_password(
    user_id: int, old_password: str, new_password: str, db: Session = Depends(get_db)
):
    user_orm = db.query(UserORM).filter_by(id=user_id).first()
    if not user_orm:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(old_password, user_orm.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hashed = hash_password(new_password)
    user_orm.hashed_password = new_hashed
    user_orm.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user_orm)

    _log_action(user_id, "PASSWORD_CHANGED", "Password changed")
    logging.info(f"Password changed for user: {user_id}")

    return True


# Logging function (placeholder)
def _log_action(user_id: int, action: str, message: str):
    # Implement logging to a secure location
    pass
