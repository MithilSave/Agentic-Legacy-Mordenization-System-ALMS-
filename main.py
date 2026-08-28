"""
Architecture Migration Assistant — Main Entry Point
=====================================================
CLI entry point that:
1. Loads configuration
2. Initializes RAG/ChromaDB knowledge base
3. Launches the DOS-style terminal UI
4. Runs the orchestrator pipeline on a codebase

Usage:
    python main.py <source_path>         # Run full pipeline
    python main.py --init-kb             # Populate knowledge base
    python main.py --demo                # Run on sample monolith
    python main.py --skip-hitl <path>    # Skip HITL gates (testing)
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Force UTF-8 encoding for standard streams (fixes cp1252 charmap error on Windows with Rich)
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(level: str = "INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy libraries
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def init_knowledge_base():
    """Initialize and populate the RAG knowledge base."""
    from core.config import Config
    from rag.knowledge_base import KnowledgeBase
    from ui.dashboard import DOSDashboard

    config = Config()
    dashboard = DOSDashboard()

    dashboard.show_banner()
    dashboard.console.print("\n[bold bright_green]  ▶ INITIALIZING KNOWLEDGE BASE[/]\n")

    kb = KnowledgeBase(config=config)
    stats = kb.load_and_index()

    if stats:
        dashboard.show_kb_stats(stats)
        total = sum(stats.values())
        dashboard.console.print(
            f"\n[bold bright_green]  ✓ Knowledge base initialized: "
            f"{total} documents indexed across {len(stats)} categories[/]\n"
        )
    else:
        dashboard.console.print(
            "[bold bright_yellow]  ⚠ No documents found in knowledge_base/ directory.\n"
            "  Make sure knowledge_base/ contains subdirectories with .md files.[/]\n"
        )

    return stats


def run_pipeline(source_path: str, skip_hitl: bool = False):
    """Run the full migration pipeline with DOS UI."""
    from core.config import Config
    from core.orchestrator import PipelineOrchestrator
    from ui.dashboard import DOSDashboard

    config = Config()
    dashboard = DOSDashboard()

    # Show banner
    dashboard.show_banner()

    # Check if knowledge base is populated
    from rag.vector_store import VectorStore
    vs = VectorStore(config)
    kb_count = vs.collection.count()
    if kb_count == 0:
        dashboard.console.print(
            "[bold bright_yellow]  ⚠ Knowledge base is empty. "
            "Run 'python main.py --init-kb' first.\n"
            "  Continuing without RAG context...[/]\n"
        )

    # Show pipeline diagram
    dashboard.show_pipeline()
    dashboard.console.print()

    # Create orchestrator with UI callback
    orchestrator = PipelineOrchestrator(
        config=config,
        ui_callback=dashboard.handle_event,
    )

    try:
        # Run the pipeline
        state = orchestrator.run(
            source_path=source_path,
            skip_hitl=skip_hitl,
        )

        # Display detailed results
        if state.analyzer_output:
            dashboard.show_analyzer_results(state.analyzer_output)

        if state.architect_output:
            dashboard.show_architect_results(state.architect_output)

        if state.service_units:
            refactoring_outputs = [u.refactoring_output for u in state.service_units if u.refactoring_output]
            if refactoring_outputs:
                dashboard.show_refactoring_results(refactoring_outputs)

            for unit in state.service_units:
                if unit.test_gen_output:
                    dashboard.show_test_results(unit.test_gen_output)

            needs_review = [u.service.name for u in state.service_units if u.needs_human_review]
            if needs_review:
                dashboard.console.print(
                    f"\n[bold bright_yellow]  ⚠ Services needing manual review "
                    f"(exceeded retry limit): {', '.join(needs_review)}[/]"
                )

        # Show errors if any
        if state.errors:
            dashboard.console.print("\n[bold bright_red]  Errors encountered:[/]")
            for err in state.errors:
                dashboard.console.print(f"  [bright_red]  • {err}[/]")

        # Save outputs
        _save_outputs(state, source_path)

        return state

    except KeyboardInterrupt:
        dashboard.console.print("\n[bold bright_yellow]  ⚠ Pipeline interrupted by user[/]")
    except Exception as e:
        dashboard.console.print(f"\n[bold bright_red]  ✗ Fatal error: {e}[/]")
        logging.getLogger("main").error(f"Fatal error: {e}", exc_info=True)
    finally:
        orchestrator.cleanup()


def _save_outputs(state, source_path: str):
    """Save pipeline outputs to files with production-ready Docker artifacts."""
    import json
    import yaml
    from datetime import datetime

    output_dir = Path(source_path).parent / "migration_output"
    output_dir.mkdir(exist_ok=True)

    # Save analyzer output
    if state.analyzer_output:
        with open(output_dir / "analyzer_output.json", "w") as f:
            json.dump(state.analyzer_output.model_dump(), f, indent=2, default=str)

    # Save architect output
    if state.architect_output:
        with open(output_dir / "architect_output.json", "w") as f:
            json.dump(state.architect_output.model_dump(), f, indent=2, default=str)

    # Initialize docker-compose structure
    compose_services = {}
    base_port = 8001
    service_names_for_gateway = []

    # ── Save generated service code ──
    for unit in state.service_units:
        if not unit.refactoring_output:
            continue
        refactoring_output = unit.refactoring_output
        service_dir = output_dir / refactoring_output.service_name
        service_dir.mkdir(exist_ok=True)

        # Ensure data directory exists for SQLite
        (service_dir / "data").mkdir(exist_ok=True)
        (service_dir / "data" / ".gitkeep").write_text("", encoding="utf-8")

        for gen_file in refactoring_output.files:
            file_path = service_dir / gen_file.filename
            file_path.write_text(gen_file.content, encoding="utf-8")

        # ── Production Dockerfile (multi-stage) ──
        service_slug = refactoring_output.service_name.lower().replace(" ", "-")
        dockerfile_content = f"""# === {refactoring_output.service_name} ===
