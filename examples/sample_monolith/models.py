"""
Sample Monolith — Data Models
==============================
Plain data classes used across all modules.
ANTI-PATTERN: Shared models create cross-module coupling.
"""


class User:
    """User data model — shared across users, orders, and payments modules."""

    def __init__(self, id=None, email=None, name=None, hashed_password=None,
                 is_active=True, role="user", created_at=None, updated_at=None):
        self.id = id
        self.email = email
        self.name = name
        self.hashed_password = hashed_password
        self.is_active = is_active
        self.role = role
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
            "role": self.role,
            "created_at": str(self.created_at) if self.created_at else None,
        }

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=row["id"], email=row["email"], name=row["name"],
            hashed_password=row["hashed_password"], is_active=bool(row["is_active"]),
            role=row["role"], created_at=row["created_at"], updated_at=row["updated_at"]
        )


class UserProfile:
    """Extended user profile data."""

    def __init__(self, id=None, user_id=None, bio=None, avatar_url=None,
                 phone=None, address=None):
        self.id = id
        self.user_id = user_id
        self.bio = bio
        self.avatar_url = avatar_url
        self.phone = phone
        self.address = address

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "phone": self.phone,
            "address": self.address,
        }


class Product:
    """Product data model."""

    def __init__(self, id=None, name=None, description=None, price=0.0,
                 stock_quantity=0, category=None, created_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.price = price
        self.stock_quantity = stock_quantity
        self.category = category
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock_quantity": self.stock_quantity,
            "category": self.category,
        }

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=row["id"], name=row["name"], description=row["description"],
            price=row["price"], stock_quantity=row["stock_quantity"],
            category=row["category"], created_at=row["created_at"]
        )


class Order:
    """Order data model — depends on User and Product."""

    def __init__(self, id=None, user_id=None, status="pending", total_amount=0.0,
                 shipping_address=None, items=None, created_at=None, updated_at=None):
        self.id = id
        self.user_id = user_id
        self.status = status
        self.total_amount = total_amount
        self.shipping_address = shipping_address
        self.items = items or []
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "total_amount": self.total_amount,
            "shipping_address": self.shipping_address,
            "items": [item.to_dict() for item in self.items] if self.items else [],
            "created_at": str(self.created_at) if self.created_at else None,
        }

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=row["id"], user_id=row["user_id"], status=row["status"],
            total_amount=row["total_amount"], shipping_address=row["shipping_address"],
            created_at=row["created_at"], updated_at=row["updated_at"]
        )


class OrderItem:
    """Individual order line item."""

    def __init__(self, id=None, order_id=None, product_id=None,
                 quantity=1, unit_price=0.0):
        self.id = id
        self.order_id = order_id
        self.product_id = product_id
        self.quantity = quantity
        self.unit_price = unit_price

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "subtotal": self.quantity * self.unit_price,
        }


class Payment:
    """Payment data model — depends on Order and User."""

    def __init__(self, id=None, order_id=None, user_id=None, amount=0.0,
                 method="credit_card", status="pending", transaction_id=None,
                 created_at=None):
        self.id = id
        self.order_id = order_id
        self.user_id = user_id
        self.amount = amount
        self.method = method
        self.status = status
        self.transaction_id = transaction_id
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "method": self.method,
            "status": self.status,
            "transaction_id": self.transaction_id,
        }


class Refund:
    """Refund data model."""

    def __init__(self, id=None, payment_id=None, amount=0.0,
                 reason=None, status="pending", created_at=None):
        self.id = id
        self.payment_id = payment_id
        self.amount = amount
        self.reason = reason
        self.status = status
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "payment_id": self.payment_id,
            "amount": self.amount,
            "reason": self.reason,
            "status": self.status,
        }
