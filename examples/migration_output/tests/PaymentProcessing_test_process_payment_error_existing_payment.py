
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


def test_process_payment_error_existing_payment(client, db_session):
    existing_payment = PaymentORM(order_id=1, user_id=1, amount=100.0, method="credit_card", status="completed")
    db_session.add(existing_payment)
    db_session.commit()

    payment_data = {
        "order_id": 1,
        "user_id": 1,
        "amount": 200.0,
        "method": "credit_card"
    }
    response = client.post("/payments", json=payment_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Payment already exists for order"}

@given(amount=st.floats(min_value=0, max_value=1000))