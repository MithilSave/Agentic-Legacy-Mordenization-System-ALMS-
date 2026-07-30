"""
Sample Monolith — Payments Module
===================================
Payment processing, refunds, and transaction management.
ANTI-PATTERN: Queries users table directly — creates circular dependency
with the users module (users → payments → users).
"""

import logging
import uuid
import random
from datetime import datetime

from database import query, execute
from models import Payment, Refund

logger = logging.getLogger("monolith.payments")

# ANTI-PATTERN: Simulated external service configuration as globals
PAYMENT_GATEWAY_API_KEY = "sk_test_fake_key_12345"
PAYMENT_GATEWAY_URL = "https://api.stripe.com/v1"
SUPPORTED_METHODS = ["credit_card", "debit_card", "bank_transfer", "wallet"]


# ──────────────────────────────────────────────
# Payment Processing
# ──────────────────────────────────────────────

def process_payment(order_id, user_id, amount, method="credit_card"):
    """Process a payment for an order.

    ANTI-PATTERN: This function queries the users table directly
    instead of calling the users module, creating a hidden dependency.
    Also mixes payment processing with user validation.
    """
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"Unsupported payment method: {method}")

    if amount <= 0:
        raise ValueError("Payment amount must be positive")

    # ANTI-PATTERN: Direct query to users table — cross-domain data access
    user_rows = query("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))
    if not user_rows:
        raise ValueError(f"User {user_id} not found or inactive")

    # Check for duplicate payments
    existing = query(
        "SELECT id FROM payments WHERE order_id = ? AND status IN ('completed', 'pending')",
        (order_id,)
    )
    if existing:
        raise ValueError(f"Payment already exists for order {order_id}")

    # --- Simulate payment gateway call ---
    transaction_id = _call_payment_gateway(
        amount=amount,
        method=method,
        user_email=user_rows[0]["email"],  # ANTI-PATTERN: using user data from direct query
        user_name=user_rows[0]["name"]
    )

    # Record payment
    status = "completed" if transaction_id else "failed"
    payment_id = execute(
        """INSERT INTO payments (order_id, user_id, amount, method, status, transaction_id)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (order_id, user_id, round(amount, 2), method, status, transaction_id)
    )

    _log_payment_action(user_id, "PAYMENT_PROCESSED",
                        f"Order #{order_id}, amount: ${amount:.2f}, status: {status}")

    logger.info(f"Payment {status}: order={order_id}, amount=${amount:.2f}, txn={transaction_id}")

    return {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": round(amount, 2),
        "status": status,
        "transaction_id": transaction_id,
        "method": method,
    }


def _call_payment_gateway(amount, method, user_email, user_name):
    """Simulate calling an external payment gateway.

    In production, this would call Stripe/PayPal API.
    For the demo monolith, we simulate success/failure.
    """
    # Simulate ~95% success rate
    if random.random() < 0.95:
        transaction_id = f"txn_{uuid.uuid4().hex[:16]}"
        logger.info(f"Gateway approved: {transaction_id} for {user_email}")
        return transaction_id
    else:
        logger.warning(f"Gateway declined payment for {user_email}")
        return None


# ──────────────────────────────────────────────
# Payment Queries
# ──────────────────────────────────────────────

def get_payment(payment_id):
    """Get a payment by ID."""
    rows = query("SELECT * FROM payments WHERE id = ?", (payment_id,))
    if not rows:
        return None

    row = rows[0]
    return {
        "id": row["id"],
        "order_id": row["order_id"],
        "user_id": row["user_id"],
        "amount": row["amount"],
        "method": row["method"],
        "status": row["status"],
        "transaction_id": row["transaction_id"],
        "created_at": row["created_at"],
    }


def get_payment_status(order_id):
    """Get payment status for an order.

    ANTI-PATTERN: Returns string status instead of structured data.
    """
    rows = query(
        "SELECT status, transaction_id FROM payments WHERE order_id = ? ORDER BY created_at DESC LIMIT 1",
        (order_id,)
    )
    if not rows:
        return "no_payment"
    return rows[0]["status"]


def get_user_payments(user_id, page=1, per_page=10):
    """Get payment history for a user.

    ANTI-PATTERN: Joins with orders table — cross-domain query.
    """
    offset = (page - 1) * per_page
    rows = query(
        """SELECT p.*, o.status as order_status, o.total_amount as order_total
        FROM payments p
        JOIN orders o ON p.order_id = o.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?""",
        (user_id, per_page, offset)
    )

    payments = []
    for row in rows:
        payments.append({
            "id": row["id"],
            "order_id": row["order_id"],
            "amount": row["amount"],
            "method": row["method"],
            "status": row["status"],
            "transaction_id": row["transaction_id"],
            "order_status": row["order_status"],
            "order_total": row["order_total"],
            "created_at": row["created_at"],
        })

    return {"payments": payments, "page": page, "per_page": per_page}


# ──────────────────────────────────────────────
# Refund Processing
# ──────────────────────────────────────────────

def process_refund(order_id, reason=None):
    """Process a refund for an order.

    ANTI-PATTERN: Complex refund logic with multiple cross-domain queries
    and mixed responsibilities.
    """
    # Find the payment for this order
    payment_rows = query(
        "SELECT * FROM payments WHERE order_id = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
        (order_id,)
    )

    if not payment_rows:
        raise ValueError(f"No completed payment found for order {order_id}")

    payment = payment_rows[0]
    refund_amount = payment["amount"]

    # Check if already refunded
    existing_refund = query(
        "SELECT id FROM refunds WHERE payment_id = ? AND status IN ('completed', 'pending')",
        (payment["id"],)
    )
    if existing_refund:
        raise ValueError(f"Refund already processed for payment {payment['id']}")

    # ANTI-PATTERN: Simulate gateway refund
    refund_txn = _call_refund_gateway(
        transaction_id=payment["transaction_id"],
        amount=refund_amount
    )

    refund_status = "completed" if refund_txn else "failed"

    # Record refund
    refund_id = execute(
        "INSERT INTO refunds (payment_id, amount, reason, status) VALUES (?, ?, ?, ?)",
        (payment["id"], refund_amount, reason, refund_status)
    )

    # Update payment status
    if refund_status == "completed":
        execute(
            "UPDATE payments SET status = 'refunded' WHERE id = ?",
            (payment["id"],)
        )

    _log_payment_action(
        payment["user_id"], "REFUND_PROCESSED",
        f"Order #{order_id}, amount: ${refund_amount:.2f}, status: {refund_status}"
    )

    return {
        "refund_id": refund_id,
        "payment_id": payment["id"],
        "order_id": order_id,
        "amount": refund_amount,
        "reason": reason,
        "status": refund_status,
    }


def _call_refund_gateway(transaction_id, amount):
    """Simulate refund via payment gateway."""
    if random.random() < 0.98:
        refund_id = f"ref_{uuid.uuid4().hex[:16]}"
        logger.info(f"Refund approved: {refund_id} for txn {transaction_id}")
        return refund_id
    else:
        logger.warning(f"Refund declined for txn {transaction_id}")
        return None


# ──────────────────────────────────────────────
# Payment Analytics
# ──────────────────────────────────────────────

def get_payment_stats():
    """Get global payment statistics.

    ANTI-PATTERN: Analytics query that joins across multiple domains.
    """
    rows = query("""
        SELECT
            COUNT(*) as total_transactions,
            COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as total_collected,
            COALESCE(SUM(CASE WHEN status = 'refunded' THEN amount ELSE 0 END), 0) as total_refunded,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
            COUNT(CASE WHEN status = 'refunded' THEN 1 END) as refunded
        FROM payments
    """)

    if not rows:
        return {}

    row = rows[0]
    return {
        "total_transactions": row["total_transactions"],
        "total_collected": round(row["total_collected"], 2),
        "total_refunded": round(row["total_refunded"], 2),
        "net_revenue": round(row["total_collected"] - row["total_refunded"], 2),
        "success_rate": round(row["successful"] / max(row["total_transactions"], 1) * 100, 1),
    }


# ──────────────────────────────────────────────
# Audit Logging (ANTI-PATTERN: duplicated from users module)
# ──────────────────────────────────────────────

def _log_payment_action(user_id, action, details):
    """Log a payment action. Duplicated logging pattern from users module."""
    try:
        execute(
            "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details)
        )
    except Exception as e:
        logger.error(f"Failed to log payment action: {e}")
