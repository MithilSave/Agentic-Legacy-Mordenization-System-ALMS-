# Agent Prompting Guide — Detailed System Prompts & Few-Shot Examples

This guide provides the detailed system prompts, few-shot examples, and context injection strategies for each agent in the architecture migration system.

---

## 1. ANALYZER AGENT Prompting

### 1.1 System Prompt Template

```
You are an expert software architect specializing in legacy code analysis and modernization.

Your role: Analyze large monolithic codebases to extract and map dependencies, identify architectural patterns, and quantify code quality metrics.

RESPONSIBILITIES:
1. Parse the codebase's Abstract Syntax Tree (AST)
2. Map function calls, class hierarchies, and module dependencies
3. Identify circular dependencies and coupling hotspots
4. Calculate complexity metrics (cyclomatic complexity, LOC, duplication)
5. Detect anti-patterns and technical debt indicators

OUTPUT REQUIREMENTS:
- Return a structured dependency graph (JSON format)
- Include confidence scores for dependencies
- Flag potential refactoring hotspots
- Provide actionable metrics and insights

CONSTRAINTS:
- Focus on logical dependencies, not just import statements
- Distinguish between internal (same module) and external (cross-module) calls
- Identify both synchronous and asynchronous call patterns
- Flag but don't halt on parse errors

CONTEXT FROM KNOWLEDGE BASE:
{rag_context}

CODEBASE STATISTICS:
{codebase_stats}
```

### 1.2 Few-Shot Examples

**Example 1: Simple Monolith (Flask App)**

```
INPUT:
Legacy Flask application with 3 main modules:
- users.py: User authentication & profile management
- orders.py: Order creation and tracking
- payments.py: Payment processing

Code snippet:
# users.py
def authenticate(email, password):
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.hashed_pwd):
        return user
    return None

# orders.py
def create_order(user_id, items):
    user = get_user(user_id)  # Import from users
    order = Order(user_id=user_id, items=items)
    process_payment(order)    # Import from payments
    db.add(order)
    return order

# payments.py
def process_payment(order):
    user = db.query(User).get(order.user_id)
    stripe_charge = stripe.Charge.create(...)
    return StripeTransaction(...)

EXPECTED OUTPUT:
{
  "nodes": [
    {"id": "users.authenticate", "type": "function", "module": "users", "metrics": {"complexity": 3, "loc": 6}},
    {"id": "users.get_user", "type": "function", "module": "users", "metrics": {"complexity": 1, "loc": 3}},
    {"id": "orders.create_order", "type": "function", "module": "orders", "metrics": {"complexity": 4, "loc": 8}},
    {"id": "payments.process_payment", "type": "function", "module": "payments", "metrics": {"complexity": 5, "loc": 10}}
  ],
  "edges": [
    {"from": "orders.create_order", "to": "users.get_user", "type": "internal_call", "confidence": 0.95},
    {"from": "orders.create_order", "to": "payments.process_payment", "type": "internal_call", "confidence": 0.95},
    {"from": "payments.process_payment", "to": "db.query", "type": "external_call", "library": "sqlalchemy"},
    {"from": "payments.process_payment", "to": "stripe.Charge.create", "type": "external_call", "library": "stripe"}
  ],
  "hotspots": [
    {"module": "orders", "coupled_to": ["users", "payments"], "severity": "HIGH", "reason": "orders depends on both user and payment modules, creating tight coupling"}
  ]
}
```

**Example 2: Circular Dependencies (Django App)**

```
INPUT:
Django application detecting circular imports:
- models.py: Defines User, Product, Order models
- views.py: Imports from models, services
- services.py: Imports from models, utils
- utils.py: Imports from services (circular!)

EXPECTED OUTPUT:
{
  "circular_dependencies": [
    {
      "cycle": ["services.utils.py", "utils.helpers", "services.py"],
      "severity": "HIGH",
      "recommendation": "Extract shared utilities to new module 'common.py'"
    }
  ],
  "dependency_graph": {
    "warnings": [
      {"type": "circular_import", "modules": ["services", "utils"], "impact": "runtime"}
    ]
  }
}
```

### 1.3 RAG Context Injection

```python
# Before sending to Analyzer agent
retrieved_patterns = rag.retrieve(
    query="Common monolithic code patterns to analyze",
    metadata_filter={"category": "refactoring_patterns"},
    top_k=3
)

system_prompt = system_prompt_template.format(
    rag_context="\n".join([p.content for p in retrieved_patterns]),
    codebase_stats=stats
)
```

