"""
Core — Constants, Pydantic Schemas & Prompt Templates
======================================================
Defines the data contracts between agents and the system prompts
from AGENT_PROMPTING_GUIDE.md.

Schemas follow CONTEXT.md §9:
- AnalyzerOutput: dependency graph with nodes/edges/hotspots
- ArchitectOutput: proposed services with confidence scores
- RefactoringOutput: generated FastAPI code
- TestGenOutput: test suite with coverage metrics
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


# ══════════════════════════════════════════════
#  ENUMS
# ══════════════════════════════════════════════

class AgentPhase(str, Enum):
    INIT = "init"
    ANALYZING = "analyzing"
    ARCHITECTING = "architecting"
    REFACTORING = "refactoring"
    TESTING = "testing"
    COMPLETE = "complete"
    FAILED = "failed"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EdgeType(str, Enum):
    INTERNAL_CALL = "internal_call"
    EXTERNAL_CALL = "external_call"
    IMPORT = "import"
    INHERITANCE = "inheritance"
    DB_ACCESS = "db_access"


# ══════════════════════════════════════════════
#  ANALYZER OUTPUT SCHEMAS
# ══════════════════════════════════════════════

class CodeMetrics(BaseModel):
    """Metrics for a single code element."""
    complexity: int = Field(default=1, description="Cyclomatic complexity")
    loc: int = Field(default=0, description="Lines of code")
    parameters: int = Field(default=0, description="Number of parameters")


class GraphNode(BaseModel):
    """A node in the dependency graph (function, class, or module)."""
    id: str = Field(description="Unique identifier, e.g. 'users.authenticate'")
    type: str = Field(description="Node type: 'function', 'class', 'module', 'db_call'")
    module: str = Field(description="Source module name")
    metrics: CodeMetrics = Field(default_factory=CodeMetrics)
    docstring: Optional[str] = None


class GraphEdge(BaseModel):
    """An edge in the dependency graph (call, import, or inheritance)."""
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    type: EdgeType = Field(default=EdgeType.INTERNAL_CALL)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    library: Optional[str] = Field(default=None, description="External library name")


class CouplingHotspot(BaseModel):
    """A module with high coupling to other modules."""
    module: str
    coupled_to: List[str] = Field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    reason: str = ""


class CodebaseStats(BaseModel):
    """High-level statistics about the analyzed codebase."""
    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    languages: List[str] = Field(default_factory=lambda: ["python"])
    cyclomatic_complexity_avg: float = 0.0


class AnalyzerOutput(BaseModel):
    """Complete output from the Analyzer Agent.

    Validated via Pydantic — zero tokens, deterministic.
    Per CONTEXT.md §15: LLM validating LLM output is an anti-pattern.
    """
    codebase_stats: CodebaseStats = Field(default_factory=CodebaseStats)
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    hotspots: List[CouplingHotspot] = Field(default_factory=list)
    external_dependencies: List[str] = Field(default_factory=list)
    circular_dependencies: List[Dict[str, Any]] = Field(default_factory=list)


# ══════════════════════════════════════════════
#  ARCHITECT OUTPUT SCHEMAS
# ══════════════════════════════════════════════

class ServiceEndpoint(BaseModel):
    """An API endpoint for a proposed service."""
    path: str
    methods: List[str] = Field(default_factory=lambda: ["GET"])


class InterServiceCall(BaseModel):
    """A dependency between proposed services."""
    calls: str = Field(description="Target service name")
    pattern: str = Field(default="sync_rest", description="sync_rest | async_message_queue")
    frequency: str = Field(default="medium", description="low | medium | high")


class ServiceBoundary(BaseModel):
    """A proposed microservice boundary from the Architect Agent."""
    name: str = Field(description="Service name, e.g. 'user-service'")
    bounded_context: str = Field(description="DDD bounded context description")
    modules: List[str] = Field(default_factory=list, description="Source modules included")
    tables: List[str] = Field(default_factory=list, description="Database tables owned")
    endpoints: List[ServiceEndpoint] = Field(default_factory=list)
    inter_service_calls: List[InterServiceCall] = Field(default_factory=list)
    external_dependencies: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    reason: str = Field(default="", description="Why this boundary was chosen")


class ArchitectOutput(BaseModel):
    """Complete output from the Architect Agent."""
    proposed_services: List[ServiceBoundary] = Field(default_factory=list)
    inter_service_patterns: Dict[str, Any] = Field(default_factory=dict)
    data_ownership: Dict[str, Any] = Field(default_factory=dict)


# ══════════════════════════════════════════════
#  REFACTORING OUTPUT SCHEMAS
# ══════════════════════════════════════════════

class GeneratedFile(BaseModel):
    """A single generated source file."""
    filename: str
    content: str
    file_type: str = Field(default="python", description="python | yaml | sql")


class RefactoringOutput(BaseModel):
    """Complete output from the Refactoring Agent."""
    service_name: str
    files: List[GeneratedFile] = Field(default_factory=list)
    py_compile_passed: bool = False
    black_formatted: bool = False
    isort_applied: bool = False


# ══════════════════════════════════════════════
#  TEST-GEN OUTPUT SCHEMAS
# ══════════════════════════════════════════════

class TestCase(BaseModel):
    """A generated test case."""
    name: str
    test_type: str = Field(default="unit", description="unit | integration | shadow | property")
    code: str = ""


class ShadowTestResult(BaseModel):
    """Result of comparing legacy vs. new system output."""
    test_name: str
    passed: bool
    legacy_output: Optional[str] = None
    new_output: Optional[str] = None
    diff: Optional[str] = None


class TestGenOutput(BaseModel):
    """Complete output from the Test-Gen Agent."""
    service_name: str
    test_cases: List[TestCase] = Field(default_factory=list)
    shadow_results: List[ShadowTestResult] = Field(default_factory=list)
    coverage_target: float = 85.0
    total_tests: int = 0
    passed_tests: int = 0


# ══════════════════════════════════════════════
#  ORCHESTRATOR STATE
# ══════════════════════════════════════════════

class ServiceUnit(BaseModel):
    """Tracks one proposed microservice through refactor -> validate -> test.

    Replaces the old flat `refactoring_outputs` list / single `test_gen_output`
    field so every proposed service (not just the first) carries its own
    refactor output, test output, and retry state through the graph.
    """
    service: ServiceBoundary
    refactoring_output: Optional[RefactoringOutput] = None
    test_gen_output: Optional[TestGenOutput] = None
    compile_attempts: int = 0
    needs_human_review: bool = False
    status: str = "pending"  # pending | refactoring | validating | testing | done | failed


class PipelineState(BaseModel):
    """The stateful workflow state passed between agents.

    Matches the State dict from ARCHITECTURE_MIGRATION_IMPLEMENTATION_PLAN.md.
    """
    project_id: str = ""
    source_path: str = ""
    source_code: Dict[str, str] = Field(default_factory=dict, description="filename -> content")
    current_phase: AgentPhase = AgentPhase.INIT
    analyzer_output: Optional[AnalyzerOutput] = None
    dependency_review_approved: bool = False
    architect_output: Optional[ArchitectOutput] = None
    service_units: List[ServiceUnit] = Field(default_factory=list)
    human_approvals: List[Dict[str, Any]] = Field(default_factory=list)
    iteration_count: int = 0
    errors: List[str] = Field(default_factory=list)


# ══════════════════════════════════════════════
#  SYSTEM PROMPT TEMPLATES
#  From AGENT_PROMPTING_GUIDE.md
# ══════════════════════════════════════════════

ANALYZER_SYSTEM_PROMPT = """You are an expert software architect specializing in legacy code analysis and modernization.

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