# Multi-stage build for minimal image size

# Stage 1: Install dependencies
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create data directory for SQLite and set permissions
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check — Docker marks container unhealthy if /health fails
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Use exec form for proper signal handling (graceful shutdown)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
"""
        (service_dir / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")

        # ── requirements.txt ──
        reqs_content = """# === Auto-generated dependencies ===
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
python-dotenv>=1.0.0
httpx>=0.25.0
"""
        (service_dir / "requirements.txt").write_text(reqs_content, encoding="utf-8")

        # ── .dockerignore ──
        dockerignore_content = """__pycache__/
*.pyc
*.pyo
.git/
.env
.venv/
*.md
tests/
.pytest_cache/
.mypy_cache/
.DS_Store
"""
        (service_dir / ".dockerignore").write_text(dockerignore_content, encoding="utf-8")

        # ── .env.example ──
        env_example = f"""# === {refactoring_output.service_name} Environment Variables ===
DATABASE_URL=sqlite:///./data/app.db
SERVICE_NAME={service_slug}
LOG_LEVEL=INFO
ALLOWED_ORIGINS=*
"""
        (service_dir / ".env.example").write_text(env_example, encoding="utf-8")

        # ── Add to docker-compose ──
        service_name_slug = service_slug
        compose_services[service_name_slug] = {
            "build": {
                "context": f"./{refactoring_output.service_name}",
                "dockerfile": "Dockerfile",
            },
            "container_name": service_name_slug,
            "expose": ["8000"],
            "environment": {
                "DATABASE_URL": "sqlite:///./data/app.db",
                "SERVICE_NAME": service_name_slug,
                "LOG_LEVEL": "INFO",
            },
            "volumes": [
                f"{service_name_slug}-data:/app/data",
            ],
            "networks": ["microservices"],
            "restart": "unless-stopped",
            "healthcheck": {
                "test": ["CMD", "python", "-c",
                         "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"],
                "interval": "15s",
                "timeout": "5s",
                "retries": 3,
                "start_period": "10s",
            },
            "deploy": {
                "resources": {
                    "limits": {"memory": "256M", "cpus": "0.5"},
                    "reservations": {"memory": "128M"},
                },
            },
            "logging": {
                "driver": "json-file",
                "options": {"max-size": "10m", "max-file": "3"},
            },
        }
        service_names_for_gateway.append(service_name_slug)
        base_port += 1

    # ── Generate Nginx API Gateway ──
    if service_names_for_gateway:
        gateway_dir = output_dir / "api-gateway"
        gateway_dir.mkdir(exist_ok=True)

        # Build nginx.conf with upstream blocks and location routing
        upstream_blocks = []
        location_blocks = []
        for svc_name in service_names_for_gateway:
            upstream_blocks.append(
                f"    upstream {svc_name.replace('-', '_')} {{\n"
                f"        server {svc_name}:8000;\n"
                f"    }}"
            )
            # Derive a path prefix from the service name (e.g., user-service -> /api/users)
            path_prefix = svc_name.replace("-service", "").replace("-", "/")
            location_blocks.append(
                f"        # {svc_name}\n"
                f"        location /api/{path_prefix} {{\n"
                f"            proxy_pass http://{svc_name.replace('-', '_')};\n"
                f"            proxy_set_header Host $host;\n"
                f"            proxy_set_header X-Real-IP $remote_addr;\n"
                f"            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                f"            proxy_set_header X-Forwarded-Proto $scheme;\n"
                f"        }}"
            )

        nginx_conf = f"""# === Auto-Generated API Gateway (Nginx) ===
