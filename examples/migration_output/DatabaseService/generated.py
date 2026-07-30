# === main.py ===

import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

# Database setup
DATABASE_URL = "sqlite:///./monolith.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user")
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    updated_at = Column(TIMESTAMP, onupdate=datetime.datetime.utcnow)

    user_profile = relationship("UserProfileORM", uselist=False, back_populates="user")
    orders = relationship("OrderORM", back_populates="user")


class UserProfileORM(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bio = Column(Text)
    avatar_url = Column(String)
    phone = Column(String)
    address = Column(String)


class ProductORM(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, default=0)
    category = Column(String)


class OrderORM(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")
    total_amount = Column(Float, default=0.0)
    shipping_address = Column(String)

    user = relationship("UserORM", back_populates="orders")
    order_items = relationship("OrderItemORM", back_populates="order")


class OrderItemORM(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship("OrderORM", back_populates="order_items")
    product = relationship("ProductORM")


class PaymentORM(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, default="credit_card")
    status = Column(String, default="pending")
    transaction_id = Column(String)


class RefundORM(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(Text)
    status = Column(String, default="pending")


class AuditLogORM(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    action = Column(String, nullable=False)
    details = Column(Text)
    ip_address = Column(String)


# Pydantic Schemas
class UserBaseSchema(BaseModel):
    email: str
    name: str
    hashed_password: str


class UserProfileBaseSchema(BaseModel):
    bio: str | None
    avatar_url: str | None
    phone: str | None
    address: str | None


class ProductBaseSchema(BaseModel):
    name: str
    description: str | None
    price: float
    stock_quantity: int = 0
    category: str | None


class OrderBaseSchema(BaseModel):
    user_id: int
    status: str = "pending"
    total_amount: float = 0.0
    shipping_address: str | None


class OrderItemBaseSchema(BaseModel):
    order_id: int
    product_id: int
    quantity: int
    unit_price: float


class PaymentBaseSchema(BaseModel):
    order_id: int
    user_id: int
    amount: float
    method: str = "credit_card"
    status: str = "pending"


class RefundBaseSchema(BaseModel):
    payment_id: int
    amount: float
    reason: str | None


class AuditLogBaseSchema(BaseModel):
    user_id: int
    action: str
    details: str | None
    ip_address: str | None


# Dependency for database session
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# FastAPI app setup
app = FastAPI()


@app.post("/users/", response_model=UserBaseSchema)
async def create_user(user: UserBaseSchema, db: Session = Depends(get_db)):
    new_user = UserORM(**user.dict())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users/{user_id}", response_model=UserBaseSchema)
async def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/users/{user_id}", response_model=UserBaseSchema)
async def update_user(user_id: int, updated_user: UserBaseSchema, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for key, value in updated_user.dict().items():
        setattr(user, key, value)

    db.commit()
    return user


@app.delete("/users/{user_id}", response_model=UserBaseSchema)
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return user


@app.post("/user_profiles/", response_model=UserProfileBaseSchema)
async def create_user_profile(profile: UserProfileBaseSchema, db: Session = Depends(get_db)):
    new_profile = UserProfileORM(**profile.dict())
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile


# Add more endpoints for other models as needed
