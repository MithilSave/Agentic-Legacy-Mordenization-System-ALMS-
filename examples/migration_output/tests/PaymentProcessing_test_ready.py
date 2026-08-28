
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


def test_ready(client, db_session):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
