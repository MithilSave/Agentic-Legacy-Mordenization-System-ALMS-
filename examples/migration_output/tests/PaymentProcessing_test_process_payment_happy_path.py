
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

def test_process_payment_happy_path(client):
    response = client.post("/payments/", json={
        "order_id": "12345",
        "user_id": "user123",
        "amount": 10.99,
        "method": "credit_card"
    })
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "status" in data and data["status"] == "completed"
    assert "transaction_id" in data

