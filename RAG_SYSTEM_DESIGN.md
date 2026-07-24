# RAG System Design & Knowledge Base Strategy

## Overview

The Retrieval-Augmented Generation (RAG) system augments each agent with contextual information from a specialized knowledge base, enabling smarter architectural decisions, better code generation, and faster refactoring cycles. This document details the RAG pipeline architecture, knowledge base structure, and integration points with the multi-agent system.

---

## RAG Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE BASE LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  FastAPI     │  │   DDD        │  │   Patterns   │  ...     │
│  │  Patterns    │  │   Patterns   │  │   Library    │           │
│  │  (200 docs)  │  │   (150 docs) │  │  (300 docs)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Security    │  │   Testing    │  │   Database   │  ...     │
│  │  Best Prac.  │  │   Templates  │  │   Patterns   │           │
│  │  (120 docs)  │  │  (180 docs)  │  │  (100 docs)  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌──────────────────┐
                    │  Semantic        │
                    │  Chunking        │
                    │  Engine          │
                    └──────────────────┘
                              ↓
        ┌─────────────────────────────────────────┐
        │         Text Embeddings                  │
        │  (OpenAI / Ollama local embeddings)     │
        └─────────────────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────┐
        │      Vector Database (Pinecone)         │
        │   - 50K+ vectorized documents           │
        │   - Metadata filtering by category      │
        │   - Similarity search (cosine distance) │
        └─────────────────────────────────────────┘
                              ↓
        ┌──────────────────────────────────────────────┐
        │         Agent-Specific Retrievers            │
        │  ┌──────────────┐  ┌──────────────┐        │
        │  │   Analyzer   │  │   Architect  │  ...   │
        │  │   Retriever  │  │   Retriever  │        │
        │  └──────────────┘  └──────────────┘        │
        └──────────────────────────────────────────────┘
                              ↓
        ┌──────────────────────────────────────────────┐
        │  Augmented Agent Context (LLM Prompts)      │
        │  - Retrieved examples                        │
        │  - Relevant code snippets                    │
        │  - Best practices & patterns                 │
        └──────────────────────────────────────────────┘
```

---

## Knowledge Base Structure

### 1. Document Categories & Content

#### Category 1: FastAPI Patterns (200 documents)
**Purpose**: Teach agents how to structure and generate FastAPI code correctly

**Content Types:**
- Basic routing patterns (GET, POST, PUT, DELETE)
- Dependency injection examples
- Middleware configuration
- Error handling patterns
- Async/await patterns
- Database integration (SQLAlchemy)
- Authentication & authorization
- Request/response validation (Pydantic)
- OpenAPI schema generation

**Example Document:**
```markdown
# FastAPI Dependency Injection Pattern

## Context
FastAPI uses Python type hints for automatic dependency resolution.

## Pattern
```python
from fastapi import FastAPI, Depends

async def get_db():
    db = connect_to_database()
    yield db
    db.close()

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db = Depends(get_db)):
    return db.query(User).filter(User.id == user_id).first()
```

## When to Use
- Database connection management
- Authentication/authorization checks
- Rate limiting
- Logging & monitoring

## Anti-patterns
- Avoid global variables for database connections
- Don't share Depends() instances across multiple routes

## Metadata
- category: "fastapi_patterns"
- difficulty: "intermediate"
- related_patterns: ["context_managers", "async_patterns"]
```

**Indexing Strategy:**
- Embed each pattern's title + description + code snippet
- Use metadata filters: `category="fastapi_patterns"`, `difficulty="beginner|intermediate|advanced"`
- Create hierarchical retrieval: basic patterns → advanced patterns based on refactoring agent complexity needs

---

#### Category 2: Domain-Driven Design Patterns (150 documents)
**Purpose**: Guide Architect Agent in identifying bounded contexts and service boundaries

**Content Types:**
- Aggregate root identification
- Value object definition
- Service boundary patterns
- Anti-corruption layers
- Event sourcing patterns
- CQRS (Command Query Responsibility Segregation)
- Domain events
- Repository patterns

**Example Document:**
```markdown
# Identifying Bounded Contexts in Microservices

## Problem
Large monoliths have tangled domain models that make service boundary identification difficult.

## Solution
Use domain-driven design to identify bounded contexts—subsystems with well-defined boundaries and explicit contracts.