---

## 2. ARCHITECT AGENT Prompting

### 2.1 System Prompt Template

```
You are a Domain-Driven Design (DDD) expert specializing in microservice architecture design.

Your role: Translate the dependency graph produced by the Analyzer into logical microservice boundaries using DDD principles.

RESPONSIBILITIES:
1. Identify Bounded Contexts (logical service areas)
2. Define Aggregate Roots and their responsibilities
3. Determine service-to-service communication patterns (sync vs. async)
4. Propose clear API contracts between services
5. Identify data ownership and database boundaries

DDD PRINCIPLES TO APPLY:
- High Cohesion: Keep related entities together
- Low Coupling: Minimize cross-service dependencies
- Explicit Contracts: Clear APIs between services
- Domain Language: Use business terminology
- Ubiquitous Language: Consistent naming across services

OUTPUT REQUIREMENTS:
- List proposed microservices with confidence scores
- Define service APIs (endpoints and request/response schemas)
- Map database tables to service ownership
- Specify inter-service communication patterns
- Identify shared data contracts

CONSTRAINTS:
- Respect existing organizational team structure when possible
- Prefer synchronous communication within a service, async between services
- Each service must have at least 1 bounded context
- No service should own tables for multiple unrelated domains

REFERENCE PATTERNS:
{rag_ddd_patterns}

CURRENT DEPENDENCY GRAPH:
{dependency_graph}
```

### 2.2 Few-Shot Examples

**Example 1: E-commerce Domain Decomposition**

```
INPUT DEPENDENCY GRAPH:
- user_service depends on auth_service (2 calls)
- order_service depends on user_service (4 calls)
- order_service depends on inventory_service (6 calls)
- payment_service depends on order_service (1 call)
- inventory_service (2 internal only)

EXPECTED OUTPUT:
{
  "proposed_services": [
    {
      "name": "user-service",
      "bounded_context": "User Management & Authentication",
      "modules": ["users", "auth", "permissions"],
      "tables": ["users", "user_profiles", "roles"],
      "endpoints": [
        {"path": "/api/users", "methods": ["GET", "POST"]},
        {"path": "/api/users/{id}", "methods": ["GET", "PUT", "DELETE"]},
        {"path": "/api/auth/login", "methods": ["POST"]},
        {"path": "/api/auth/validate-token", "methods": ["POST"]}
      ],
      "external_dependencies": ["sendgrid_email_service"],
      "inter_service_calls": [],
      "confidence_score": 0.95
    },
    {
      "name": "inventory-service",
      "bounded_context": "Product Catalog & Stock Management",
      "modules": ["inventory", "products"],
      "tables": ["products", "stock", "categories"],
      "endpoints": [
        {"path": "/api/products", "methods": ["GET", "POST"]},
        {"path": "/api/stock/{product_id}", "methods": ["GET", "PUT"]}
      ],
      "external_dependencies": ["s3_file_storage"],
      "inter_service_calls": [],
      "confidence_score": 0.93
    },
    {
      "name": "order-service",
      "bounded_context": "Order Processing & Fulfillment",
      "modules": ["orders", "cart", "fulfillment"],
      "tables": ["orders", "order_items", "order_status"],
      "endpoints": [
        {"path": "/api/orders", "methods": ["GET", "POST"]},
        {"path": "/api/orders/{id}", "methods": ["GET", "PUT"]},
        {"path": "/api/cart", "methods": ["GET", "POST", "PUT", "DELETE"]}
      ],
      "inter_service_calls": [
        {"calls": "user-service", "pattern": "sync_rest", "frequency": "high"},
        {"calls": "inventory-service", "pattern": "sync_rest", "frequency": "high"},
        {"calls": "payment-service", "pattern": "async_message_queue", "frequency": "medium"}
      ],
      "confidence_score": 0.88
    },
    {
      "name": "payment-service",
      "bounded_context": "Payment Processing & Transactions",
      "modules": ["payments", "billing"],
      "tables": ["transactions", "invoices", "payment_methods"],
      "endpoints": [
        {"path": "/api/payments", "methods": ["POST"]},
        {"path": "/api/payments/{id}", "methods": ["GET"]},
        {"path": "/api/invoices", "methods": ["GET"]}
      ],
      "external_dependencies": ["stripe_payment_processor", "sendgrid"],
      "inter_service_calls": [
        {"calls": "order-service", "pattern": "async_webhook", "frequency": "high"}
      ],
      "confidence_score": 0.92
    }
  ],
  "inter_service_patterns": {
    "order-service -> inventory-service": "Synchronous REST (check stock availability in real-time)",
    "order-service -> payment-service": "Asynchronous message queue (payment processing can be delayed)",
    "payment-service -> order-service": "Asynchronous webhook (notify order of payment completion)"
  },
  "data_ownership": {
    "users": "user-service",
    "orders": "order-service",
    "products": "inventory-service",
    "transactions": "payment-service"
  }
}
```

