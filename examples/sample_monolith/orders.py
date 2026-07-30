"""
Sample Monolith — Orders Module
=================================
Order creation, tracking, and fulfillment.
Depends on both Users and Payments modules (tight coupling).
"""

import logging
from datetime import datetime

from database import query, execute
from models import Order, OrderItem, Product

# ANTI-PATTERN: Importing directly from sibling modules
from users import get_user, check_permission, _log_action
from payments import process_payment, get_payment_status

logger = logging.getLogger("monolith.orders")

# ANTI-PATTERN: Global configuration as module-level constants
MAX_ORDER_ITEMS = 50
MIN_ORDER_AMOUNT = 1.00
ORDER_STATUSES = ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled"]


# ──────────────────────────────────────────────
# Order Creation
# ──────────────────────────────────────────────

def create_order(user_id, items, shipping_address=None):
    """Create a new order with items.

    ANTI-PATTERN: This function does too much — validation, creation,
    payment processing, and stock updates all in one function.
    High cyclomatic complexity.

    Args:
        user_id: The user placing the order
        items: List of dicts with product_id and quantity
        shipping_address: Delivery address

    Returns:
        Order dict on success

    Raises:
        ValueError: On validation failures
    """
    # --- Validate user exists ---
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    if not user.get("is_active"):
        raise ValueError(f"User {user_id} is deactivated")

    # --- Validate items ---
    if not items:
        raise ValueError("Order must contain at least one item")

    if len(items) > MAX_ORDER_ITEMS:
        raise ValueError(f"Order cannot exceed {MAX_ORDER_ITEMS} items")

    # --- Validate products and calculate totals ---
    total_amount = 0.0
    validated_items = []

    for item in items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)

        if quantity <= 0:
            raise ValueError(f"Invalid quantity for product {product_id}")

        # ANTI-PATTERN: N+1 query pattern — one query per item
        product_rows = query("SELECT * FROM products WHERE id = ?", (product_id,))
        if not product_rows:
            raise ValueError(f"Product {product_id} not found")

        product = Product.from_row(product_rows[0])

        if product.stock_quantity < quantity:
            raise ValueError(
                f"Insufficient stock for {product.name}: "
                f"requested {quantity}, available {product.stock_quantity}"
            )

        subtotal = product.price * quantity
        total_amount += subtotal
        validated_items.append({
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": product.price,
        })

    if total_amount < MIN_ORDER_AMOUNT:
        raise ValueError(f"Order total must be at least ${MIN_ORDER_AMOUNT}")

    # --- Create order ---
    order_id = execute(
        "INSERT INTO orders (user_id, total_amount, shipping_address, status) VALUES (?, ?, ?, ?)",
        (user_id, round(total_amount, 2), shipping_address, "pending")
    )

    # --- Insert order items and update stock ---
    for item in validated_items:
        execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
            (order_id, item["product_id"], item["quantity"], item["unit_price"])
        )

        # ANTI-PATTERN: Stock update inside order creation — should be separate service
        execute(
            "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
            (item["quantity"], item["product_id"])
        )

    # --- Auto-process payment ---
    # ANTI-PATTERN: Calling payments module directly — tight coupling
    try:
        payment_result = process_payment(
            order_id=order_id,
            user_id=user_id,
            amount=total_amount,
            method="credit_card"
        )
        if payment_result.get("status") == "completed":
            execute(
                "UPDATE orders SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (order_id,)
            )
    except Exception as e:
        logger.error(f"Payment failed for order {order_id}: {e}")
        execute(
            "UPDATE orders SET status = 'payment_failed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (order_id,)
        )

    _log_action(user_id, "ORDER_CREATED", f"Order #{order_id}, total: ${total_amount:.2f}")
    logger.info(f"Order created: #{order_id} for user {user_id}")

    return get_order(order_id)


# ──────────────────────────────────────────────
# Order Retrieval
# ──────────────────────────────────────────────

