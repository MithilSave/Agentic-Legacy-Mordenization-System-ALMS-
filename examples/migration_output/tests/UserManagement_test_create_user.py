
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

def test_create_user(email):
    user_data = UserCreate(email=email, name="Test User", password="testpassword")
    response = client.post("/api/users/", json=user_data.dict())
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == email


@pytest.mark.parametrize("email", ["user@example.com"])