
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


def test_create_order_happy_path(product, db_session):
    order_data = {
        "user_id": 1,
        "items": [{"product_id": product.id, "quantity": 5}],
        "shipping_address": "Test Address"
    }
    response = client.post("/orders/", json=order_data)
    assert response.status_code == 200
    order_response = response.json()
    assert order_response["user_id"] == 1
    assert len(order_response["items"]) == 1
    assert order_response["total_amount"] == 50.0

