# Quick Reference Guide — Architecture Migration Assistant

## Project at a Glance

**Goal**: Build an autonomous AI system that migrates legacy monoliths to microservices in **weeks instead of months**.

**Core Innovation**: Multi-agent orchestration (Analyzer → Architect → Refactoring → Test-Gen) + RAG knowledge base + HITL governance.

**Timeline**: 12 weeks | **Team Size**: 5 people | **Stack**: LangGraph, FastAPI, Pinecone, Claude 3.5 Sonnet

---

## Key Documents

| Document | Purpose | Read Time |
|----------|---------|-----------|
| **ARCHITECTURE_MIGRATION_IMPLEMENTATION_PLAN.md** | Full implementation roadmap, timelines, team structure | 30 min |
| **RAG_SYSTEM_DESIGN.md** | RAG pipeline architecture, knowledge base structure, retrieval strategies | 25 min |
| **ADVANCED_FEATURES_&_ENHANCEMENTS.md** | Multi-language support, incremental migration, monitoring, learning systems | 20 min |
| **QUICK_REFERENCE_GUIDE.md** (this file) | Quick lookup, key concepts, commands | 5 min |

---

## Core Agents & Their Roles

```
┌──────────────────────────────────────────────────────────────┐
│                 ANALYZER AGENT                                │
│  Input: Legacy monolithic code                               │
│  Output: Dependency graph, complexity metrics                │
│  Tools: AST parsing, Neo4j, radon library                    │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│              ARCHITECT AGENT (DDD)                            │
│  Input: Dependency graph, domain description                 │
│  Output: Microservice boundaries, service APIs               │
│  Tools: Graph clustering, RAG retrieval, domain patterns     │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│            REFACTORING AGENT (Code Gen)                      │
│  Input: Service boundary definitions, legacy code            │
│  Output: Production-ready FastAPI microservices              │
│  Tools: Jinja2 templates, Pydantic schemas, code linting     │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│              TEST-GEN AGENT                                   │
│  Input: Generated services, legacy logic                     │
│  Output: Unit tests, integration tests, shadow test suite    │
│  Tools: pytest, hypothesis, shadow testing engine            │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│         HUMAN-IN-THE-LOOP (HITL) DASHBOARD                   │
│  - Review architectural proposals                            │
│  - Approve code generation                                   │
│  - Inject feedback for refinement                            │
│  - Manage deployment releases                                │
└──────────────────────────────────────────────────────────────┘
```

---

## Technology Stack Cheat Sheet

### Orchestration & LLM
- **LangGraph**: Multi-agent state machine orchestration
- **LangChain**: LLM integration & tool abstraction
- **Claude 3.5 Sonnet**: Primary reasoning model
- **GPT-4o**: Fallback for code generation

### Code Analysis
- **Python AST**: Parse Python codebases
- **javalang / Roslyn**: Parse Java / C# codebases
- **NetworkX / Neo4j**: Dependency graph representation
- **Radon**: Code complexity metrics

### Code Generation & Validation
- **Jinja2**: Template rendering for FastAPI services
- **LibCST**: AST manipulation for code transformations
- **black / isort**: Code formatting
- **pylint / flake8**: Linting
- **bandit**: Security scanning

### RAG & Knowledge Base
- **Pinecone**: Vector database (cloud)
- **Weaviate**: Vector database (self-hosted alternative)
- **OpenAI text-embedding-3-small**: Embeddings
- **Ollama**: Local LLM alternative

### Testing & Quality
- **pytest**: Unit/integration testing framework
- **pytest-cov**: Code coverage
- **hypothesis**: Property-based testing
- **docker**: Sandbox for generated code execution

### Monitoring & Observability
- **OpenTelemetry**: Distributed tracing
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboard
- **structlog**: Structured logging

### Web UI
- **Streamlit**: HITL dashboard (fast, Python-native)
- **FastAPI**: Backend API for orchestrator

---

## Critical Implementation Checkpoints

### Week 1-2: Foundation
```
✅ LangGraph orchestrator skeleton
✅ Pinecone/Weaviate setup + initial KB load (500 documents)
✅ Tool registry & safety framework
✅ Sample monolith (Flask app) for testing
```

**Verification**: `python test_orchestrator.py --mode integration` ✓

---

### Week 3-4: Analyzer & Architect
```
✅ AST parser for Python codebases
✅ Dependency graph generation & visualization
✅ Graph clustering (Louvain algorithm)
✅ RAG integration for pattern retrieval
✅ Service boundary proposals with confidence scores
```

**Verification**: Run on sample Flask monolith, verify DDD output

---

### Week 5-6: Refactoring Agent
```
✅ FastAPI template engine
✅ Pydantic schema auto-generation from legacy models
✅ SQLAlchemy ORM model generation
✅ Code linting & formatting pipeline
✅ Generated services pass syntax validation
```

