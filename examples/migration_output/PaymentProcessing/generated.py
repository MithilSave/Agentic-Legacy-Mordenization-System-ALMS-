import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Database setup
DATABASE_URL = "sqlite:///./payment_processing.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, nullable=False)
    status = Column(String, nullable=False)
    transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    reason = Column(String, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# FastAPI app setup
app = FastAPI()


class PaymentRequest(BaseModel):
    order_id: str
    user_id: str
    amount: float
    method: Optional[str] = "credit_card"


class PaymentResponse(PaymentRequest):
    id: int
    status: str
    transaction_id: Optional[str]


@app.post("/payments/", response_model=PaymentResponse)
def process_payment(payment_request: PaymentRequest, db: Session = Depends(get_db)):
    try:
        # Validate input data
        if payment_request.method not in ["credit_card", "debit_card", "bank_transfer", "wallet"]:
            raise HTTPException(status_code=422, detail="Unsupported payment method")

        if payment_request.amount <= 0:
            raise HTTPException(status_code=422, detail="Payment amount must be positive")

        # Check user existence
        user = db.query(Payment).filter_by(user_id=payment_request.user_id, is_active=True).first()
        if not user:
            raise HTTPException(
                status_code=404, detail=f"User {payment_request.user_id} not found or inactive"
            )

        # Check for duplicate payments
        existing_payment = (
            db.query(Payment)
            .filter_by(order_id=payment_request.order_id, status_in=("completed", "pending"))
            .first()
        )
        if existing_payment:
            raise HTTPException(
                status_code=409,
                detail=f"Payment already exists for order {payment_request.order_id}",
            )

        # Simulate payment gateway call
        transaction_id = _call_payment_gateway(payment_request.amount, payment_request.method)

        # Record payment
        new_payment = Payment(
            order_id=payment_request.order_id,
            user_id=payment_request.user_id,
            amount=round(payment_request.amount, 2),
            method=payment_request.method,
            status="completed" if transaction_id else "failed",
            transaction_id=transaction_id,
        )
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)

        return {**new_payment.__dict__, "id": new_payment.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _call_payment_gateway(amount: float, method: str):
    # Simulate ~95% success rate
    if random.random() < 0.95:
        transaction_id = f"txn_{uuid.uuid4().hex[:16]}"
        return transaction_id
    else:
        return None


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return {**payment.__dict__, "id": payment.id}


@app.get("/payments/status/{order_id}", response_model=dict)
def get_payment_status(order_id: str, db: Session = Depends(get_db)):
    payment = (
        db.query(Payment).filter_by(order_id=order_id, status_in=("completed", "pending")).first()
    )
    if not payment:
        return {"status": "no_payment"}

    return {"status": payment.status}


@app.get("/users/payments/{user_id}", response_model=dict)
def get_user_payments(
    user_id: str, page: int = 1, per_page: int = 10, db: Session = Depends(get_db)
):
    offset = (page - 1) * per_page
    payments = (
        db.query(Payment)
        .filter_by(user_id=user_id)
        .order_by(Payment.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return {
        "payments": [payment.__dict__ for payment in payments],
        "page": page,
        "per_page": per_page,
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Error handling and logging setup
@app.exception_handler(Exception)
async def custom_exception_handler(request, exc):
    logger.error(f"Error processing request: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
