
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

def test_delete_user(email):
    user_data = UserCreate(email=email, name="Test User", password="testpassword")
    client.post("/api/users/", json=user_data.dict())
    response = client.delete(f"/api/users/{user_data.email}")
    assert response.status_code == 204


@pytest.mark.parametrize("email", ["user@example.com"])