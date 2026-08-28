import logging
import os
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
SERVICE_NAME = os.getenv("SERVICE_NAME", "OrderProcessing")

# Database setup
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ORM models
class OrderORM(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    shipping_address = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderItemORM(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)


class ProductORM(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, default=0)


# Pydantic schemas
class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int


class CreateOrderRequest(BaseModel):
    user_id: int
    items: list[OrderItemSchema]
    shipping_address: str | None = None


class OrderResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    shipping_address: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemSchema]


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
        raise HTTPException(status_code=503, detail="Database not available")


# Order endpoints
@app.post("/orders/", response_model=OrderResponse)
async def create_order(request: CreateOrderRequest, db: Session = Depends(get_db)):
    # Validate user exists (mocked for demonstration)
    if request.user_id != 1:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate items
    if not request.items or len(request.items) > 50:
        raise HTTPException(status_code=400, detail="Invalid number of items")

    total_amount = 0.0
    validated_items = []

    for item in request.items:
        product_row = db.query(ProductORM).filter(ProductORM.id == item.product_id).first()
        if not product_row:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        if product_row.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400, detail=f"Insufficient stock for product {product_row.name}"
            )

        subtotal = product_row.price * item.quantity
        total_amount += subtotal
        validated_items.append(
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": product_row.price,
            }
        )

    if total_amount < 1.00:
        raise HTTPException(status_code=400, detail="Order total must be at least $1.00")

    # Create order
    new_order = OrderORM(
        user_id=request.user_id,
        total_amount=round(total_amount, 2),
        shipping_address=request.shipping_address,
        status="pending",
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Insert order items and update stock
    for item in validated_items:
        new_item = OrderItemORM(
            order_id=new_order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )
        db.add(new_item)
        db.query(ProductORM).filter(ProductORM.id == item["product_id"]).update(
            {"stock_quantity": ProductORM.stock_quantity - item["quantity"]}
        )
    db.commit()

    # Mock payment processing
    if True:  # Replace with actual payment logic
        new_order.status = "confirmed"
        db.commit()
    else:
        new_order.status = "payment_failed"
        db.commit()

    return get_order(new_order.id, db)


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    order_row = db.query(OrderORM).filter(OrderORM.id == order_id).first()
    if not order_row:
        raise HTTPException(status_code=404, detail="Order not found")

    item_rows = (
        db.query(OrderItemORM, ProductORM)
        .join(ProductORM, OrderItemORM.product_id == ProductORM.id)
        .filter(OrderItemORM.order_id == order_id)
        .all()
    )

    items = []
    for item_row in item_rows:
        item, product = item_row
        items.append(
            {
                "product_id": item.product_id,
                "product_name": product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.quantity * item.unit_price,
            }
        )

    result = {
        "id": order_row.id,
        "user_id": order_row.user_id,
        "total_amount": order_row.total_amount,
        "shipping_address": order_row.shipping_address,
        "status": order_row.status,
        "created_at": order_row.created_at,
        "updated_at": order_row.updated_at,
        "items": items,
    }
    return result


@app.get("/users/{user_id}/orders/", response_model=list[OrderResponse])
async def get_user_orders(
    user_id: int,
    status: str | None = None,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db),
):
    query = db.query(OrderORM).filter(OrderORM.user_id == user_id)
    if status:
        query = query.filter(OrderORM.status == status)

    orders = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for order in orders:
        item_rows = (
            db.query(OrderItemORM, ProductORM)
            .join(ProductORM, OrderItemORM.product_id == ProductORM.id)
            .filter(OrderItemORM.order_id == order.id)
            .all()
        )

        items = []
        for item_row in item_rows:
            item, product = item_row
            items.append(
                {
                    "product_id": item.product_id,
                    "product_name": product.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "subtotal": item.quantity * item.unit_price,
                }
            )

        result.append(
            {
                "id": order.id,
                "user_id": order.user_id,
                "total_amount": order.total_amount,
                "shipping_address": order.shipping_address,
                "status": order.status,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "items": items,
            }
        )

    return result
