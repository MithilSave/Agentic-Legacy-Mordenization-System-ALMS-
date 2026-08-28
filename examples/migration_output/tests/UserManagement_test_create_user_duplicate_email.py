
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


def test_create_user_duplicate_email(client: TestClient, db_session: Session):
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "password": "securepassword"
    }
    client.post("/users/", json=user_data)
    response = client.post("/users/", json=user_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

