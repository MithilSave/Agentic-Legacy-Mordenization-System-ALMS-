
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

def test_update_user(email):
    user_data = UserCreate(email=email, name="Test User", password="testpassword")
    client.post("/api/users/", json=user_data.dict())
    updated_name = "Updated Test User"
    response = client.put(f"/api/users/{user_data.email}", json={"name": updated_name})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == updated_name


@pytest.mark.parametrize("email", ["user@example.com"])