**Verification**: `pytest tests/refactoring_agent/ --cov=85%` ✓

---

### Week 7-8: Testing & Shadow Testing
```
✅ Test case extraction from legacy code
✅ pytest template generation
✅ Shadow testing engine (legacy vs. new side-by-side)
✅ Parity validation framework
✅ Coverage report generation
```

**Verification**: 100% functional parity on sample services

---

### Week 9-10: HITL Dashboard & Safety
```
✅ Streamlit UI with approval checkpoints
✅ Code sandbox (Docker container execution)
✅ Security scanning (Bandit integration)
✅ Audit logging system
✅ Human feedback injection mechanism
```

**Verification**: End-to-end approval workflow

---

### Week 11-12: Integration & Capstone
```
✅ End-to-end migration on real monolith
✅ Performance benchmarking (vs. manual refactoring)
✅ ROI analysis & cost breakdown
✅ Capstone presentation materials
✅ Documentation & deployment guide
```

**Verification**: Live demo on stage

---

## Key Metrics to Track

### Technical KPIs
| Metric | Target | Baseline |
|--------|--------|----------|
| Functional Parity | 100% | N/A |
| Code Coverage | ≥85% | Manual: ~65% |
| Security Issues (HIGH) | 0 | Manual: 3-5 per service |
| Syntax Errors in Generated Code | <1% | Manual: ~3% |
| Test Pass Rate | ≥95% | Manual: ~90% |

### Business KPIs
| Metric | Target | Baseline |
|--------|--------|----------|
| Migration Time per Service | 1-2 weeks | Manual: 4-8 weeks |
| Human Effort Reduction | 70% | Baseline: 100% |
| Cost Savings (5-8 services) | $250K-500K | @$30K/week engineer cost |
| Deployment Velocity Improvement | 3x faster | Monolith: 1 per month |

### Agent Performance
| Agent | Success Rate | Iterations to Approval | Quality Score |
|-------|--------------|----------------------|----------------|
| Analyzer | ≥95% | 1-2 | ≥0.90 |
| Architect | ≥90% | 2-3 | ≥0.85 |
| Refactoring | ≥85% | 2-4 | ≥0.80 |
| Test-Gen | ≥92% | 1-2 | ≥0.88 |

---

## Common Troubleshooting

### LLM Context Window Overflow
**Symptom**: Agent fails with "context_length_exceeded"
**Solution**: 
```python
# Use ContextWindowManager to chunk large codebases
chunks = context_manager.chunk_codebase(large_codebase, max_tokens=8000)
for chunk in chunks:
    analyzer.analyze(chunk)
```

---

### Poor Retrieval Quality (RAG)
**Symptom**: Retrieved documents not relevant to agent query
**Solution**:
```python
# Re-index with better chunking strategy
knowledge_base.reindex(
    chunking_strategy="semantic",
    chunk_overlap=100,
    min_chunk_size=200
)

# Evaluate retrieval with human judges
eval_results = evaluate_retrieval(test_queries=50, human_judges=3)
if eval_results.ndcg_5 < 0.75:
    refine_prompt_templates()
```

---

### Generated Code Fails Tests
**Symptom**: pytest fails on generated services
**Solution**:
```python
# Use AutomatedDebugger to fix common issues
from agents.error_recovery import AutomatedDebugger

debugger = AutomatedDebugger(kb=knowledge_base)
fixed_code, fixes = debugger.detect_and_fix_errors(
    generated_code=service_code,
    test_results=test_results
)

# If still failing, inject human feedback
if test_results.pass_rate < 0.90:
    hitl.request_feedback(
        code=service_code,
        failures=test_results.failures,
        agent="refactoring_agent"
    )
```

---

### Agent Stuck in Infinite Loop
**Symptom**: Orchestrator keeps retrying same operation
**Solution**:
```python
# Check iteration count
if state.iteration_count >= MAX_ITERATIONS (15):
    # Force HITL review
    hitl.escalate_to_human(
        agent=current_agent,
        state=state,
        reason="Max iterations exceeded"
    )
    # Or retry with different prompt
    agent.system_prompt = generate_alternative_prompt(state)
```

---

## Performance Optimization Tips

### 1. Cache RAG Results
```python
cache = RedisCache(ttl=3600)

@cache.cached(key_func=lambda q: f"retrieval:{hash(q)}")
def retrieve_from_kb(query: str):
    return vector_store.similarity_search(query)
```

### 2. Batch LLM Calls
```python
# Instead of sequential calls
for service in services:
    response = client.messages.create(...)  # Slow

# Use batch processing
batch_jobs = client.beta.batch.create(
    requests=[
        {"custom_id": f"service_{i}", "params": {...}}
        for i, service in enumerate(services)
    ]
)
```

### 3. Pre-warm Vector DB Indexes
```python
# Create HNSW index on first startup
vector_db.create_index(
    dimension=1536,
    metric="cosine",
    index_type="hnsw",
    ef_construction=500
)
```

