"""
Sample Monolith — Users Module
================================
User authentication, profile management, and authorization.
Contains deliberate coupling to payments module (circular dependency).
"""

import hashlib
import secrets
import logging
from datetime import datetime

from database import query, execute, get_connection
from models import User, UserProfile

# ANTI-PATTERN: Module-level logger with inconsistent configuration
logger = logging.getLogger("monolith.users")

# ANTI-PATTERN: Global state for session tokens
_active_sessions = {}


# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────

def hash_password(password):
    """Hash a password with salt using SHA-256.

    ANTI-PATTERN: Rolling own crypto instead of using bcrypt/argon2.
    """
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password, hashed_password):
    """Verify a password against its hash."""
    try:
        salt, stored_hash = hashed_password.split(":")
        computed_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return computed_hash == stored_hash
    except (ValueError, AttributeError):
        return False


def authenticate(email, password):
    """Authenticate a user by email and password.

    Returns user object on success, None on failure.
    """
    rows = query("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,))
    if not rows:
        logger.warning(f"Authentication failed: user not found for {email}")
        return None

    user = User.from_row(rows[0])
    if user and verify_password(password, user.hashed_password):
        # Create session token
        token = secrets.token_urlsafe(32)
        _active_sessions[token] = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "created_at": datetime.now().isoformat()
        }
        _log_action(user.id, "LOGIN", f"User {email} logged in")
        logger.info(f"User authenticated: {email}")
        return {"user": user.to_dict(), "token": token}

    logger.warning(f"Authentication failed: bad password for {email}")
    return None


def validate_session(token):
    """Check if a session token is valid."""
    return _active_sessions.get(token)


def logout(token):
    """Invalidate a session token."""
    session = _active_sessions.pop(token, None)
    if session:
        _log_action(session["user_id"], "LOGOUT", "User logged out")
    return session is not None


# ──────────────────────────────────────────────
# User CRUD
# ──────────────────────────────────────────────

def create_user(email, name, password, role="user"):
    """Register a new user.

    ANTI-PATTERN: No input validation at this layer.
    """
    # Check for existing user
    existing = query("SELECT id FROM users WHERE email = ?", (email,))
    if existing:
        raise ValueError(f"User with email {email} already exists")

    hashed = hash_password(password)
    user_id = execute(
        "INSERT INTO users (email, name, hashed_password, role) VALUES (?, ?, ?, ?)",
        (email, name, hashed, role)
    )

    # ANTI-PATTERN: Creating profile inside user creation — mixed responsibilities
    execute(
        "INSERT INTO user_profiles (user_id) VALUES (?)",
        (user_id,)
    )

    _log_action(user_id, "USER_CREATED", f"New user: {email}")
    logger.info(f"User created: {email} (id={user_id})")

    return get_user(user_id)


def get_user(user_id):
    """Get a user by ID."""
    rows = query("SELECT * FROM users WHERE id = ?", (user_id,))
    if not rows:
        return None
    return User.from_row(rows[0]).to_dict()


def get_user_by_email(email):
    """Get a user by email address."""
    rows = query("SELECT * FROM users WHERE email = ?", (email,))
    if not rows:
        return None
    return User.from_row(rows[0]).to_dict()


def list_users(page=1, per_page=20):
    """List all users with pagination.

    ANTI-PATTERN: SQL string concatenation (injection risk in more complex cases).
    """
    offset = (page - 1) * per_page
    rows = query(
        f"SELECT * FROM users ORDER BY created_at DESC LIMIT {per_page} OFFSET {offset}"
    )
    total_rows = query("SELECT COUNT(*) as count FROM users")
    total = total_rows[0]["count"] if total_rows else 0

    return {
        "users": [User.from_row(r).to_dict() for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def update_user(user_id, **kwargs):
    """Update user fields.

    ANTI-PATTERN: Accepts arbitrary kwargs without validation.
    """
    allowed_fields = {"name", "email", "role", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return get_user(user_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [user_id]

    execute(
        f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values
    )

    _log_action(user_id, "USER_UPDATED", f"Updated fields: {list(updates.keys())}")
    return get_user(user_id)


def delete_user(user_id):
    """Soft-delete a user by deactivating them."""
    execute("UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,))
    _log_action(user_id, "USER_DELETED", "User deactivated")
    return True


def change_password(user_id, old_password, new_password):
    """Change a user's password."""
    rows = query("SELECT * FROM users WHERE id = ?", (user_id,))
    if not rows:
        raise ValueError("User not found")

    user = User.from_row(rows[0])
    if not verify_password(old_password, user.hashed_password):
        raise ValueError("Current password is incorrect")

    new_hashed = hash_password(new_password)
    execute(
        "UPDATE users SET hashed_password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_hashed, user_id)
    )

    _log_action(user_id, "PASSWORD_CHANGED", "Password updated")
    return True


# ──────────────────────────────────────────────
# Profile Management
# ──────────────────────────────────────────────

def get_profile(user_id):
    """Get user profile with user data."""
    user = get_user(user_id)
    if not user:
        return None

    profile_rows = query("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    profile = None
    if profile_rows:
        profile = UserProfile(
            id=profile_rows[0]["id"], user_id=user_id,
            bio=profile_rows[0]["bio"], avatar_url=profile_rows[0]["avatar_url"],
            phone=profile_rows[0]["phone"], address=profile_rows[0]["address"]
        ).to_dict()

    return {"user": user, "profile": profile}


def update_profile(user_id, **kwargs):
    """Update user profile fields."""
    allowed_fields = {"bio", "avatar_url", "phone", "address"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return get_profile(user_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [user_id]

    execute(f"UPDATE user_profiles SET {set_clause} WHERE user_id = ?", values)

    _log_action(user_id, "PROFILE_UPDATED", f"Updated: {list(updates.keys())}")
    return get_profile(user_id)


# ──────────────────────────────────────────────
# ANTI-PATTERN: Cross-module function for payment history
# This creates a CIRCULAR DEPENDENCY: users → payments → users
# ──────────────────────────────────────────────

def get_user_payment_summary(user_id):
    """Get payment summary for a user.

    ANTI-PATTERN: Users module directly queries payments table,
    creating tight coupling between user and payment domains.
    """
    rows = query(
        """SELECT
            COUNT(*) as total_payments,
            COALESCE(SUM(amount), 0) as total_spent,
            COALESCE(AVG(amount), 0) as avg_payment
        FROM payments WHERE user_id = ? AND status = 'completed'""",
        (user_id,)
    )

    if not rows:
        return {"total_payments": 0, "total_spent": 0, "avg_payment": 0}

    return {
        "total_payments": rows[0]["total_payments"],
        "total_spent": round(rows[0]["total_spent"], 2),
        "avg_payment": round(rows[0]["avg_payment"], 2),
    }


# ──────────────────────────────────────────────
# Authorization
# ──────────────────────────────────────────────

def check_permission(user_id, required_role="user"):
    """Check if user has the required role."""
    user = get_user(user_id)
    if not user:
        return False

    role_hierarchy = {"admin": 3, "manager": 2, "user": 1}
    user_level = role_hierarchy.get(user.get("role", "user"), 0)
    required_level = role_hierarchy.get(required_role, 0)

    return user_level >= required_level


# ──────────────────────────────────────────────
# Audit Logging (ANTI-PATTERN: duplicated across modules)
# ──────────────────────────────────────────────

def _log_action(user_id, action, details):
    """Log an action to the audit table."""
    try:
        execute(
            "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details)
        )
    except Exception as e:
        logger.error(f"Failed to log action: {e}")
