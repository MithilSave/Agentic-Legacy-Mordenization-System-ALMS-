
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st
from sqlalchemy.orm import Session

from main import app, get_db, OrderORM, ProductORM, OrderItemORM

# Setup test client

# Fixtures for database session and setup/teardown
@pytest.fixture(autouse=True)


@pytest.fixture


@pytest.fixture


# Unit tests for each endpoint


def test_create_order_insufficient_stock(product, db_session):
    product.stock_quantity = 2
    db_session.commit()
    order_data = {
        "user_id": 1,
        "items": [{"product_id": product.id, "quantity": 5}],
        "shipping_address": "Test Address"
    }
    response = client.post("/orders/", json=order_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Insufficient stock for product 1"}


# Property-based test using Hypothesis

@given(
    user_id=st.integers(min_value=1),
    product_id=st.integers(min_value=1),
    quantity=st.integers(min_value=1, max_value=100)
)