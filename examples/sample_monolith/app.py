"""
Sample Monolith — Flask Application Entry Point
=================================================
A monolithic Flask application combining Users, Orders, and Payments.
This is the test fixture for the Architecture Migration Assistant.

~450 LOC across all modules. Deliberate anti-patterns:
- Global database connection
- Circular dependencies (users ↔ payments)
- Tight coupling (orders → users, orders → payments)
- N+1 queries
- Mixed responsibilities (God functions)
- Duplicated audit logging
- Custom crypto (should use bcrypt)
- Global session state
- SQL string formatting
"""

from flask import Flask, request, jsonify
import logging

# ANTI-PATTERN: All modules imported at top level — circular dependency risk
from database import get_connection, close as close_db
from users import (
    authenticate, create_user, get_user, list_users,
    update_user, delete_user, get_profile, update_profile,
    get_user_payment_summary, logout, validate_session
)
from orders import (
    create_order, get_order, get_user_orders,
    update_order_status, cancel_order, get_order_stats
)
from payments import (
    process_payment, get_payment, get_user_payments,
    process_refund, get_payment_stats
)

# ──────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-key-change-in-production"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("monolith.app")

# Initialize database on startup
get_connection()


# ──────────────────────────────────────────────
# Auth Routes
# ──────────────────────────────────────────────

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Email and password required"}), 400

    result = authenticate(data["email"], data["password"])
    if not result:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify(result), 200


@app.route("/api/auth/logout", methods=["POST"])
def do_logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if logout(token):
        return jsonify({"message": "Logged out"}), 200
    return jsonify({"error": "Invalid token"}), 401


# ──────────────────────────────────────────────
# User Routes
# ──────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
def api_list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return jsonify(list_users(page, per_page)), 200


@app.route("/api/users", methods=["POST"])
def api_create_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["email", "name", "password"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        user = create_user(data["email"], data["name"], data["password"],
                           data.get("role", "user"))
        return jsonify(user), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/users/<int:user_id>", methods=["GET"])
def api_get_user(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200


@app.route("/api/users/<int:user_id>", methods=["PUT"])
def api_update_user(user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    try:
        user = update_user(user_id, **data)
        return jsonify(user), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    delete_user(user_id)
    return jsonify({"message": "User deactivated"}), 200


@app.route("/api/users/<int:user_id>/profile", methods=["GET"])
def api_get_profile(user_id):
    profile = get_profile(user_id)
    if not profile:
        return jsonify({"error": "User not found"}), 404
    return jsonify(profile), 200


@app.route("/api/users/<int:user_id>/profile", methods=["PUT"])
def api_update_profile(user_id):
    data = request.get_json()
    profile = update_profile(user_id, **data)
    return jsonify(profile), 200


@app.route("/api/users/<int:user_id>/payment-summary", methods=["GET"])
def api_user_payment_summary(user_id):
    summary = get_user_payment_summary(user_id)
    return jsonify(summary), 200


# ──────────────────────────────────────────────
# Order Routes
# ──────────────────────────────────────────────

@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data = request.get_json()
    if not data or "user_id" not in data or "items" not in data:
        return jsonify({"error": "user_id and items required"}), 400

    try:
        order = create_order(
            data["user_id"], data["items"],
            data.get("shipping_address")
        )
        return jsonify(order), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/orders/<int:order_id>", methods=["GET"])
def api_get_order(order_id):
    order = get_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order), 200


@app.route("/api/users/<int:user_id>/orders", methods=["GET"])
def api_get_user_orders(user_id):
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    orders = get_user_orders(user_id, status=status, page=page)
    return jsonify(orders), 200


@app.route("/api/orders/<int:order_id>/status", methods=["PUT"])
def api_update_order_status(order_id):
    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"error": "status required"}), 400
    try:
        order = update_order_status(order_id, data["status"], data.get("user_id"))
        return jsonify(order), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
def api_cancel_order(order_id):
    data = request.get_json() or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    try:
        result = cancel_order(order_id, user_id, data.get("reason"))
        return jsonify(result), 200
    except (ValueError, PermissionError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/orders/stats", methods=["GET"])
def api_order_stats():
    user_id = request.args.get("user_id", type=int)
    stats = get_order_stats(user_id)
    return jsonify(stats), 200


# ──────────────────────────────────────────────
# Payment Routes
# ──────────────────────────────────────────────

@app.route("/api/payments/<int:payment_id>", methods=["GET"])
def api_get_payment(payment_id):
    payment = get_payment(payment_id)
    if not payment:
        return jsonify({"error": "Payment not found"}), 404
    return jsonify(payment), 200


@app.route("/api/users/<int:user_id>/payments", methods=["GET"])
def api_get_user_payments(user_id):
    page = request.args.get("page", 1, type=int)
    payments = get_user_payments(user_id, page=page)
    return jsonify(payments), 200


@app.route("/api/payments/stats", methods=["GET"])
def api_payment_stats():
    stats = get_payment_stats()
    return jsonify(stats), 200


@app.route("/api/orders/<int:order_id>/refund", methods=["POST"])
def api_refund_order(order_id):
    data = request.get_json() or {}
    try:
        result = process_refund(order_id, data.get("reason"))
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "monolith",
        "version": "1.0.0",
    }), 200


if __name__ == "__main__":
    try:
        app.run(debug=True, port=5000)
    finally:
        close_db()