## Pattern
1. Identify core domain areas (User, Order, Payment)
2. Define bounded context for each area
3. Specify context boundaries (API contracts)
4. Map dependencies between contexts

## Example: E-commerce System
```
Domain: Order Management
├─ Entities: Order, OrderItem, OrderStatus
├─ Aggregate Root: Order
├─ Repository: OrderRepository
├─ Service: OrderService
└─ Events: OrderCreated, OrderPaid

Boundary Contracts:
- User Service → Order Service: CreateOrder(user_id, items)
- Payment Service → Order Service: OrderPaid(order_id, amount)
```

## Metrics for Good Boundaries
- High cohesion within context (80%+ internal calls)
- Low coupling between contexts (15%- external calls)
- Clear API contracts between services

## Metadata
- category: "ddd_patterns"
- domain: "ecommerce|saas|financial"
- complexity: "high"
- related_concepts: ["microservices", "api_contracts"]
```

**Indexing Strategy:**
- Embed domain models and context diagrams
- Metadata filters: `category="ddd_patterns"`, `domain="ecommerce"` (for domain-specific context)
- Create graph-based retrieval: find patterns for similar domain structures

---

#### Category 3: Refactoring Patterns Library (300 documents)
**Purpose**: Provide concrete examples of similar monolith-to-microservice transformations

**Content Types:**
- Code transformation examples (monolith → FastAPI)
- Module extraction patterns
- Database schema splitting
- Common refactoring anti-patterns
- Technology stack migration stories

**Example Document:**
```markdown
# Flask Monolith → FastAPI Microservice: User Service Refactoring

## Original Flask Code (Monolith)
```python
# app.py
from flask import Flask, request, jsonify
from database import db, User

app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
def list_users():
    users = db.session.query(User).all()
    return jsonify([{"id": u.id, "email": u.email, "name": u.name} for u in users])

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = db.session.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "Not found"}, 404
    return jsonify({"id": user.id, "email": user.email, "name": user.name})
```

## Refactored FastAPI Service
```python
# services/user_service/main.py
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import engine, SessionLocal, Base, UserModel

Base.metadata.create_all(bind=engine)
app = FastAPI(title="user-service", version="1.0.0")

class UserSchema(BaseModel):
    id: int
    email: str
    name: str
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/users", response_model=List[UserSchema])
async def list_users(db: Session = Depends(get_db)):
    users = db.query(UserModel).all()
    return users

@app.get("/users/{user_id}", response_model=UserSchema)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

## Transformation Rules Applied
1. Flask app → FastAPI app instance
2. Flask routes → Pydantic + type-hinted FastAPI endpoints
3. Direct DB access → Dependency-injected sessions
4. Dict returns → Pydantic models
5. 404 error handling → HTTPException

## Metadata
- category: "refactoring_patterns"
- from_framework: "flask"
- to_framework: "fastapi"
- domain: "user_management"
- complexity: "low"
- lines_of_code_changed: 45
```

**Indexing Strategy:**
- Embed code snippets from both before/after states
- Create metadata: `from_framework="flask"`, `to_framework="fastapi"`, `domain="user_management"`
- Use semantic search: "Convert Django user authentication to FastAPI" → find similar patterns

---

#### Category 4: Security Best Practices (120 documents)
**Purpose**: Ensure generated code follows security standards (OWASP Top 10)

**Content Types:**
- Input validation patterns
- SQL injection prevention (using SQLAlchemy parameterization)
- Authentication & authorization
- Secrets management
- CORS configuration
- Rate limiting
- Logging sensitive data precautions

**Example Document:**
```markdown
# Input Validation in FastAPI

## Best Practice
Always validate user input at service boundaries using Pydantic models.

## Anti-pattern (Vulnerable)
```python
@app.post("/users")
async def create_user(user_data: dict):
    # Directly using dict without validation
    db.insert(user_data)  # SQL injection risk!
```

## Best Pattern (Secure)
```python
from pydantic import BaseModel, EmailStr, constr

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    name: constr(max_length=100)

@app.post("/users", response_model=UserSchema)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Pydantic validates: valid email, password 8+ chars, name max 100 chars
    db_user = UserModel(**user.dict())
    db.add(db_user)
    db.commit()
    return db_user
