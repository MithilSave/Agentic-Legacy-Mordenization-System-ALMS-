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
    """Save pipeline outputs to files."""
    import json
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
    base_port = 8000

    # Save generated service code
    for unit in state.service_units:
        if not unit.refactoring_output:
            continue
        refactoring_output = unit.refactoring_output
        service_dir = output_dir / refactoring_output.service_name
        service_dir.mkdir(exist_ok=True)

        for gen_file in refactoring_output.files:
            file_path = service_dir / gen_file.filename
            file_path.write_text(gen_file.content, encoding="utf-8")
            
        # Add Dockerfile
        dockerfile_content = f"""FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "generated:app", "--host", "0.0.0.0", "--port", "8000"]
"""
        (service_dir / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")
        
        # Add requirements.txt
        reqs_content = "fastapi\nuvicorn\nsqlalchemy\npydantic\n"
        (service_dir / "requirements.txt").write_text(reqs_content, encoding="utf-8")
        
        # Add to docker-compose
        service_name_slug = refactoring_output.service_name.lower().replace(" ", "-")
        compose_services[service_name_slug] = {
            "build": f"./{refactoring_output.service_name}",
            "ports": [f"{base_port}:8000"],
            "restart": "always"
        }
        base_port += 1

    # Generate docker-compose.yml
    if compose_services:
        import yaml
        compose_content = {
            "version": "3.8",
            "services": compose_services
        }
        with open(output_dir / "docker-compose.yml", "w") as f:
            yaml.dump(compose_content, f, default_flow_style=False, sort_keys=False)

    # Save test suites (one per service)
    tests_dir = output_dir / "tests"
    for unit in state.service_units:
        if not unit.test_gen_output:
            continue
        tests_dir.mkdir(exist_ok=True)
        for tc in unit.test_gen_output.test_cases:
            test_file = tests_dir / f"{unit.service.name}_{tc.name}.py"
            test_file.write_text(tc.code, encoding="utf-8")

    # Save pipeline summary
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
        required = ["qwen2.5-coder:7b"]
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
