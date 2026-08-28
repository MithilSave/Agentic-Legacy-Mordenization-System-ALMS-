
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


def test_process_payment_hypothesis(amount):
    payment = PaymentCreate(order_id=1, user_id=1, amount=amount, method="credit_card")
    with pytest.raises(HTTPException) as excinfo:
        process_payment(payment, db=None)
    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Unsupported payment method" in str(excinfo.value.detail)

# test_shadow.py
import json
from fastapi.testclient import TestClient
from main import app
