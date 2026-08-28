
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


def test_process_payment_happy_path(client, db_session):
    payment_data = {
        "order_id": 1,
        "user_id": 1,
        "amount": 100.0,
        "method": "credit_card"
    }
    response = client.post("/payments", json=payment_data)
    assert response.status_code == 200
    payment_response = response.json()
    assert payment_response["order_id"] == payment_data["order_id"]
    assert payment_response["amount"] == payment_data["amount"]
    assert payment_response["status"] in ["completed", "failed"]
