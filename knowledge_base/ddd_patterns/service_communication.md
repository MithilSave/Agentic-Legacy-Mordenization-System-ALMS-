# Service Communication Patterns

## Synchronous (REST)
Use when: the caller needs an immediate response and can't proceed without it.
```
Order Service → User Service: GET /api/users/{id} (validate user exists before creating order)
```

## Asynchronous (Message Queue)
Use when: the operation can be deferred and eventual consistency is acceptable.
```
Order Service → Payment Service: PaymentRequested event (payment processing can be delayed)
Payment Service → Order Service: PaymentCompleted event (async webhook notification)
```

## Decision Matrix
| Criteria | Sync (REST) | Async (Events) |
|----------|------------|----------------|
| Latency requirement | Immediate | Tolerable delay |
| Failure handling | Retry/circuit breaker | Dead letter queue |
| Coupling | Higher | Lower |
| Data consistency | Strong | Eventual |
| Use when | Read operations, validation | Write operations, notifications |

## Anti-patterns
- Synchronous chains of >3 services (latency compounds)
- Async for operations that need immediate validation
- Mixing sync and async for the same operation flow