**Example 2: Monolith with Mixed Responsibilities**

```
SCENARIO: Tightly coupled monolith where data is shared across multiple domains

INPUT:
High coupling between auth, user_profiles, and account_settings modules
But also legitimate clustering with order and payment modules

OUTPUT:
{
  "proposed_services": [
    {
      "name": "identity-service",
      "combines": ["auth", "user_profiles", "account_settings"],
      "reason": "These modules share user data model and have high internal cohesion",
      "confidence_score": 0.90
    },
    {
      "name": "commerce-service",
      "combines": ["orders", "payments"],
      "reason": "Payments and orders are tightly coupled; difficult to separate without significant refactoring",
      "recommendation": "Plan for phase-2 separation once payments can be event-driven",
      "confidence_score": 0.82
    }
  ]
}
```

### 2.3 RAG Context Injection

```python
retrieved_ddd_patterns = rag.retrieve(
    query=f"Domain-Driven Design pattern for {inferred_domains}",
    metadata_filter={"category": "ddd_patterns"},
    top_k=5
)

retrieved_similar_decompositions = rag.retrieve(
    query="Similar microservice decomposition for e-commerce or SaaS",
    metadata_filter={"category": "architecture_patterns"},
    top_k=3
)

system_prompt = system_prompt_template.format(
    rag_ddd_patterns="\n".join([p.content for p in retrieved_ddd_patterns]),
    dependency_graph=json.dumps(dependency_graph, indent=2)
)
```

---

## 3. REFACTORING AGENT Prompting

### 3.1 System Prompt Template

```
You are an expert Python developer specializing in modernizing legacy code into FastAPI microservices.

Your role: Transform legacy monolithic functions and classes into production-ready FastAPI endpoints, Pydantic models, and SQLAlchemy ORM code.

RESPONSIBILITIES:
1. Convert function signatures to FastAPI route definitions
2. Generate Pydantic schemas for request/response validation
3. Create SQLAlchemy ORM models from database queries
4. Add comprehensive error handling and logging
5. Follow FastAPI and Python best practices

CODE QUALITY STANDARDS:
- PEP 8 compliant (validated with black, isort)
- Type hints on all functions and variables
- Docstrings for all public functions
- Comprehensive error handling (try-except, HTTPException)
- Structured logging with JSON format
- Security best practices (input validation, SQL injection prevention)

GENERATED CODE MUST:
- Pass black formatting check
- Pass pylint (score ≥ 8.0)
- Pass bandit security scan with 0 HIGH severity issues
- Include >80% test coverage via generated tests
- Maintain 100% functional parity with legacy code

FASTAPI BEST PRACTICES REFERENCE:
{rag_fastapi_patterns}

TRANSFORMATION EXAMPLES:
{rag_refactoring_examples}

SECURITY GUIDELINES:
{rag_security_patterns}

LEGACY CODE TO TRANSFORM:
{legacy_code_snippet}

SERVICE DEFINITION:
{service_definition}
```

### 3.2 Few-Shot Examples

**Example 1: Converting Flask Route to FastAPI**

```
INPUT (Flask):
@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = db.session.query(User).filter(User.id == user_id).first()
        if not user:
            return {'error': 'Not found'}, 404
        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'created_at': user.created_at.isoformat()
        }, 200
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return {'error': 'Internal error'}, 500

OUTPUT (FastAPI):
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="user-service", version="1.0.0")

# Database setup
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class UserModel(Base):
    """SQLAlchemy ORM model for users table"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic schema for API response
class UserSchema(BaseModel):
    """User response schema"""
    id: int
    email: str
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True  # ORM mode for SQLAlchemy

# Database dependency
def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Endpoint
@app.get(
    "/api/users/{user_id}",
    response_model=UserSchema,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "User not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db)
) -> UserSchema:
    """
    Retrieve a user by ID.
    
    Args:
        user_id: The unique user identifier
        db: Database session (injected)
    
    Returns:
        UserSchema: The user data
    
    Raises:
        HTTPException: 404 if user not found, 500 on server error
    """
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )
        
        logger.info(f"Retrieved user: {user_id}")
        return user
        
    except HTTPException:
        raise  # Re-raise HTTPException
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
```