# Routes requests to backend microservices by path prefix

{"chr(10)".join(upstream_blocks)}

    server {{
        listen 80;
        server_name localhost;

        # Gateway health check
        location /health {{
            return 200 '{{"status": "healthy", "service": "api-gateway"}}';
            add_header Content-Type application/json;
        }}

        # Service discovery — list all available services
        location /api {{
            return 200 '{{"services": {json.dumps(service_names_for_gateway)}}}';
            add_header Content-Type application/json;
        }}

{chr(10).join(location_blocks)}

        # Default — 404
        location / {{
            return 404 '{{"error": "Not found. Use /api for service discovery."}}';
            add_header Content-Type application/json;
        }}
    }}
"""
        (gateway_dir / "nginx.conf").write_text(nginx_conf, encoding="utf-8")

        # Add gateway to docker-compose
        gateway_depends = {}
        for svc_name in service_names_for_gateway:
            gateway_depends[svc_name] = {"condition": "service_healthy"}

        compose_services["api-gateway"] = {
            "image": "nginx:alpine",
            "container_name": "api-gateway",
            "ports": ["8080:80"],
            "volumes": [
                "./api-gateway/nginx.conf:/etc/nginx/conf.d/default.conf:ro",
            ],
            "depends_on": gateway_depends,
            "networks": ["microservices"],
            "restart": "unless-stopped",
            "healthcheck": {
                "test": ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:80/health"],
                "interval": "15s",
                "timeout": "5s",
                "retries": 3,
            },
        }

    # ── Generate docker-compose.yml ──
    if compose_services:
        # Build volumes dict
        volumes_dict = {}
        for svc_name in service_names_for_gateway:
            volumes_dict[f"{svc_name}-data"] = None

        compose_content = {
            "services": compose_services,
            "networks": {
                "microservices": {
                    "driver": "bridge",
                },
            },
            "volumes": volumes_dict,
        }
        with open(output_dir / "docker-compose.yml", "w") as f:
            yaml.dump(compose_content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # ── Generate root .env ──
    env_content = """# === Environment Variables for all services ===
# Copy this to .env and adjust values for your deployment
LOG_LEVEL=INFO
ALLOWED_ORIGINS=*
"""
    (output_dir / ".env.example").write_text(env_content, encoding="utf-8")

    # ── Generate README.md ──
    svc_list = "\n".join([f"  - **{name}**" for name in service_names_for_gateway])
    readme_content = f"""# Migration Output — Microservices

