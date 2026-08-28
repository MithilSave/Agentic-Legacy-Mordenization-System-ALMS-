import logging
import os
import random
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
SERVICE_NAME = os.getenv("SERVICE_NAME", "PaymentProcessing")

# Database setup
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ORM models
class PaymentORM(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, nullable=False)
    status = Column(String, nullable=False)
    transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefundORM(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False)
    reason = Column(String, nullable=True)
    amount_refunded = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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


# Schemas
class PaymentCreate(BaseModel):
    order_id: int
    user_id: int
    amount: float = Field(..., gt=0)
    method: str


class PaymentResponse(BaseModel):
    payment_id: int
    order_id: int
    amount: float
    status: str
    transaction_id: str | None
    method: str


class RefundCreate(BaseModel):
    order_id: int
    reason: str | None = None


# Endpoints
@app.post("/payments", response_model=PaymentResponse)
async def process_payment(payment: PaymentCreate, db: Session = Depends(get_db)):
    if payment.method not in ["credit_card", "debit_card", "bank_transfer", "wallet"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported payment method"
        )

    existing_payment = (
        db.query(PaymentORM)
        .filter(
            PaymentORM.order_id == payment.order_id, PaymentORM.status.in_(["completed", "pending"])
        )
        .first()
    )
    if existing_payment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payment already exists for order"
        )

    transaction_id = _call_payment_gateway(amount=payment.amount, method=payment.method)
    status = "completed" if transaction_id else "failed"

    new_payment = PaymentORM(
        order_id=payment.order_id,
        user_id=payment.user_id,
        amount=payment.amount,
        method=payment.method,
        status=status,
        transaction_id=transaction_id,
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    return {
        "payment_id": new_payment.id,
        "order_id": new_payment.order_id,
        "amount": new_payment.amount,
        "status": new_payment.status,
        "transaction_id": new_payment.transaction_id,
        "method": new_payment.method,
    }


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(PaymentORM).filter(PaymentORM.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    return {
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "status": payment.status,
        "transaction_id": payment.transaction_id,
        "method": payment.method,
    }


@app.post("/refunds", response_model=RefundCreate)
async def process_refund(refund: RefundCreate, db: Session = Depends(get_db)):
    # Find the payment for this order
    payment = (
        db.query(PaymentORM)
        .filter(PaymentORM.order_id == refund.order_id, PaymentORM.status == "completed")
        .order_by(PaymentORM.created_at.desc())
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed payment found for this order",
        )

    # Simulate refund processing
    amount_refunded = (
        payment.amount
    )  # In a real scenario, you would call the payment gateway to process the refund
    new_refund = RefundORM(
        order_id=refund.order_id, reason=refund.reason, amount_refunded=amount_refunded
    )
    db.add(new_refund)
    db.commit()
    db.refresh(new_refund)

    return {
        "order_id": new_refund.order_id,
        "reason": new_refund.reason,
        "amount_refunded": new_refund.amount_refunded,
    }


def _call_payment_gateway(amount, method):
    """Simulate calling an external payment gateway."""
    if random.random() < 0.95:
        transaction_id = f"txn_{uuid.uuid4().hex[:16]}"
        logging.info(f"Gateway approved: {transaction_id} for amount {amount}")
        return transaction_id
    else:
        logging.warning(f"Gateway declined payment for amount {amount}")
        return None


# Error handling and logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