```

## Metadata
- category: "security_patterns"
- owasp_category: "A01:2021_injection"
- severity: "critical"
```

**Indexing Strategy:**
- Link to OWASP Top 10 categories
- Embed both vulnerable and secure code patterns
- Metadata: `severity="critical|high|medium"`

---

#### Category 5: Testing & Shadow Testing Templates (180 documents)
**Purpose**: Provide test case templates for Test-Gen Agent

**Content Types:**
- Unit test patterns (pytest)
- Integration test patterns
- Shadow testing examples
- Test data generation
- Mocking strategies
- Coverage goals

**Example Document:**
```markdown
# Shadow Testing Pattern: User Service

## Objective
Run identical inputs against legacy Flask app and new FastAPI service, compare outputs to ensure 100% functional parity.

## Setup
```python
# tests/shadow_tests.py
import pytest
from user_service import app as new_app
from legacy_app import app as legacy_app
from fastapi.testclient import TestClient

new_client = TestClient(new_app)
legacy_client = TestClient(legacy_app)

@pytest.fixture
def sample_users():
    return [
        {"id": 1, "email": "alice@example.com", "name": "Alice"},
        {"id": 2, "email": "bob@example.com", "name": "Bob"},
    ]

def test_get_user_shadow(sample_users):
    """Verify new service returns identical output to legacy app"""
    for user in sample_users:
        legacy_response = legacy_client.get(f"/api/users/{user['id']}")
        new_response = new_client.get(f"/users/{user['id']}")
        
        assert legacy_response.json() == new_response.json()
        assert legacy_response.status_code == new_response.status_code
```

## Validation Criteria
- Response body matches exactly
- Status codes match
- Response headers (where relevant) match
- Latency: New service ≤ 2x legacy (acceptable overhead)

## Metadata
- category: "testing_patterns"
- test_type: "shadow_testing"
- language: "python"
```

**Indexing Strategy:**
- Embed full test code examples
- Metadata: `test_type="unit|integration|shadow"`, `language="python|java"`

---

#### Category 6: Database Migration Patterns (100 documents)
**Purpose**: Guide database schema refactoring and ORM model generation

**Content Types:**
- Schema normalization patterns
- ORM model design (SQLAlchemy)
- Data migration strategies
- Multi-database scenarios
- Foreign key handling
- Denormalization trade-offs

**Example Document:**
```markdown
# Monolith Database → Microservice Database Schema Refactoring

## Problem
Monolithic database often has tables shared across multiple logical domains, creating tight coupling.

## Solution: Database per Service Pattern
1. Identify tables for each microservice
2. Create separate database schemas
3. Use API contracts instead of shared tables
4. Handle data synchronization via async messaging

## Example
```sql
-- Original Monolith: Single Database
CREATE TABLE users (id INT, email VARCHAR, name VARCHAR);
CREATE TABLE orders (id INT, user_id INT, total DECIMAL);
CREATE TABLE payments (id INT, order_id INT, status VARCHAR);

-- After Refactoring: Separate Databases

-- User Service DB
CREATE TABLE users (id INT PRIMARY KEY, email VARCHAR UNIQUE, name VARCHAR);

-- Order Service DB
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,  -- Reference only, no FK to users table
    total DECIMAL,
    created_at TIMESTAMP
);

-- Payment Service DB
CREATE TABLE payments (
    id INT PRIMARY KEY,
    order_id INT,
    status VARCHAR,
    amount DECIMAL
);
```

## SQLAlchemy ORM Model Generation
```python
# order_service/models.py
from sqlalchemy import Column, Integer, String, DateTime, Numeric
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)  # NOT a foreign key - cross-service reference
    total = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
```

## Metadata
- category: "database_patterns"
- pattern_type: "schema_refactoring"
- complexity: "medium"
```

---

### 2. Knowledge Base Statistics

```
Total Documents: ~1,150
Average Document Length: 400-800 words
Total Embeddings: ~5,000+ (multi-chunk docs)
Storage: Pinecone (cloud) or Weaviate (self-hosted)
Embedding Model: OpenAI text-embedding-3-small (1536 dims) or Ollama

Category Breakdown:
├─ FastAPI Patterns: 200 docs (17%)
├─ DDD Patterns: 150 docs (13%)
├─ Refactoring Patterns: 300 docs (26%)
├─ Security Best Practices: 120 docs (10%)
├─ Testing Templates: 180 docs (16%)
├─ Database Patterns: 100 docs (9%)
└─ Other (CI/CD, Monitoring, etc.): 100 docs (9%)
```