> Auto-generated by Architecture Migration Assistant on {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Services Generated
{svc_list}

## Quick Start

### Prerequisites
- [Docker](https://www.docker.com/get-started) installed and running
- [Docker Compose](https://docs.docker.com/compose/) v2+

### Run All Services
```bash
# Build and start all services
docker-compose up --build

# Run in detached (background) mode
docker-compose up --build -d
```

### Access
- **API Gateway**: http://localhost:8080
- **Service Discovery**: http://localhost:8080/api
- **Health Check**: http://localhost:8080/health

### Stop All Services
```bash
docker-compose down

# Stop and remove volumes (clears all data)
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f <service-name>
```

## Project Structure
```
migration_output/
├── docker-compose.yml          # Orchestrates all services
├── .env.example                # Environment variable template
├── api-gateway/
│   └── nginx.conf              # Nginx reverse proxy config
├── <service-name>/
│   ├── main.py                 # FastAPI application
│   ├── Dockerfile              # Multi-stage production build
│   ├── requirements.txt        # Python dependencies
│   ├── .dockerignore           # Docker build exclusions
│   ├── .env.example            # Service-specific env vars
│   └── data/                   # SQLite database directory
└── tests/                      # Generated test suites
```

## Architecture
- Each service runs in its own container with an isolated SQLite database
- Services communicate through the `microservices` Docker network
- The **API Gateway** (Nginx) provides a single entry point on port 8080
- Health checks ensure services are ready before receiving traffic
- Resource limits prevent any single service from consuming all host resources
"""
    (output_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # ── Save test suites (one per service) ──
    tests_dir = output_dir / "tests"
    for unit in state.service_units:
        if not unit.test_gen_output:
            continue
        tests_dir.mkdir(exist_ok=True)
        for tc in unit.test_gen_output.test_cases:
            test_file = tests_dir / f"{unit.service.name}_{tc.name}.py"
            test_file.write_text(tc.code, encoding="utf-8")

    # ── Save pipeline summary ──
    summary = {
        "project_id": state.project_id,
        "source_path": state.source_path,
        "completed_at": datetime.now().isoformat(),
        "phase": state.current_phase.value,
        "services_generated": len(state.service_units),
        "tests_generated": sum(
            u.test_gen_output.total_tests for u in state.service_units if u.test_gen_output
        ),
        "services_needing_review": [u.service.name for u in state.service_units if u.needs_human_review],
        "errors": state.errors,
        "approvals": state.human_approvals,
    }

    with open(output_dir / "pipeline_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Outputs saved to: {output_dir}")


def check_ollama():
    """Verify Ollama is running and the model is available."""
    from ui.dashboard import DOSDashboard
    dashboard = DOSDashboard()

    try:
        import ollama as ollama_client
        models = ollama_client.list()
        model_names = [m.get("name", m.get("model", "")) for m in models.get("models", [])]

        dashboard.console.print("[bold bright_green]  ✓ Ollama connection OK[/]")
        dashboard.console.print(f"  [bright_green]  Available models: {', '.join(model_names)}[/]")

        # Check for required models
        required = ["qwen2.5-coder:14b"]
        for req in required:
            found = any(req in name for name in model_names)
            status = "✓" if found else "✗"
            color = "bright_green" if found else "bright_red"
            dashboard.console.print(f"  [{color}]  {status} {req}[/]")

        return True

    except Exception as e:
        dashboard.console.print(f"[bold bright_red]  ✗ Ollama not available: {e}[/]")
        dashboard.console.print(
            "  [bright_yellow]  Make sure Ollama is running: ollama serve[/]"
        )
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Architecture Migration Assistant — Monolith to Microservices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --demo                  Run on sample monolith
  python main.py --init-kb               Populate knowledge base
  python main.py examples/sample_monolith  Analyze a codebase
  python main.py --skip-hitl <path>      Skip HITL gates
  python main.py --check                 Check Ollama connection
        """
    )

    parser.add_argument("source", nargs="?", default=None,
                        help="Path to the legacy codebase to analyze")
    parser.add_argument("--init-kb", action="store_true",
                        help="Initialize the RAG knowledge base")
    parser.add_argument("--demo", action="store_true",
                        help="Run on the built-in sample monolith")
    parser.add_argument("--skip-hitl", action="store_true",
                        help="Skip HITL approval gates (for testing)")
    parser.add_argument("--check", action="store_true",
                        help="Check Ollama connection and model availability")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")

    args = parser.parse_args()

    setup_logging(args.log_level)

    # ── Check Ollama ──
    if args.check:
        check_ollama()
        return

    # ── Init Knowledge Base ──
    if args.init_kb:
        init_knowledge_base()
        return

    # ── Determine source path ──
    if args.demo:
        source_path = str(PROJECT_ROOT / "examples" / "sample_monolith")
    elif args.source:
        source_path = args.source
    else:
        parser.print_help()
        print("\n  Tip: Run 'python main.py --demo' to try the sample monolith.\n")
        return

    # Validate source path
    if not Path(source_path).exists():
        print(f"  Error: Source path does not exist: {source_path}")
        sys.exit(1)

    # ── Run Pipeline ──
    run_pipeline(source_path, skip_hitl=args.skip_hitl)


if __name__ == "__main__":
    main()
