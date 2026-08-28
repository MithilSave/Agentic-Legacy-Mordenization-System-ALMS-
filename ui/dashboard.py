"""
UI — DOS-Style Terminal Dashboard
====================================
Retro DOS-style terminal interface using the Rich library.
Green-on-black text, ASCII art, typewriter effects,
box-drawn panels, progress bars, and real-time agent output.

This gives the capstone demo a distinctive, memorable look.
"""

import time
import sys
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.rule import Rule
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.tree import Tree

logger = logging.getLogger("ui.dashboard")


# ══════════════════════════════════════════════
#  ASCII ART BANNER
# ══════════════════════════════════════════════

BANNER = r"""
[bold bright_green]
     █████╗  ██╗     ███╗   ███╗███████╗ 
    ██╔══██╗ ██║     ████╗ ████║██╔════╝ 
    ███████║ ██║     ██╔████╔██║███████╗ 
    ██╔══██║ ██║     ██║╚██╔╝██║╚════██║ 
    ██║  ██║ ███████╗██║ ╚═╝ ██║███████║ 
    ╚═╝  ╚═╝ ╚══════╝╚═╝     ╚═╝╚══════╝ 
                                                                 
 T H E   A G E N T I C   L E G A C Y   M O D E R N I Z A T I O N   S Y S T E M
                                                                 
          ┌─────────────────────────────────────────┐            
          │  Monolith → Microservices  │  v1.0.0    │            
          │  Powered by Qwen2.5-coder:14b via Ollama│            
          │  ChromaDB RAG │ NetworkX │ DiskCache    │            
          └─────────────────────────────────────────┘            
[/bold bright_green]"""


PIPELINE_DIAGRAM = """
[bright_green]
  ┌──────────┐    ┌──────────┐    ┌──────┐    ┌──────────┐    ┌──────────┐    ┌──────┐
  │ ANALYZER │──▶│ARCHITECT │───▶│ HITL │───▶│REFACTOR  │──▶│ TEST-GEN │──▶│ HITL │
  │   Agent  │    │  Agent   │    │ Gate │    │  Agent   │    │  Agent   │    │ Gate │
  └──────────┘    └──────────┘    └──────┘    └──────────┘    └──────────┘    └──────┘
       {s1}             {s2}           {s3}          {s4}             {s5}          {s6}
[/bright_green]"""


# ══════════════════════════════════════════════
#  DOS DASHBOARD
# ══════════════════════════════════════════════

