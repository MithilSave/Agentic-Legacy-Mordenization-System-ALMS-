
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


def test_shadow_authenticate(client: TestClient, db_session: Session):
    # Create a user in the new service
    user_data = {
        "email": "shadow@example.com",
        "name": "Shadow User",
        "password": "securepassword"
    }
    client.post("/users/", json=user_data)

    # Simulate legacy authentication (assuming similar logic)
    hashed_password = hash_password(user_data["password"])
    user_orm = db_session.query(UserORM).filter_by(email=user_data["email"]).first()
    assert user_orm is not None
    assert verify_password(user_data["password"], user_orm.hashed_password)

    # Authenticate using the new service
    response = client.post("/auth/login", json={"email": user_data["email"], "password": user_data["password"]})
    assert response.status_code == 200
    auth_response = response.json()
    assert "user" in auth_response
    assert "token" in auth_response

    # Compare legacy and new authentication results
    assert auth_response["user"]["email"] == user_orm.email
    assert auth_response["user"]["name"] == user_orm.name