---

## Semantic Chunking Strategy

### Chunking Algorithm

```python
class SemanticChunker:
    """
    Split documents into meaningful chunks that preserve semantic coherence.
    Standard chunking (fixed size) loses context; semantic chunking preserves meaning.
    """
    
    def chunk_by_semantics(self, text, target_chunk_size=500):
        """
        1. Split by logical boundaries (section headers, code blocks)
        2. Group related sentences until reaching target size
        3. Add context from parent section
        """
        chunks = []
        
        # Step 1: Identify logical boundaries
        sections = self.split_by_headers(text)
        
        for section_title, section_content in sections:
            # Step 2: Split section into sentence groups
            sentences = sent_tokenize(section_content)
            current_chunk = f"[Section: {section_title}]\n"
            
            for sentence in sentences:
                if len(encode(current_chunk + sentence)) < target_chunk_size:
                    current_chunk += sentence + " "
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk)
                    current_chunk = f"[Section: {section_title}]\n{sentence} "
            
            if current_chunk.strip():
                chunks.append(current_chunk)
        
        return chunks
    
    def chunk_code_blocks(self, text):
        """For code-heavy documents, preserve code block integrity"""
        chunks = []
        current_chunk = ""
        in_code_block = False
        
        for line in text.split('\n'):
            if line.startswith('```'):
                in_code_block = not in_code_block
                current_chunk += line + '\n'
            elif in_code_block:
                # Keep entire code block together
                current_chunk += line + '\n'
            else:
                if len(encode(current_chunk + line)) > 500:
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
        
        if current_chunk.strip():
            chunks.append(current_chunk)
        
        return chunks
```

### Indexing Configuration

```python
knowledge_base.index_with_config(
    documents=all_docs,
    chunking_strategy="semantic",
    chunk_size=500,
    chunk_overlap=100,  # 100 token overlap for context
    embedding_model="text-embedding-3-small",
    vector_db="pinecone",
    metadata_fields={
        "category": str,
        "difficulty": ["beginner", "intermediate", "advanced"],
        "domain": str,
        "related_patterns": list,
        "language": str
    }
)
```

---

## Agent-Specific Retrieval Strategies

### 1. Analyzer Agent Retriever

**Query Type**: "I'm analyzing a monolithic codebase. What are common dependency patterns I should look for?"

**Retrieval Logic**:
```python
def retrieve_for_analyzer(codebase_sample: str, top_k=5):
    queries = [
        # Multi-query retrieval for diverse context
        f"Common monolithic code patterns and coupling antipatterns",
        f"Dependency graph analysis and circular dependency detection",
        f"Code metrics for identifying refactoring hotspots",
        f"Sample monolithic architectures: {extract_key_terms(codebase_sample)}"
    ]
    
    results = []
    for query in queries:
        docs = vector_store.similarity_search(
            query=query,
            top_k=2,
            metadata_filter={"category": "refactoring_patterns"}
        )
        results.extend(docs)
    
    return deduplicate_and_rank(results, top_k)
```

**Retrieved Context Injected into Prompt**:
```
## Similar Codebases Analyzed
{retrieved_refactoring_patterns}

## Common Dependency Antipatterns
{retrieved_patterns_for_coupling}

Now analyze this codebase:
{user_codebase}
```

---

### 2. Architect Agent Retriever

**Query Type**: "How should I decompose this monolith into bounded contexts?"

**Retrieval Logic**:
```python
def retrieve_for_architect(dependency_graph: dict, domain_description: str, top_k=5):
    # Infer primary domain from codebase
    domains_detected = extract_domains(dependency_graph)
    
    queries = [
        f"Domain-Driven Design bounded context patterns for {domains_detected[0]}",
        f"Microservice boundary identification from monolithic dependency graph",
        f"Service mesh patterns and inter-service communication",
        f"Event-driven architecture vs. synchronous API patterns"
    ]
    
    results = []
    for query in queries:
        docs = vector_store.similarity_search(
            query=query,
            top_k=2,
            metadata_filter={"category": "ddd_patterns"}
        )
        results.extend(docs)
    
    return results
