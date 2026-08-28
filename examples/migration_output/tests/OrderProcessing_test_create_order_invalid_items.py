
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


def test_create_order_invalid_items(db_session):
    order_data = {
        "user_id": 1,
        "items": [{"product_id": 999, "quantity": 5}],
        "shipping_address": "Test Address"
    }
    response = client.post("/orders/", json=order_data)
    assert response.status_code == 404
    assert response.json() == {"detail": "Product 999 not found"}

