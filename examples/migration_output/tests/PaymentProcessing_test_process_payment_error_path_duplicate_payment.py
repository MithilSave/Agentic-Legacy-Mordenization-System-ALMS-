
# payment_processing_tests.py

import json
from unittest.mock import patch, Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm.session import Session
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID
from random import random
from hypothesis import given, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, rule

from app import process_payment, get_payment, PaymentRequest, PaymentResponse, _call_payment_gateway
from database import get_db


# Unit Tests for /payments/ endpoint

def test_process_payment_error_path_duplicate_payment(client):
    client.post("/payments/", json={
        "order_id": "12345",
        "user_id": "user123",
        "amount": 10.99,
        "method": "credit_card"
    })
    response = client.post("/payments/", json={
        "order_id": "12345",
        "user_id": "user123",
        "amount": 10.99,
        "method": "credit_card"
    })
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data and data["detail"] == "Payment already exists for order 12345"


# Property-Based Test using Hypothesis
@given(
    amount=st.floats(min_value=0.01, max_value=1000),
    method=st.sampled_from(["credit_card", "debit_card", "bank_transfer", "wallet"])
)
@initialize()