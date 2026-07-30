
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

def test_create_user_hypothesis(email, name, password):
    user_data = UserCreate(email=email, name=name, password=password)
    response = client.post("/api/users/", json=user_data.dict())
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == email


# Shadow Test Comparing Legacy vs New Output