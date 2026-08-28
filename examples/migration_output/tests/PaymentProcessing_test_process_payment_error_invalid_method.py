
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


def test_process_payment_error_invalid_method(client, db_session):
    payment_data = {
        "order_id": 1,
        "user_id": 1,
        "amount": 100.0,
        "method": "invalid_method"
    }
    response = client.post("/payments", json=payment_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported payment method"}
