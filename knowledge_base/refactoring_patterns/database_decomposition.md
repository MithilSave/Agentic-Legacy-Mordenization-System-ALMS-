# Database Decomposition Pattern

## Problem
Monolithic databases have shared tables across domains, creating tight coupling between services.

## Solution: Database-per-Service
Each microservice owns its database schema. Cross-service data access happens through APIs, not direct table queries.

## Transformation Steps
1. Identify table ownership by analyzing which module primarily writes to each table
2. Replace foreign keys across service boundaries with API references
3. Use eventual consistency for cross-service data synchronization
4. Implement the Saga pattern for distributed transactions

## Example
```python
# BEFORE: Orders module directly queries users table
user = db.query("SELECT * FROM users WHERE id = ?", (user_id,))

# AFTER: Orders service calls User service API
user = await user_service_client.get_user(user_id)
```
