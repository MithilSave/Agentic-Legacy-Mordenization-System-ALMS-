
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

def test_logout(email):
    user_data = UserCreate(email=email, name="Test User", password="testpassword")
    _create_user(test_db, user_data)
    token_response = client.post("/api/token", data={"username": email, "password": "testpassword"})
    assert token_response.status_code == 200
    token = token_response.json().get("access_token")
    response = client.delete(f"/api/users/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204


# Property-Based Test using Hypothesis
import hypothesis
from hypothesis import given, strategies as st

@given(email=st.emails(), name=st.text(), password=st.text())