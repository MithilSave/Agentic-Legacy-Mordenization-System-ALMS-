# main.py

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from .database import Base, engine, get_db
from .models import OrderItemORM, OrderORM, ProductORM
from .schemas import OrderCreateSchema, OrderItemSchema, OrderResponseSchema

# Initialize FastAPI app
app = FastAPI()

# Database setup
Base.metadata.create_all(bind=engine)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrderProcessing")


# Dependency to get database session
def get_db_session() -> Session:
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# Pydantic models for request/response validation


class OrderCreateSchema:
    user_id: int
    items: List[OrderItemSchema]
    shipping_address: Optional[str] = None


class OrderResponseSchema(OrderORM):
    class Config:
        orm_mode = True


class OrderItemSchema:
    product_id: int
    quantity: int
    unit_price: float


# SQLAlchemy ORM models

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class OrderORM(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(Float)
    shipping_address = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    items = relationship("OrderItemORM", back_populates="order")


class OrderItemORM(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)

    order = relationship("OrderORM", back_populates="items")
    product = relationship("ProductORM")


class ProductORM(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    stock_quantity = Column(Integer)
    price = Column(Float)


# Database engine setup
from sqlalchemy import create_engine

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL)


def get_db():
    db = engine.connect()
    try:
        yield db
    finally:
        db.close()


# FastAPI routes with comprehensive error handling and logging


@app.post("/orders", response_model=OrderResponseSchema)
async def create_order(order: OrderCreateSchema, db: Session = Depends(get_db_session)):
    user_id = order.user_id
    items = order.items
    shipping_address = order.shipping_address

    # Validate user exists
    if not (user := db.query(ProductORM).filter_by(id=user_id).first()):
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="User is deactivated")

    # Validate items
    total_amount = 0.0
    validated_items = []

    for item in items:
        product_id = item.product_id
        quantity = item.quantity

        if quantity <= 0:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid quantity")

        # Validate products and calculate totals
        product = db.query(ProductORM).filter_by(id=product_id).first()
        if not product:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Product not found")

        if product.stock_quantity < quantity:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Insufficient stock")

        subtotal = product.price * quantity
        total_amount += subtotal
        validated_items.append(
            {
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": product.price,
            }
        )

    if total_amount < 1.00:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST, detail="Order total must be at least $1"
        )

    # Create order
    new_order = OrderORM(
        user_id=user_id,
        total_amount=round(total_amount, 2),
        shipping_address=shipping_address,
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
        db.commit()

        # Update stock
        updated_stock = db.query(ProductORM).filter_by(id=item["product_id"]).first()
        if not updated_stock:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Product not found in database"
            )

        updated_stock.stock_quantity -= item["quantity"]
        db.add(updated_stock)
        db.commit()

    # Auto-process payment
    try:
        # Simulate payment processing (replace with actual implementation)
        if total_amount > 10.00:  # Example condition for payment processing
            new_order.status = "confirmed"
            db.commit()
    except Exception as e:
        logger.error(f"Payment failed for order {new_order.id}: {e}")
        new_order.status = "payment_failed"
        db.commit()

    return new_order


@app.get("/orders/{order_id}", response_model=OrderResponseSchema)
async def get_order(order_id: int, db: Session = Depends(get_db_session)):
    order = db.query(OrderORM).filter_by(id=order_id).first()
    if not order:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Order not found")

    # Fetch order items
    item_rows = db.execute(
        """SELECT oi.*, p.name as product_name
           FROM order_items oi
           JOIN products p ON oi.product_id = p.id
           WHERE oi.order_id = :order_id""",
        {"order_id": order_id},
    ).fetchall()

    items = []
    for row in item_rows:
        items.append(
            {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "quantity": row["quantity"],
                "unit_price": row["unit_price"],
                "subtotal": row["quantity"] * row["unit_price"],
            }
        )

    result = order.to_dict()
    result["items"] = items
    return result


@app.get("/users/{user_id}/orders", response_model=List[OrderResponseSchema])
async def get_user_orders(
    user_id: int,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db_session),
):
    query = "SELECT * FROM orders WHERE user_id = :user_id"
    params = {"user_id": user_id}

    if status:
        query += " AND status = :status"
        params["status"] = status

    offset = (page - 1) * per_page
    results = db.execute(query, params).fetchall()[offset : offset + per_page]

    orders = [OrderORM.from_row(row) for row in results]
    return [order.to_dict() for order in orders]


# Example usage of the database session
def main():
    with get_db_session() as db:
        # Example data insertion (for testing purposes)
        product1 = ProductORM(name="Product 1", stock_quantity=10, price=2.50)
        product2 = ProductORM(name="Product 2", stock_quantity=5, price=3.75)

        db.add_all([product1, product2])
        db.commit()


if __name__ == "__main__":
    main()