CODEBASE STRUCTURE:
{code_structure}

Respond ONLY with valid JSON matching the expected schema. No markdown, no explanation outside the JSON."""


ARCHITECT_SYSTEM_PROMPT = """You are a Domain-Driven Design (DDD) expert specializing in microservice architecture design.

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
- Each service must have at least 1 bounded context
- No service should own tables for multiple unrelated domains
- Prefer synchronous communication within a service, async between services

REFERENCE PATTERNS:
{rag_ddd_patterns}

CURRENT DEPENDENCY GRAPH:
{dependency_graph}

Respond ONLY with valid JSON matching the expected schema. No markdown, no explanation outside the JSON."""


REFACTORING_SYSTEM_PROMPT = """You are an expert Python developer specializing in modernizing legacy code into production-ready, Docker-deployable FastAPI microservices.

Your role: Transform legacy monolithic functions and classes into FastAPI endpoints, Pydantic models, and SQLAlchemy ORM code that can run directly inside Docker containers.

RESPONSIBILITIES:
1. Convert function signatures to FastAPI route definitions
2. Generate Pydantic schemas for request/response validation
3. Create SQLAlchemy ORM models from database queries
4. Add comprehensive error handling and logging
5. Follow FastAPI and Python best practices
6. Ensure the service is container-ready (health checks, env config, CORS)