```

---

### 3. Refactoring Agent Retriever

**Query Type**: "Transform this Django view into a FastAPI endpoint"

**Retrieval Logic**:
```python
def retrieve_for_refactoring(legacy_code_snippet: str, target_framework="fastapi", top_k=5):
    # Identify source framework
    source_framework = detect_framework(legacy_code_snippet)
    
    queries = [
        f"Refactor {source_framework} to {target_framework}: {legacy_code_snippet[:100]}",
        f"{target_framework} patterns for {infer_feature_type(legacy_code_snippet)}",
        f"Database integration patterns in {target_framework}",
        f"Error handling and validation in {target_framework}"
    ]
    
    results = []
    for query in queries:
        docs = vector_store.similarity_search(
            query=query,
            top_k=2,
            metadata_filter={
                "category": "fastapi_patterns",
                "from_framework": source_framework,
                "to_framework": target_framework
            }
        )
        results.extend(docs)
    
    # Retrieve security patterns
    security_docs = vector_store.similarity_search(
        query="Security best practices for FastAPI endpoints",
        top_k=1,
        metadata_filter={"category": "security_patterns"}
    )
    results.extend(security_docs)
    
    return results
```

---

### 4. Test-Gen Agent Retriever

**Query Type**: "Generate tests for this FastAPI user service"

**Retrieval Logic**:
```python
def retrieve_for_test_gen(service_definition: dict, top_k=5):
    queries = [
        "FastAPI unit test patterns with pytest",
        "Shadow testing implementation for microservices",
        f"Test cases for {service_definition.get('endpoints', [])[0]['path']}",
        "Test data generation and mocking strategies"
    ]
    
    results = []
    for query in queries:
        docs = vector_store.similarity_search(
            query=query,
            top_k=2,
            metadata_filter={"category": "testing_patterns"}
        )
        results.extend(docs)
    
    return results
```

---

## RAG Integration with LLM Prompting

### System Prompt Enhancement

**Before (without RAG)**:
```
You are an expert refactoring agent. Convert this legacy code to FastAPI.
[Legacy Code]
```

**After (with RAG)**:
```
You are an expert refactoring agent. Convert this legacy code to FastAPI.

## Reference Examples (from knowledge base)
### Similar Transformation 1: Django View → FastAPI
[Retrieved refactoring example]

### Similar Transformation 2: Flask Routes → FastAPI
[Retrieved refactoring example]

## FastAPI Best Practices
[Retrieved FastAPI pattern docs]

## Security Checklist
[Retrieved security best practices]

## Now, refactor this legacy code:
[Legacy Code]

Generate production-ready FastAPI code following the patterns above.
```

### Context Scoring & Ranking

```python
class RAGScorer:
    """Score relevance of retrieved documents"""
    
    def score_retrieval(self, retrieved_docs, query, agent_type):
        scores = {}
        
        for doc in retrieved_docs:
            # 1. Semantic similarity (vector distance)
            semantic_score = 1 - doc.similarity_score  # Lower distance = higher score
            
            # 2. Category match (agent-specific)
            category_weight = self.AGENT_CATEGORY_WEIGHTS[agent_type].get(doc.category, 0.3)
            
            # 3. Recency (prefer recent docs)
            recency_score = 1.0 if doc.updated_at > (now - 365 days) else 0.7
            
            # 4. Usage frequency (popular patterns score higher)
            usage_score = min(doc.usage_count / 100, 1.0)
            
            final_score = (
                semantic_score * 0.5 +
                category_weight * 0.3 +
                recency_score * 0.1 +
                usage_score * 0.1
            )
            
            scores[doc.id] = final_score
        
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

---

## Knowledge Base Maintenance & Updates

### Continuous Ingestion Pipeline

```
Weekly Updates:
├─ Re-index FastAPI releases & changelog
├─ Monitor GitHub for trending microservice patterns
├─ Ingest community best practices (Dev.to, Medium)
└─ Update security patterns based on CVEs

Monthly Curation:
├─ Review usage analytics (which patterns were retrieved most?)
├─ Remove low-relevance documents
├─ Merge redundant or duplicate patterns
└─ Add missing patterns based on agent feedback

Quarterly Deep Dives:
├─ Full knowledge base validation
├─ Expert review of retrieval quality
├─ Benchmark retrieval latency & accuracy
└─ Plan major category expansions
```