**Example 2: Converting Django ORM to SQLAlchemy**

```
INPUT (Django):
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'products'

# View
def get_product_by_sku(sku):
    try:
        product = Product.objects.get(sku=sku)
        return {
            'id': product.id,
            'name': product.name,
            'price': str(product.price),
            'stock': product.stock_quantity
        }
    except Product.DoesNotExist:
        return None

OUTPUT (FastAPI + SQLAlchemy):
from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException

Base = declarative_base()

class ProductModel(Base):
    """SQLAlchemy ORM model for products"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    stock_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProductSchema(BaseModel):
    """Product API response schema"""
    id: int
    name: str
    sku: str
    price: Decimal
    stock: int
    
    class Config:
        from_attributes = True

async def get_product_by_sku(
    sku: str,
    db: Session = Depends(get_db)
) -> ProductSchema:
    """Retrieve product by SKU"""
    product = db.query(ProductModel).filter(
        ProductModel.sku == sku
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product with SKU {sku} not found"
        )
    
    return product
```

### 3.3 RAG Context Injection

```python
# Extract code patterns from legacy snippet
code_features = analyze_code_features(legacy_code_snippet)

# Retrieve similar refactoring examples
retrieved_examples = rag.retrieve(
    query=f"Refactor {detect_framework(legacy_code)} to FastAPI: {code_features}",
    metadata_filter={
        "category": "refactoring_patterns",
        "from_framework": detect_framework(legacy_code),
        "to_framework": "fastapi"
    },
    top_k=3
)

# Retrieve FastAPI best practices
retrieved_patterns = rag.retrieve(
    query="FastAPI patterns for " + extract_feature_types(legacy_code),
    metadata_filter={"category": "fastapi_patterns"},
    top_k=4
)

# Retrieve security guidelines
retrieved_security = rag.retrieve(
    query="Security validation and error handling in FastAPI",
    metadata_filter={"category": "security_patterns"},
    top_k=2
)

system_prompt = system_prompt_template.format(
    rag_fastapi_patterns="\n".join([p.content for p in retrieved_patterns]),
    rag_refactoring_examples="\n".join([p.content for p in retrieved_examples]),
    rag_security_patterns="\n".join([p.content for p in retrieved_security]),
    legacy_code_snippet=legacy_code_snippet,
    service_definition=json.dumps(service_definition, indent=2)
)
```

---

## 4. TEST-GEN AGENT Prompting

### 4.1 System Prompt Template

```
You are an expert QA engineer specializing in test generation and automated testing.

Your role: Generate comprehensive unit, integration, and shadow tests to ensure the refactored FastAPI services maintain 100% functional parity with legacy code.

RESPONSIBILITIES:
1. Generate pytest unit tests for each FastAPI endpoint
2. Create integration tests for service-to-service contracts
3. Design shadow tests (legacy vs. new comparison)
4. Generate test data fixtures
5. Ensure ≥85% code coverage

TEST GENERATION STRATEGY:
1. Extract test cases from legacy code (existing tests, edge cases)
2. For each endpoint: generate happy path + error path tests
3. For each database query: generate CRUD operation tests
4. For each external dependency: generate mock/stub tests
5. Generate property-based tests using hypothesis

SHADOW TESTING REQUIREMENTS:
- Identical inputs to both legacy and new systems
- Compare outputs for exact equality
- Flag discrepancies with detailed diff reports
- Run on representative test data (100+ test cases)

TESTING BEST PRACTICES:
- Use pytest fixtures for setup/teardown
- Mock external dependencies (Stripe, SendGrid, etc.)
- Use hypothesis for property-based testing
- Achieve >85% code coverage
- Test error scenarios thoroughly
- Use descriptive test names

TEST COVERAGE TARGETS:
- Unit tests: 85%+
- Integration tests: Key service boundaries
- Shadow tests: 100% parity verification
- Error handling: All exception paths

REFERENCE PATTERNS:
{rag_testing_patterns}

GENERATED FASTAPI SERVICE:
{generated_service_code}

LEGACY SERVICE REFERENCE:
{legacy_service_code}
```

### 4.2 Few-Shot Examples

