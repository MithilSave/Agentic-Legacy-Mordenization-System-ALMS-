# Codebase Explanation Guide

Welcome to the Architecture Migration Assistant! This document explains the entire project structure, what each file does, and the most important functions inside them. It will help you understand exactly how the AI agents work together to migrate a monolithic app into microservices.

---

## 1. The Core Infrastructure (`core/`)
These files handle the fundamental configuration and state management of the application.

### `core/config.py`
- **What it does**: Reads your settings (like which LLM model to use, RAG thresholds, agent temperatures) and provides them to the rest of the app. It acts as the "Source of Truth" for configuration.
- **Important Functions**: 
  - `Config._load_config()`: Automatically looks for a `config.yaml` file to load custom settings; otherwise, it falls back to sensible defaults.
  - `Config.get_agent_config(agent_name)`: Returns specific settings (like context window size) for a given agent.

### `core/constants.py`
- **What it does**: Defines the **Pydantic Schemas** (data contracts) and **System Prompts** for all the agents. This is crucial because it forces the AI to reply in a strict JSON format instead of unstructured text.
- **Important Classes/Schemas**:
  - `AnalyzerOutput`: What the Analyzer agent returns (nodes, edges, hotspots).
  - `ArchitectOutput`: What the Architect agent returns (proposed microservices and their endpoints).
  - `RefactoringOutput`: The generated Python code files from the Refactoring agent.
  - `PipelineState`: The "brain" of the Orchestrator, storing the current step and data as it gets passed between agents.

### `core/orchestrator.py`
- **What it does**: The master controller. It builds and executes a **LangGraph** `StateGraph` that runs the entire pipeline step-by-step (`Analyze → Architect → Refactor → TestGen`). It handles conditional routing, Human-in-the-Loop (HITL) checkpoints where it pauses for your approval, and cyclic loops (if you reject a proposal, it routes the graph back to the agent to try again).
- **Important Functions**:
  - `PipelineOrchestrator._build_graph()`: Constructs the LangGraph nodes, edges, and conditional routing logic.
  - `PipelineOrchestrator.run()`: Starts the LangGraph execution using `graph.invoke()`.

---

## 2. The AI Agents (`agents/`)
These are the specialized AI components, each responsible for a specific phase of the migration.

### `agents/analyzer_agent.py`
- **What it does**: Parses the legacy code into an Abstract Syntax Tree (AST), finds out which functions call which other functions, builds a dependency graph, and finds "coupling hotspots" (code that is too tangled).
- **Important Functions**:
  - `AnalyzerAgent.analyze()`: The main method. It calls the code parsing tools, fetches RAG context, and asks the LLM for deep insights.

### `agents/architect_agent.py`
- **What it does**: Takes the dependency graph from the Analyzer and groups related code together into "communities" (using the Louvain clustering algorithm). It then proposes Domain-Driven Design (DDD) microservices based on those groups.
- **Important Functions**:
  - `ArchitectAgent.design_architecture()`: Uses clustering and the LLM to output a list of proposed Microservices (like User Management or Order Processing).

### `agents/refactoring_agent.py`
- **What it does**: The code generator. It takes a proposed microservice and generates brand new **FastAPI** code, Pydantic schemas, and SQLAlchemy models from the legacy monolithic code.
- **Important Functions**:
  - `RefactoringAgent.refactor_service()`: Generates the actual Python files. It uses a 6,000-token context window so it can see all the original code.

### `agents/test_gen_agent.py`
- **What it does**: Writes automated tests (`pytest`) for the newly generated FastAPI code.
- **Important Functions**:
  - `TestGenAgent.generate_tests()`: Asks the LLM to write unit tests, integration tests, and shadow parity tests to make sure the new code acts exactly like the old code.

---

## 3. RAG System (`rag/` & `knowledge_base/`)
Retrieval-Augmented Generation (RAG) is how the AI "reads" best-practices during the migration.

### `rag/knowledge_base.py`
- **What it does**: Reads all the `.md` documents from the `knowledge_base/` folder, chunks them semantically (by headers/sections rather than random word counts), and prepares them for the database.
- **Important Functions**:
  - `KnowledgeBase.load_and_index()`: Scans the markdown files and inserts them into ChromaDB.

### `rag/vector_store.py`
- **What it does**: Manages the local `ChromaDB` instance. It uses Ollama's `nomic-embed-text` to turn text into embeddings (numbers) and stores them so the AI can search for them later.
- **Important Functions**:
  - `VectorStore.add_documents()`: Adds chunks to the DB.
  - `VectorStore.query()`: Searches the database for the most relevant design patterns based on the agent's current task.

### `rag/retriever.py`
- **What it does**: The bridge between the Agents and the Vector Store. It ensures each agent only gets the context it needs (e.g., the Architect only gets DDD patterns, not FastAPI routing patterns).

---

## 4. The Tools (`tools/`)
Helper scripts used by the agents to perform deterministic (non-AI) actions.

### `tools/code_analysis.py`
- **What it does**: Uses Python's built-in `ast` library to read code without executing it. It builds a `NetworkX` graph of how modules connect.
- **Important Functions**:
  - `extract_code_structure()`: Scans files to list all functions, classes, and imports.
  - `build_dependency_graph()`: Connects the dots to show which function calls what.

### `tools/code_generation.py`
- **What it does**: Formats the code generated by the LLM. It applies `black` and `isort` for styling and runs `py_compile` to catch syntax errors before saving.
- **Important Functions**:
  - `format_code()`: Makes the generated code look professional.
  - `validate_syntax()`: Ensures the generated code doesn't have blatant Python syntax errors.

### `tools/testing.py`
- **What it does**: The Shadow Testing Engine. It compares the JSON output of the old monolith with the new FastAPI microservice to ensure they return the exact same data.
- **Important Functions**:
  - `ShadowTestingEngine.run_shadow_tests()`: Compares old vs. new function outputs.

---

## 5. Storage & Safety (`storage/` & `safety/`)

### `storage/audit_logger.py`
- **What it does**: Connects to a local SQLite database to log every single action the agents take, how long it took, and what you (the human) decided at the HITL checkpoints. Useful for the final Capstone demo report.

### `storage/cache.py`
- **What it does**: Saves LLM responses to your hard drive (`DiskCache`) based on the hash of your code. This prevents the AI from re-running expensive, 5-minute inferences if your code hasn't changed.

### `safety/validator.py`
- **What it does**: Optional security checker. It runs `bandit` over the generated code to make sure the LLM didn't write SQL-injection vulnerabilities.

---

## 6. User Interface (`ui/dashboard.py` & `main.py`)

### `ui/dashboard.py`
- **What it does**: The "DOS-style" retro terminal interface. It uses the `rich` library to draw the cool green-on-black ASCII art, progress bars, and data tables.
- **Important Functions**:
  - `DOSDashboard.handle_event()`: Listens for updates from the Orchestrator and prints them nicely to the screen.
  - `DOSDashboard._on_hitl_checkpoint()`: The function that pauses the screen and asks you to type `y` or `n`.

### `main.py`
- **What it does**: The entry point. It's the file you actually run from the terminal (`python main.py --demo`). It wires all the above components together and starts the Orchestrator.

---

## 7. The Sample Monolith (`examples/sample_monolith/`)
- **What it is**: A deliberately messy, tightly-coupled Flask application simulating real-world legacy code. It is what the Agents analyze and attempt to break apart. It contains typical bad practices (like `database.py` global connections and `users`/`orders`/`payments` heavily importing each other) so the AI has something challenging to fix.