CODE QUALITY STANDARDS:
- PEP 8 compliant (validated with black, isort)
- Type hints on all functions and variables
- Docstrings for all public functions
- Comprehensive error handling (try-except, HTTPException)
- Structured logging with JSON format
- Security best practices (input validation, SQL injection prevention)

DOCKER-READY REQUIREMENTS (CRITICAL):
1. The main FastAPI app variable MUST be named `app` in a file named `main.py`
2. Include a `/health` GET endpoint that returns {{"status": "healthy", "service": "<service-name>"}} — no auth, no DB call
3. Include a `/ready` GET endpoint that verifies the database connection is alive
4. Read the database URL from environment variable: `DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")`
5. Add CORS middleware allowing all origins (configurable via env var)
6. Use `os.getenv()` for ALL configuration — never hardcode connection strings, secrets, or ports
7. Include `Base.metadata.create_all(bind=engine)` in a startup event so tables are created automatically

SQLALCHEMY ORM CONSTRAINTS:
- You MUST import `declarative_base`, `ForeignKey`, and `datetime` if defining models.
- You MUST declare `Base = declarative_base()` and ensure all ORM models inherit from `Base` (e.g. `class UserORM(Base):`).
- Use `connect_args={{"check_same_thread": False}}` when DATABASE_URL contains "sqlite".

GENERATED CODE MUST:
- Pass py_compile check
- Pass black formatting check
- Include type hints on all functions
- Maintain 100% functional parity with legacy code
- BE ENTIRELY SELF-CONTAINED! Do not import from local project files like 'database', 'models', or 'schemas' because those files will not exist. Write all database engine setup, models, and schemas directly inside the generated file.

TEMPLATE STRUCTURE for main.py:
```python
import os
import logging
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from pydantic import BaseModel, Field

# Configuration from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
SERVICE_NAME = os.getenv("SERVICE_NAME", "<service-name>")

# Database setup
engine = create_engine(DATABASE_URL, connect_args={{"check_same_thread": False}} if "sqlite" in DATABASE_URL else {{}})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ... ORM models here ...

# App setup
app = FastAPI(title=SERVICE_NAME)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def on_startup():
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
async def health():
    return {{"status": "healthy", "service": SERVICE_NAME}}

@app.get("/ready")
async def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {{"status": "ready", "database": "connected"}}
    except Exception:
        raise HTTPException(status_code=503, detail="Database not available")

# ... endpoints here ...
```

FASTAPI BEST PRACTICES REFERENCE:
{rag_fastapi_patterns}

SECURITY GUIDELINES:
{rag_security_patterns}

DOCKER & CONTAINER PATTERNS:
{rag_docker_patterns}

SERVICE DEFINITION:
{service_definition}

LEGACY CODE TO TRANSFORM:
{legacy_code}

Generate complete, runnable Python files. Each file should be self-contained and Docker-ready."""


TESTGEN_SYSTEM_PROMPT = """You are an expert QA engineer specializing in test generation and automated testing.

Your role: Generate comprehensive unit, integration, and shadow tests to ensure the refactored FastAPI services maintain 100% functional parity with legacy code.

RESPONSIBILITIES:
1. Generate pytest unit tests for each FastAPI endpoint
2. Create integration tests for service-to-service contracts
3. Design shadow tests (legacy vs. new comparison)
4. Generate test data fixtures
5. Ensure ≥85% code coverage

TEST GENERATION STRATEGY:
1. For each endpoint: generate happy path + error path tests
2. For each database query: generate CRUD operation tests
3. For each external dependency: generate mock/stub tests
4. Generate property-based tests using hypothesis

TESTING BEST PRACTICES:
- Use pytest fixtures for setup/teardown
- Mock external dependencies
- Use hypothesis for property-based testing
- Test error scenarios thoroughly
- Use descriptive test names

REFERENCE PATTERNS:
{rag_testing_patterns}

GENERATED FASTAPI SERVICE:
{generated_service_code}

LEGACY SERVICE REFERENCE:
{legacy_service_code}

Generate complete pytest test files. Each test should be self-contained and runnable."""