class DOSDashboard:
    """DOS-style terminal UI for the Architecture Migration Assistant.

    Features:
    - Green-on-black retro aesthetic
    - ASCII art banner and pipeline diagram
    - Typewriter-style text output
    - Box-drawn panels for agent status
    - Real-time progress bars
    - Color-coded severity indicators
    - CLI HITL approval gates
    """

    def __init__(self):
        self.console = Console(
            force_terminal=True,
            color_system="truecolor",
            width=100,
        )
        self.events: List[Dict] = []
        self.start_time = None
        self.current_phase = ""

        # Phase status tracking
        self.phase_status = {
            "analyzing": "⬜",
            "hitl_0": "⬜",
            "architecting": "⬜",
            "hitl_1": "⬜",
            "refactoring": "⬜",
            "testing": "⬜",
            "hitl_2": "⬜",
        }

    def show_banner(self):
        """Display the ASCII art banner with typewriter effect."""
        self.console.clear()
        panel = Panel(
            Align.center(BANNER.strip('\n')),
            border_style="bold bright_green",
            padding=(1, 4),
            expand=False
        )
        self.console.print(Align.center(panel))
        self.console.print()
        time.sleep(0.5)

        # System info bar
        self._typewrite("[bright_green]  ╔══════════════════════════════════════════════════════════════╗")
        self._typewrite(f"  ║  System initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}             ║")
        self._typewrite("  ║  Model: qwen2.5-coder:7b │ Embeddings: nomic-embed-text    ║")
        self._typewrite("  ║  Vector DB: ChromaDB │ Cache: DiskCache │ Graph: NetworkX   ║")
        self._typewrite("  ╚══════════════════════════════════════════════════════════════╝")
        self.console.print()

    def show_pipeline(self):
        """Display the pipeline diagram with current status."""
        statuses = self.phase_status
        diagram = PIPELINE_DIAGRAM.format(
            s1=statuses["analyzing"],
            s2=statuses["architecting"],
            s3=statuses["hitl_1"],
            s4=statuses["refactoring"],
            s5=statuses["testing"],
            s6=statuses["hitl_2"],
        )
        self.console.print(Panel(
            diagram,
            title="[bold bright_green]═══ PIPELINE STATUS ═══[/]",
            border_style="bright_green",
            padding=(0, 1),
        ))

    def handle_event(self, event: str, data: Dict[str, Any]) -> Any:
        """Handle pipeline events — this is the UI callback.

        Returns response data for HITL checkpoints.
        """
        self.events.append({"event": event, "data": data, "time": datetime.now()})

        if event == "pipeline_start":
            self._on_pipeline_start(data)
        elif event == "phase_start":
            self._on_phase_start(data)
        elif event == "phase_complete":
            self._on_phase_complete(data)
        elif event == "hitl_checkpoint":
            return self._on_hitl_checkpoint(data)
        elif event == "refactoring_service":
            self._on_refactoring_service(data)
        elif event == "pipeline_complete":
            self._on_pipeline_complete(data)
        elif event == "pipeline_error":
            self._on_pipeline_error(data)
        elif event == "pipeline_rejected":
            self._on_pipeline_rejected(data)

        return None

    # ──────────────────────────────────────────────
    # Event Handlers
    # ──────────────────────────────────────────────

    def _on_pipeline_start(self, data: Dict):
        """Handle pipeline start event."""
        self.start_time = time.time()

        self.console.print(Rule("[bold bright_green]PIPELINE EXECUTION[/]", style="bright_green"))
        self.console.print()

        # Project info table
        table = Table(
            show_header=False,
            border_style="bright_green",
            box=None,
            padding=(0, 2),
        )
        table.add_column("Key", style="bright_green bold")
        table.add_column("Value", style="bright_white")

        table.add_row("Project ID", data.get("project_id", "unknown"))
        table.add_row("Source Path", data.get("source_path", "unknown"))
        table.add_row("Source Files", str(data.get("files", 0)))
        table.add_row("Started At", datetime.now().strftime("%H:%M:%S"))

        self.console.print(Panel(
            table,
            title="[bold bright_green]PROJECT INFO[/]",
            border_style="bright_green",
        ))
        self.console.print()

    def _on_phase_start(self, data: Dict):
        """Handle phase start event."""
        phase = data.get("phase", "unknown")
        agent = data.get("agent", "Unknown Agent")
        self.current_phase = phase

        # Update status
        phase_key = phase
        if phase_key in self.phase_status:
            self.phase_status[phase_key] = "🔄"

        self.console.print()
        self.console.print(f"[bold bright_green]{'═' * 60}[/]")
        self.console.print(f"[bold bright_green]  ▶ {agent.upper()} AGENT — {phase.upper()} PHASE[/]")
        self.console.print(f"[bold bright_green]{'═' * 60}[/]")

        # Spinning animation
        self._typewrite(f"  [bright_green]Initializing {agent} agent...[/]", delay=0.02)
        self._typewrite(f"  [bright_green]Loading model configuration (num_ctx, temperature)...[/]", delay=0.02)
        self._typewrite(f"  [bright_green]Querying RAG knowledge base...[/]", delay=0.02)
        self.console.print()

    def _on_phase_complete(self, data: Dict):
        """Handle phase completion event."""
        phase = data.get("phase", "unknown")
        duration = data.get("duration_ms", 0)

        # Update status
        if phase in self.phase_status:
            self.phase_status[phase] = "✅"

        # Results summary
        results_table = Table(
            show_header=False,
            border_style="bright_green",
            box=None,
            padding=(0, 2),
        )
        results_table.add_column("Metric", style="bright_green")
        results_table.add_column("Value", style="bold bright_white")

        results_table.add_row("Duration", f"{duration / 1000:.1f}s")

        if phase == "analyzing":
            results_table.add_row("Nodes", str(data.get("nodes", 0)))
            results_table.add_row("Edges", str(data.get("edges", 0)))
            results_table.add_row("Hotspots", str(data.get("hotspots", 0)))
        elif phase == "architecting":
            results_table.add_row("Services Proposed", str(data.get("services", 0)))
        elif phase == "refactoring":
            results_table.add_row("Services Generated", str(data.get("services_generated", 0)))
        elif phase == "testing":
            results_table.add_row("Tests Generated", str(data.get("tests_generated", 0)))

        results_table.add_row("Status", "[bold bright_green]✓ COMPLETE[/]")

        self.console.print(Panel(
            results_table,
            title=f"[bold bright_green]{phase.upper()} — RESULTS[/]",
            border_style="bright_green",
        ))

    def _on_refactoring_service(self, data: Dict):
        """Handle individual service refactoring progress."""
        service = data.get("service", "unknown")
        index = data.get("index", 0)
        total = data.get("total", 0)

        self._typewrite(
            f"  [bright_green]▸ Generating service [{index}/{total}]: "
            f"[bold bright_white]{service}[/][/]",
            delay=0.01,
        )

    def _on_hitl_checkpoint(self, data: Dict) -> Dict:
        """Handle HITL approval checkpoint — interactive CLI gate."""
        checkpoint = data.get("checkpoint", "unknown")

        # Update status
        if "analyze" in checkpoint:
            self.phase_status["hitl_0"] = "⏸️"
        elif "architect" in checkpoint:
            self.phase_status["hitl_1"] = "⏸️"
        elif "test_gen" in checkpoint:
            self.phase_status["hitl_2"] = "⏸️"

        self.console.print()
        self.console.print(Panel(
            Align.center(Text.from_markup(
                f"[bold bright_yellow]⚠ HUMAN APPROVAL REQUIRED ⚠\n\n"
                f"Checkpoint: [bright_white]{checkpoint}[/]\n\n"
                f"Review the output above and decide whether to proceed.\n"
                f"Type [bold]'y'[/] to approve or [bold]'n'[/] to reject.[/]"
            )),
            border_style="bright_yellow",
            title="[bold bright_yellow]═══ HITL CHECKPOINT ═══[/]",
            padding=(1, 2),
        ))

        # Get user input
        self.console.print()
        response = self.console.input("[bold bright_yellow]  ▸ Approve? (y/n): [/]").strip().lower()
        approved = response in ("y", "yes", "")

        feedback = ""
        if not approved:
            feedback = self.console.input("[bold bright_yellow]  ▸ Feedback: [/]").strip()

        # Update status
        if "analyze" in checkpoint:
            status_key = "hitl_0"
        elif "architect" in checkpoint:
            status_key = "hitl_1"
        else:
            status_key = "hitl_2"
        self.phase_status[status_key] = "✅" if approved else "❌"

        self.console.print(
            f"  [{'bright_green' if approved else 'bright_red'}]"
            f"{'✓ APPROVED' if approved else '✗ REJECTED'}"
            f"[/]"
        )

        return {"approved": approved, "feedback": feedback}

    def _on_pipeline_complete(self, data: Dict):
        """Handle pipeline completion."""
        elapsed = time.time() - self.start_time if self.start_time else 0

        self.console.print()
        
        content = Text.from_markup(
            f"[bold bright_green]"
            f"Services Generated: {data.get('services', 0)}\n"
            f"Tests Generated:    {data.get('tests', 0)}\n"
            f"Total Time:         {elapsed:.1f}s"
            f"[/]"
        )
        
        panel = Panel(
            Align.center(content),
            title="[bold white]✅ MIGRATION PIPELINE COMPLETE ✅",
            border_style="bold bright_green",
            padding=(1, 4),
            expand=False
        )
        
        self.console.print(Align.center(panel))

        # Show final pipeline diagram
        self.show_pipeline()

    def _on_pipeline_error(self, data: Dict):
        """Handle pipeline error."""
        error = data.get("error", "Unknown error")
        self.console.print()
        self.console.print(Panel(
            f"[bold bright_red]✗ PIPELINE FAILED\n\n{error}[/]",
            border_style="bright_red",
            title="[bold bright_red]ERROR[/]",
        ))

    def _on_pipeline_rejected(self, data: Dict):
        """Handle pipeline rejection at HITL."""
        checkpoint = data.get("checkpoint", "unknown")
        self.console.print(Panel(
            f"[bold bright_yellow]Pipeline stopped at checkpoint: {checkpoint}\n"
            f"Human reviewer requested changes.[/]",
            border_style="bright_yellow",
            title="[bold bright_yellow]REJECTED[/]",
        ))

    # ──────────────────────────────────────────────
    # Display Helpers
    # ──────────────────────────────────────────────

    def show_analyzer_results(self, output):
        """Display detailed Analyzer results."""
        self.console.print()
        self.console.print(Rule("[bold bright_green]ANALYZER RESULTS[/]", style="bright_green"))

        # Stats
        stats = output.codebase_stats
        table = Table(title="Codebase Statistics", border_style="bright_green")
        table.add_column("Metric", style="bright_green")
        table.add_column("Value", style="bold bright_white", justify="right")

        table.add_row("Total Files", str(stats.total_files))
        table.add_row("Total Lines", str(stats.total_lines))
        table.add_row("Functions", str(stats.total_functions))
        table.add_row("Classes", str(stats.total_classes))
        table.add_row("Avg Complexity", f"{stats.cyclomatic_complexity_avg:.1f}")

        self.console.print(table)

        # Hotspots
        if output.hotspots:
            self.console.print()
            hs_table = Table(title="Coupling Hotspots", border_style="bright_red")
            hs_table.add_column("Module", style="bright_white")
            hs_table.add_column("Severity", style="bright_red")
            hs_table.add_column("Coupled To", style="bright_yellow")
            hs_table.add_column("Reason", style="dim")

            for hs in output.hotspots:
                severity_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}.get(hs.severity.value, "white")
                hs_table.add_row(
                    hs.module,
                    f"[bold {severity_color}]█ {hs.severity.value}[/]",
                    ", ".join(hs.coupled_to[:3]),
                    hs.reason[:50],
                )

            self.console.print(hs_table)

        # Circular dependencies
        if output.circular_dependencies:
            self.console.print()
            self.console.print(
                f"[bold bright_red]  ⚠ {len(output.circular_dependencies)} "
                f"circular dependencies detected![/]"
            )
            for cd in output.circular_dependencies[:3]:
                cycle = cd.get("cycle", [])
                self.console.print(f"    [bright_red]↻ {' → '.join(str(c) for c in cycle)}[/]")

    def show_architect_results(self, output):
        """Display detailed Architect results."""
        self.console.print()
        self.console.print(Rule("[bold bright_green]ARCHITECTURE PROPOSAL[/]", style="bright_green"))

        for svc in output.proposed_services:
            # Service card
            conf_color = "bright_green" if svc.confidence_score >= 0.85 else "bright_yellow" if svc.confidence_score >= 0.7 else "bright_red"

            tree = Tree(f"[bold bright_white]{svc.name}[/] "
                        f"[{conf_color}]({svc.confidence_score:.0%} confidence)[/]")
            tree.add(f"[bright_green]Context:[/] {svc.bounded_context}")
            tree.add(f"[bright_green]Modules:[/] {', '.join(svc.modules)}")

            if svc.tables:
                tree.add(f"[bright_green]Tables:[/] {', '.join(svc.tables)}")

            if svc.endpoints:
                ep_branch = tree.add("[bright_green]Endpoints:[/]")
                for ep in svc.endpoints:
                    ep_branch.add(f"{', '.join(ep.methods)} {ep.path}")

            if svc.inter_service_calls:
                dep_branch = tree.add("[bright_green]Dependencies:[/]")
                for call in svc.inter_service_calls:
                    dep_branch.add(f"→ {call.calls} ({call.pattern})")

            if svc.reason:
                tree.add(f"[dim]{svc.reason}[/]")

            self.console.print(Panel(tree, border_style="bright_green"))

    def show_refactoring_results(self, outputs):
        """Display Refactoring Agent results."""
        self.console.print()
        self.console.print(Rule("[bold bright_green]GENERATED SERVICES[/]", style="bright_green"))

        for output in outputs:
            table = Table(
                title=f"Service: {output.service_name}",
                border_style="bright_green",
            )
            table.add_column("File", style="bright_white")
            table.add_column("Lines", style="bright_green", justify="right")
            table.add_column("Type", style="dim")

            for f in output.files:
                lines = f.content.count("\n") + 1
                table.add_row(f.filename, str(lines), f.file_type)

            table.add_row(
                "",
                f"[bold]py_compile: {'✓' if output.py_compile_passed else '✗'}[/]",
                "",
            )

            self.console.print(table)

            # Show first few lines of generated code
            if output.files:
                preview = output.files[0].content[:500]
                self.console.print(Panel(
                    Syntax(preview, "python", theme="monokai", line_numbers=True),
                    title=f"[dim]{output.files[0].filename} (preview)[/]",
                    border_style="dim",
                ))

    def show_test_results(self, output):
        """Display Test-Gen Agent results."""
        self.console.print()
        self.console.print(Rule("[bold bright_green]TEST SUITE[/]", style="bright_green"))

        table = Table(border_style="bright_green")
        table.add_column("#", style="dim", justify="right")
        table.add_column("Test Name", style="bright_white")
        table.add_column("Type", style="bright_green")

        for i, tc in enumerate(output.test_cases, 1):
            type_color = {
                "unit": "bright_green",
                "integration": "bright_blue",
                "shadow": "bright_yellow",
                "property": "bright_magenta",
            }.get(tc.test_type, "white")
            table.add_row(str(i), tc.name, f"[{type_color}]{tc.test_type}[/]")

        self.console.print(table)
        self.console.print(
            f"\n  [bright_green]Total Tests: {output.total_tests} │ "
            f"Coverage Target: {output.coverage_target}%[/]"
        )

    # ──────────────────────────────────────────────
    # Typewriter Effect
    # ──────────────────────────────────────────────

    def _typewrite(self, text: str, delay: float = 0.01):
        """Print text with a typewriter effect."""
        self.console.print(text)
        time.sleep(delay)

    def show_loading(self, message: str = "Processing"):
        """Show a loading spinner."""
        with Progress(
            SpinnerColumn(style="bright_green"),
            TextColumn("[bright_green]{task.description}[/]"),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            progress.add_task(description=message, total=None)
            time.sleep(1)

    def show_kb_stats(self, stats: Dict):
        """Display knowledge base statistics."""
        table = Table(
            title="Knowledge Base",
            border_style="bright_green",
        )
        table.add_column("Category", style="bright_green")
        table.add_column("Documents", style="bold bright_white", justify="right")

        for category, count in stats.items():
            table.add_row(category, str(count))

        self.console.print(table)
