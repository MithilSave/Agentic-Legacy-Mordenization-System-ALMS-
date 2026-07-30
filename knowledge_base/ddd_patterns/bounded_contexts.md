# Identifying Bounded Contexts

## Problem
Monolithic applications mix domain concepts across modules, making it difficult to identify service boundaries.

## DDD Approach
1. **Identify Core Domains**: What are the distinct business areas? (Users, Orders, Payments, Inventory)
2. **Map Domain Language**: Each domain uses specific terminology
3. **Find Aggregate Roots**: The primary entity that other entities cluster around
4. **Define Boundaries**: Where one domain's responsibility ends and another begins

## Signals for Service Boundaries
- Tables that are primarily read by one module and written by another → different services
- Functions with high internal cohesion (call each other frequently) → same service
- Circular dependencies between modules → consider merging or extracting shared concepts
- External API dependencies → isolate behind a service facade

## Example: E-commerce Bounded Contexts
```
User Management (Bounded Context)
├── Entities: User, UserProfile, Role
├── Aggregate Root: User
├── Events: UserCreated, UserUpdated
└── API: /api/users, /api/auth

Order Processing (Bounded Context)
├── Entities: Order, OrderItem, OrderStatus
├── Aggregate Root: Order
├── Events: OrderCreated, OrderPaid, OrderShipped
└── API: /api/orders, /api/cart

Payment Processing (Bounded Context)
├── Entities: Payment, Transaction, Refund
├── Aggregate Root: Payment
├── Events: PaymentCompleted, RefundIssued
└── API: /api/payments
```

## Metrics for Good Boundaries
- High cohesion within context: 80%+ internal calls
- Low coupling between contexts: <15% external calls
- Clear API contracts between services
