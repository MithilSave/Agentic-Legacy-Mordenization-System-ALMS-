
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


def test_create_user_happy_path(client: TestClient, db_session: Session):
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "password": "securepassword"
    }
    response = client.post("/users/", json=user_data)
    assert response.status_code == 201
    created_user = response.json()
    assert created_user["email"] == user_data["email"]
    assert created_user["name"] == user_data["name"]
    assert "id" in created_user
    assert "created_at" in created_user
    assert "updated_at" in created_user