---

## Development Workflow

### Local Development Setup
```bash
# 1. Clone repo
git clone https://github.com/YOUR_ORG/architecture-migration.git
cd architecture-migration

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start local services
docker-compose up -d  # Weaviate, Redis, PostgreSQL

# 4. Load knowledge base
python scripts/load_knowledge_base.py --mode dev

# 5. Run tests
pytest tests/ -v --cov

# 6. Start UI dashboard
streamlit run ui/dashboard.py
```

### Running End-to-End Migration
```bash
python main.py \
  --project-name "flask_to_fastapi" \
  --source-repo /path/to/legacy/flask/app \
  --target-framework fastapi \
  --auto-approve false  # Requires HITL approval at each checkpoint
```

### Deploying to Production
```bash
# Build Docker image
docker build -t architecture-migration:v1.0 .

# Deploy to AWS/GCP/Azure
terraform apply  # Provision infrastructure
helm install migration-assistant ./helm/  # Deploy K8s services

# Verify deployment
kubectl logs -f deployment/orchestrator  # Monitor logs
```

---

## Resource Allocation

### Team Composition (Recommended)
```
1x Project Manager/Scrum Master (100%)
  - WBS management, risk tracking, stakeholder updates

1x AI/ML Architect (100%)
  - LangGraph design, prompt engineering, RAG strategy

2x Backend Engineers (100% each)
  - Agents, code generation, testing infrastructure

1x DevOps/Infrastructure (100%)
  - Cloud setup, CI/CD, monitoring, database management

0.5x Solutions Architect (part-time)
  - Enterprise architecture guidance, design reviews
```

### Cost Estimate (12 weeks)
```
Labor: 5.5 people × 12 weeks × $200/hour = $264,000
Infrastructure: Pinecone ($300/mo), AWS ($500/mo), misc = $12,000
LLM API Costs: ~$50,000 (1M tokens at $0.05/token average)
────────────────────────────────────────────────
Total: ~$326,000

ROI on first 5-8 service migrations:
  Manual approach: 5 services × $120K/service = $600K
  Automated approach: $326K system + $50K per service = ~$550K
  Net savings: ~$50K + 28 weeks saved = immediate ROI
```

---

## Success Criteria for Capstone

**Technical Requirements (70% of grade)**
- ✅ End-to-end migration on real monolith (Flask/Django/Spring)
- ✅ 100% functional parity (shadow testing passes)
- ✅ ≥85% code coverage on generated services
- ✅ 0 HIGH severity security issues (Bandit)
- ✅ All agents functioning autonomously

**Business Impact (20% of grade)**
- ✅ Quantified time savings (weeks vs. months)
- ✅ Cost ROI calculation
- ✅ Live demo showcasing agent decision-making
- ✅ Comparative analysis vs. manual approach

**Documentation & Presentation (10% of grade)**
- ✅ Architecture documentation (5-10 pages)
- ✅ Agent design & prompt engineering guide
- ✅ RAG system performance metrics
- ✅ Deployment guide & runbooks
- ✅ 20-minute capstone presentation

---

## Links & Resources

**Documentation**
- FastAPI: https://fastapi.tiangolo.com/
- LangGraph: https://langchain-ai.github.io/langgraph/
- Pinecone: https://docs.pinecone.io/
- Claude API: https://docs.anthropic.com/

**Reference Papers**
- DDD: Eric Evans "Domain-Driven Design"
- Microservices: Newman "Building Microservices"
- RAG: "Retrieval-Augmented Generation for AI" (Anthropic research)

**Community**
- GitHub Issues: https://github.com/langchain-ai/langchain/discussions
- Anthropic Slack: https://discord.gg/anthropic
- FastAPI Slack: https://discord.gg/fastapi

---

## Final Checklist Before Capstone

- [ ] All agents pass unit tests (100% coverage)
- [ ] End-to-end migration completes successfully (live demo ready)
- [ ] Shadow testing achieves 100% functional parity
- [ ] HITL dashboard fully functional (approvals, feedback)
- [ ] Security scanning (Bandit) passes with 0 HIGH issues
- [ ] Knowledge base indexed and retrieving properly (NDCG@5 ≥ 0.80)
- [ ] Cost analysis & ROI calculations complete
- [ ] All documentation written & reviewed
- [ ] Capstone slides prepared (15-20 slides)
- [ ] Runbook for deployment created
- [ ] Team training completed (everyone can operate the system)

---

**Remember**: This is an ambitious project, but the payoff is enormous. A successful implementation will save enterprises hundreds of thousands of dollars and restore developer productivity. Focus on delivering a solid end-to-end prototype that *works reliably* rather than trying to support every edge case.

**Key Success Factor**: The HITL dashboard. Make it obvious, intuitive, and non-intrusive. Humans should enjoy using it, not dread opening it.

Good luck! 🚀

