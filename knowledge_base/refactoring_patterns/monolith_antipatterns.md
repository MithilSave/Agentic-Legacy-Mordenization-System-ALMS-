# Monolithic Anti-Patterns and Refactoring Strategies

## Common Anti-Patterns

### 1. Global State
Modules sharing global variables (database connections, session stores) create hidden dependencies. Refactor to dependency injection.

### 2. Circular Dependencies
Module A imports from Module B, which imports from Module A. Break cycles by extracting shared interfaces into a separate module.

### 3. God Functions
Functions with high cyclomatic complexity (>10) that handle validation, business logic, persistence, and notifications. Split into single-responsibility functions.

### 4. N+1 Query Pattern
Querying the database inside a loop instead of using joins or batch queries. Refactor to eager loading or dedicated batch endpoints.

### 5. Cross-Domain Data Access
Module directly querying tables owned by another domain (e.g., payments module reading users table). Replace with API calls between services.

### 6. Duplicated Logic
Same audit logging, error handling, or validation code copied across modules. Extract to shared utilities or middleware.

## Refactoring Strategy
1. Map all dependencies with AST analysis
2. Identify bounded contexts using DDD principles
3. Extract shared models to API contracts
4. Replace direct DB queries with service interfaces
5. Add dependency injection for all external resources
