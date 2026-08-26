
import os
from datetime import datetime
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import create_app, get_db
from models import User, UserProfile
from schemas import UserCreate, UserUpdate
from utils import hash_password, verify_password, authenticate, logout

# Initialize the test client and database session

# Utility functions for testing



# Unit Tests for User Management Endpoints
@pytest.mark.parametrize("email", ["user@example.com"])

def test_shadow_test():
    # Setup legacy service (Flask app)
    from legacy_app import app as legacy_app

    with TestClient(legacy_app) as legacy_client:
        user_data = UserCreate(email="user@example.com", name="Test User", password="testpassword")
        response_new = client.post("/api/users/", json=user_data.dict())
        assert response_new.status_code == 201
        new_user_id = response_new.json()["id"]

        # Simulate legacy service call
        response_legacy = legacy_client.post("/api/users/", json=user_data.dict())
        assert response_legacy.status_code == 201

        # Compare the output
        new_user = test_db.query(User).filter_by(id=new_user_id).first()
        legacy_user = legacy_app.db.query(User).filter_by(email="user@example.com").first()

        assert new_user.email == legacy_user.email
        assert new_user.name == legacy_user.name


# Fixtures for setup/teardown
@pytest.fixture(scope="session")
def db_session():
    test_db = next(get_db())
    yield test_db
    test_db.close()


@pytest.fixture
def user_data(db_session):
    user_data = UserCreate(email="test@example.com", name="Test User", password="testpassword")
    _create_user(db_session, user_data)
    return user_data


# Ensure ≥85% code coverage