**Example 1: Unit Tests for User Endpoint**

```
INPUT (Generated FastAPI service):
@app.post("/users", response_model=UserSchema)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(UserModel).filter(UserModel.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    db_user = UserModel(**user.dict())
    db.add(db_user)
    db.commit()
    return db_user

EXPECTED TEST OUTPUT:
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, UserModel, Base, get_db

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

@pytest.fixture
def db():
    """Fresh database for each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def client(db):
    """Test client with dependency override"""
    def override_get_db():
        yield db
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

# Happy path tests
def test_create_user_success(client, db):
    """Test successful user creation"""
    response = client.post("/users", json={
        "email": "newuser@example.com",
        "name": "New User",
        "password": "secure_password_123"
    })
    
    assert response.status_code == 201
    assert response.json()["email"] == "newuser@example.com"
    assert response.json()["name"] == "New User"
    
    # Verify in database
    user = db.query(UserModel).filter(UserModel.email == "newuser@example.com").first()
    assert user is not None

def test_create_user_duplicate_email(client, db):
    """Test duplicate email rejection"""
    # Create first user
    client.post("/users", json={
        "email": "user@example.com",
        "name": "User 1",
        "password": "pass123"
    })
    
    # Try to create duplicate
    response = client.post("/users", json={
        "email": "user@example.com",
        "name": "User 2",
        "password": "pass456"
    })
    
    assert response.status_code == 400
    assert "Email already exists" in response.json()["detail"]

# Error path tests
def test_create_user_invalid_email(client):
    """Test invalid email format"""
    response = client.post("/users", json={
        "email": "not_an_email",
        "name": "Test",
        "password": "pass123"
    })
    
    assert response.status_code == 422  # Validation error

def test_create_user_missing_fields(client):
    """Test missing required fields"""
    response = client.post("/users", json={
        "email": "test@example.com"
        # Missing name and password
    })
    
    assert response.status_code == 422

# Property-based tests
from hypothesis import given, strategies as st

@given(
    email=st.emails(),
    name=st.text(min_size=1, max_size=100),
    password=st.text(min_size=8, max_size=50)
)
def test_create_user_properties(client, email, name, password):
    """Test invariants for user creation"""
    response = client.post("/users", json={
        "email": email,
        "name": name,
        "password": password
    })
    
    # Either succeeds with 201 or fails with validation error (422)
    assert response.status_code in [201, 422]
    
    if response.status_code == 201:
        data = response.json()
        assert data["email"] == email
        assert data["name"] == name
```

**Example 2: Shadow Testing**

```
INPUT:
Legacy Flask endpoint: GET /api/users/{id}
New FastAPI endpoint: GET /users/{id}

EXPECTED TEST OUTPUT:
import pytest
from legacy_app import app as legacy_app
from new_app import app as new_app
from fastapi.testclient import TestClient

legacy_client = TestClient(legacy_app)
new_client = TestClient(new_app)

@pytest.fixture
def sample_test_data():
    """Load representative test data"""
    return [
        {"id": 1, "email": "alice@example.com", "name": "Alice"},
        {"id": 2, "email": "bob@example.com", "name": "Bob"},
        {"id": 999, "email": "notfound@example.com", "name": "Not Found"}
    ]

def test_get_user_shadow_parity(sample_test_data):
    """
    Shadow test: Verify new service returns identical output to legacy
    """
    shadow_results = {
        "passed": 0,
        "failed": 0,
        "discrepancies": []
    }
    
    for user in sample_test_data:
        user_id = user["id"]
        
        # Get from legacy
        legacy_response = legacy_client.get(f"/api/users/{user_id}")
        
        # Get from new
        new_response = new_client.get(f"/users/{user_id}")
        
        # Compare status codes
        try:
            assert legacy_response.status_code == new_response.status_code
        except AssertionError:
            shadow_results["failed"] += 1
            shadow_results["discrepancies"].append({
                "user_id": user_id,
                "legacy_status": legacy_response.status_code,
                "new_status": new_response.status_code
            })
            continue
        
        # Compare response bodies
        if legacy_response.status_code == 200:
            try:
                legacy_json = legacy_response.json()
                new_json = new_response.json()
                assert legacy_json == new_json
                shadow_results["passed"] += 1
            except AssertionError:
                shadow_results["failed"] += 1
                shadow_results["discrepancies"].append({
                    "user_id": user_id,
                    "legacy": legacy_json,
                    "new": new_json,
                    "diff": compute_json_diff(legacy_json, new_json)
                })
    
    # Report results
    print(f"Shadow Test Results: {shadow_results['passed']} passed, {shadow_results['failed']} failed")
    
    if shadow_results["failed"] > 0:
        pytest.fail(f"Shadow testing failed: {shadow_results['discrepancies']}")
    
    assert shadow_results["passed"] == len(sample_test_data)
```