def get_order(order_id):
    """Get a single order with its items."""
    order_rows = query("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not order_rows:
        return None

    order = Order.from_row(order_rows[0])

    # Fetch order items
    item_rows = query(
        """SELECT oi.*, p.name as product_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?""",
        (order_id,)
    )

    items = []
    for row in item_rows:
        items.append({
            "product_id": row["product_id"],
            "product_name": row["product_name"],
            "quantity": row["quantity"],
            "unit_price": row["unit_price"],
            "subtotal": row["quantity"] * row["unit_price"],
        })

    result = order.to_dict()
    result["items"] = items
    return result


def get_user_orders(user_id, status=None, page=1, per_page=10):
    """Get all orders for a user with optional filtering.

    ANTI-PATTERN: Payment status lookup inside order retrieval
    creates cross-domain coupling.
    """
    base_query = "SELECT * FROM orders WHERE user_id = ?"
    params = [user_id]

    if status:
        base_query += " AND status = ?"
        params.append(status)

    base_query += f" ORDER BY created_at DESC LIMIT {per_page} OFFSET {(page - 1) * per_page}"

    order_rows = query(base_query, params)

    orders = []
    for row in order_rows:
        order = get_order(row["id"])
        # ANTI-PATTERN: Calling payments module for each order — N+1 cross-module calls
        payment_status = get_payment_status(row["id"])
        order["payment_status"] = payment_status
        orders.append(order)

    return {
        "orders": orders,
        "page": page,
        "per_page": per_page,
    }


# ──────────────────────────────────────────────
# Order Status Management
# ──────────────────────────────────────────────

def update_order_status(order_id, new_status, user_id=None):
    """Update order status with validation.

    ANTI-PATTERN: Complex status transition logic embedded in module
    instead of a state machine pattern.
    """
    if new_status not in ORDER_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    order_rows = query("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not order_rows:
        raise ValueError(f"Order {order_id} not found")

    current_status = order_rows[0]["status"]

    # Status transition validation
    valid_transitions = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["processing", "cancelled"],
        "processing": ["shipped", "cancelled"],
        "shipped": ["delivered"],
        "delivered": [],
        "cancelled": [],
        "payment_failed": ["pending", "cancelled"],
    }

    allowed = valid_transitions.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{current_status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )

    execute(
        "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, order_id)
    )

    # If cancelling, restore stock
    if new_status == "cancelled":
        _restore_order_stock(order_id)

    if user_id:
        _log_action(user_id, "ORDER_STATUS_CHANGED",
                     f"Order #{order_id}: {current_status} -> {new_status}")

    return get_order(order_id)


def cancel_order(order_id, user_id, reason=None):
    """Cancel an order and initiate refund.

    ANTI-PATTERN: Order cancellation triggers payment refund directly.
    """
    order = get_order(order_id)
    if not order:
        raise ValueError(f"Order {order_id} not found")

    # Check permission — only order owner or admin
    if order["user_id"] != user_id:
        if not check_permission(user_id, "admin"):
            raise PermissionError("Not authorized to cancel this order")

    result = update_order_status(order_id, "cancelled", user_id)

    # ANTI-PATTERN: Importing and calling payments directly
    from payments import process_refund
    try:
        refund = process_refund(order_id, reason=reason or "Order cancelled by user")
        result["refund"] = refund
    except Exception as e:
        logger.error(f"Refund failed for order {order_id}: {e}")
        result["refund_error"] = str(e)

    return result


def _restore_order_stock(order_id):
    """Restore stock quantities when an order is cancelled."""
    item_rows = query("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    for row in item_rows:
        execute(
            "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?",
            (row["quantity"], row["product_id"])
        )


# ──────────────────────────────────────────────
# Order Analytics (ANTI-PATTERN: business logic in data layer)
# ──────────────────────────────────────────────

def get_order_stats(user_id=None):
    """Get order statistics.

    ANTI-PATTERN: Raw SQL analytics that should be in a reporting service.
    """
    if user_id:
        rows = query(
            """SELECT
                COUNT(*) as total_orders,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COALESCE(AVG(total_amount), 0) as avg_order_value,
                COUNT(CASE WHEN status = 'delivered' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders
            FROM orders WHERE user_id = ?""",
            (user_id,)
        )
    else:
        rows = query(
            """SELECT
                COUNT(*) as total_orders,
                COALESCE(SUM(total_amount), 0) as total_revenue,
                COALESCE(AVG(total_amount), 0) as avg_order_value,
                COUNT(CASE WHEN status = 'delivered' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders
            FROM orders"""
        )

    if not rows:
        return {}

    row = rows[0]
    return {
        "total_orders": row["total_orders"],
        "total_revenue": round(row["total_revenue"], 2),
        "avg_order_value": round(row["avg_order_value"], 2),
        "completed_orders": row["completed_orders"],
        "cancelled_orders": row["cancelled_orders"],
    }
