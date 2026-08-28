
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Generator
from hypothesis import given, strategies as st
import hashlib
import secrets

# Import necessary modules from the FastAPI app
from main import app, get_db, UserCreate, User, hash_password, verify_password, authenticate

# Setup test client and database session
@pytest.fixture(scope="module")


@pytest.fixture(scope="function", autouse=True)


# Unit Tests


def test_create_user_invalid_email(client: TestClient, db_session: Session):
    user_data = {
        "email": "invalid-email",
        "name": "Test User",
        "password": "securepassword"
    }
    response = client.post("/users/", json=user_data)
    assert response.status_code == 422
    assert "email" in response.json()["detail"][0]["loc"]