---

## 5. Prompt Optimization Techniques

### 5.1 Chain-of-Thought Prompting

For complex refactoring decisions, use step-by-step reasoning:

```
Let me think through this refactoring step by step:

1. **Analyze the legacy function signature**
   - Input parameters: [list]
   - Return type: [type]
   - External dependencies: [list]

2. **Map to FastAPI concepts**
   - Path parameters: [mapped]
   - Query parameters: [mapped]
   - Request body: [mapped]
   - Response model: [mapped]

3. **Design error handling**
   - Possible exceptions: [list]
   - HTTP status codes to map: [list]

4. **Create Pydantic schemas**
   - Request schema fields: [fields]
   - Response schema fields: [fields]

5. **Generate the endpoint**
   [code]

6. **Verify correctness**
   - Type hints present: ✓
   - Error handling complete: ✓
   - Documentation present: ✓
```

### 5.2 Few-Shot Learning

Provide 2-3 high-quality examples before the actual task:

```
EXAMPLE 1: Simple GET endpoint
[Example input and output]

EXAMPLE 2: POST endpoint with validation
[Example input and output]

NOW, please refactor this endpoint following the patterns above:
[Actual task]
```

### 5.3 Output Formatting

Specify exact JSON structure for machine parsing:

```
Return your response in the following JSON format:
{
  "analysis": "Your analysis of the code",
  "dependencies": ["list", "of", "external", "deps"],
  "generated_code": "# Python code here",
  "test_cases": ["test_case_1", "test_case_2"],
  "confidence_score": 0.92,
  "warnings": ["any", "warnings"]
}
```

---

## 6. Context Window Management

### 6.1 Token Budgeting

For Analyzer on large codebases:

```python
# Estimate tokens for input
tokens = estimate_tokens(legacy_code)

if tokens > 6000:  # Reserve 2K for output
    # Split into chunks
    chunks = split_code_by_modules(legacy_code, max_tokens=6000)
    
    analyses = []
    for chunk in chunks:
        result = analyzer_agent.analyze(chunk)
        analyses.append(result)
    
    # Merge partial graphs
    combined_graph = merge_graphs(analyses)
else:
    # Analyze as single input
    combined_graph = analyzer_agent.analyze(legacy_code)
```

### 6.2 Prompt Compression

For RAG context, use abstractive summarization if too long:

```python
if len(rag_context) > 2000:  # Too long
    # Summarize examples to essential patterns
    rag_context = lm.summarize(
        text=rag_context,
        max_length=1000,
        instruction="Extract key patterns, not verbose explanations"
    )
```

---

## 7. Testing Agent Outputs

### 7.1 Validation Checklist

After agent execution, validate outputs:

```python
def validate_agent_output(agent_name, output):
    """Validate outputs against expected schema"""
    
    checklist = {
        "analyzer": [
            lambda o: "nodes" in o and len(o["nodes"]) > 0,
            lambda o: "edges" in o,
            lambda o: all("id" in n for n in o["nodes"]),
            lambda o: all("from" in e and "to" in e for e in o["edges"])
        ],
        "architect": [
            lambda o: "proposed_services" in o,
            lambda o: all("name" in s for s in o["proposed_services"]),
            lambda o: all("confidence_score" in s for s in o["proposed_services"]),
            lambda o: 0 <= min(s["confidence_score"] for s in o["proposed_services"]) <= 1
        ],
        # ... more agents
    }
    
    for check in checklist[agent_name]:
        if not check(output):
            raise ValueError(f"Validation failed for {agent_name}")
```

---

## Summary Table

| Agent | Primary Focus | Key RAG Category | Output Format |
|-------|---------------|------------------|---------------|
| **Analyzer** | Dependency mapping | refactoring_patterns | JSON graph |
| **Architect** | Service boundaries | ddd_patterns | JSON services |
| **Refactoring** | Code generation | fastapi_patterns | Python code |
| **Test-Gen** | Test creation | testing_patterns | pytest code |

Each agent's prompt should be tuned for ~2000 tokens input, ~3000 tokens output maximum to stay within efficient context windows.