### Feedback Loop

```python
class KnowledgeBaseFeedback:
    """Track agent usage of retrieved docs"""
    
    def log_retrieval(self, agent_name, query, retrieved_docs, used_docs):
        """
        Track which retrieved docs the agent actually used.
        Use to improve ranking and relevance.
        """
        for doc in retrieved_docs:
            was_used = doc.id in [d.id for d in used_docs]
            self.db.insert({
                "agent": agent_name,
                "doc_id": doc.id,
                "query": query,
                "used": was_used,
                "timestamp": now()
            })
    
    def compute_usage_metrics(self):
        """Generate analytics: which patterns are useful?"""
        most_used = self.db.query("""
            SELECT doc_id, COUNT(*) as usage_count
            FROM retrieval_logs
            WHERE used = true
            GROUP BY doc_id
            ORDER BY usage_count DESC
        """)
        
        return most_used
```

---

## Performance & Scalability Considerations

### Retrieval Latency

```
Target SLA: < 500ms per retrieval call

Optimization Strategy:
├─ Vector DB indexing (HNSW algorithm in Pinecone)
├─ Query result caching (Redis)
├─ Batch retrievals (retrieve multiple queries in parallel)
├─ Embedding cache (pre-compute common agent queries)
└─ Regional deployment (Pinecone multi-region)
```

### Scaling to Large Codebases

```python
class ContextWindowManager:
    """Handle large legacy codebases that exceed LLM context limits"""
    
    def analyze_in_chunks(self, large_codebase, chunk_size=8000):
        """
        Split large codebases into token-limited chunks.
        Each chunk analyzed independently, then synthesized.
        """
        chunks = self.split_codebase(large_codebase, max_tokens=chunk_size)
        
        analyses = []
        for chunk in chunks:
            analysis = self.analyzer_agent.analyze(chunk)
            analyses.append(analysis)
        
        # Synthesize results
        combined_graph = self.merge_dependency_graphs(
            [a.dependency_graph for a in analyses]
        )
        
        return combined_graph
    
    def hierarchical_abstraction(self, dependency_graph):
        """
        For very large graphs, create hierarchical abstraction:
        Top level: service boundaries
        Mid level: module clusters
        Low level: function calls
        """
        return {
            "services": self.cluster_graph(dependency_graph, level="coarse"),
            "modules": self.cluster_graph(dependency_graph, level="medium"),
            "functions": dependency_graph  # Full detail when needed
        }
```

---

## Retrieval Evaluation Metrics

```
Metric                          Target    Measurement
─────────────────────────────────────────────────────
Retrieval Precision (top-5)     ≥85%      % relevant docs in top 5 results
Retrieval Recall                ≥80%      % of known relevant docs retrieved
Mean Reciprocal Rank (MRR)      ≥0.85     Average rank of first relevant doc
NDCG@5                          ≥0.8      Ranking quality (discount for lower ranks)
Agent Success Rate with RAG     ≥92%      % of migrations completing successfully
Agent Success Rate without RAG  ≤75%      Control baseline
Context Relevance (human eval)  ≥90%      Human judges: is context relevant?
Retrieval Latency               ≤500ms    Time to return top-k results
```

---

## Deployment

### Development Environment
```bash
# Local Weaviate for development
docker run -p 8080:8080 semitechnologies/weaviate:latest

# Load knowledge base
python scripts/load_knowledge_base.py --db weaviate --mode dev
```

### Production Environment
```bash
# Use Pinecone cloud for scalability
pinecone.init(api_key=PINECONE_KEY, environment="us-west1-gcp")
index = pinecone.Index("architecture-migration-kb")

# Scheduled re-indexing
0 2 * * 0  # Weekly update at 2 AM Sunday
```

---

## Summary

The RAG system provides contextual intelligence to all agents, transforming them from generic code generators into domain-aware architects and refactorers. By maintaining a comprehensive knowledge base and intelligently retrieving relevant patterns, we achieve:

✅ **Higher quality generated code** — Guided by proven patterns  
✅ **Better architectural decisions** — Informed by DDD best practices  
✅ **Faster migration cycles** — Agents leverage learned patterns  
✅ **Reduced hallucination** — Grounded in real examples  
✅ **Continuous improvement** — Knowledge base evolves with feedback  

