
# conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app, get_db, engine, Base

@pytest.fixture(scope="session", autouse=True)

@pytest.fixture

@pytest.fixture



# test_main.py
import pytest
from fastapi import HTTPException, status
from hypothesis import given, strategies as st
from main import PaymentCreate, PaymentResponse, RefundCreate, process_payment


def test_shadow_process_payment(client):
    legacy_response = {
        "payment_id": 1,
        "order_id": 1,
        "amount": 100.0,
        "status": "completed",
        "transaction_id": "tx123456789",
        "method": "credit_card"
    }

    payment_data = {
        "order_id": 1,
        "user_id": 1,
        "amount": 100.0,
        "method": "credit_card"
    }
    response = client.post("/payments", json=payment_data)
    assert response.status_code == 200
    new_response = response.json()

    # Compare legacy and new responses
    for key in ["order_id", "amount", "status", "method"]:
        assert new_response[key] == legacy_response[key]

# test_fixtures.py
import pytest

@pytest.fixture
def payment_data():
    return {
        "order_id": 1,
        "user_id": 1,
        "amount": 100.0,
        "method": "credit_card"
    }

@pytest.fixture
def refund_data():
    return {
        "order_id": 1,
        "reason": "Product not as described"
    }
