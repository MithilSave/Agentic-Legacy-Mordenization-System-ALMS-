# ALMS — Switching to `qwen3-coder:30b` on a 16 GB CPU-only Laptop + Repo Fixes

## 0. The honest version first

`qwen3-coder:30b` on Ollama is a **Mixture-of-Experts** model: 30.5B total
parameters, but only **~3.3B active per token** (8 of 128 experts fire per
token). Compute-wise that's cheap — roughly a 3B-dense model's worth of
math per token, which is why people run it on CPU at all.

The catch is **memory, not compute**. The default Ollama tag is quantized
to Q4_K_M and is **~19 GB on disk**. Your laptop has 16 GB of *total* RAM,
shared with Windows/Linux itself, ChromaDB, Python, VS Code, etc. There is
no way to fit 19 GB of weights + KV-cache + OS overhead into 16 GB of RAM.

You called this "the layering method — 8 GB in RAM, rest in SSD" (I'm
reading this as "rest on SSD"). That technique exists and it's called
**mmap-based lazy paging**: llama.cpp (which Ollama wraps) memory-maps the
GGUF file instead of `read()`-ing it wholesale. Pages of the model are
pulled into RAM only when a layer/expert is actually touched, and the OS
evicts cold pages under memory pressure. **This is already Ollama's
default behavior on CPU** — you don't need to write any code for it. What
you *do* need to do is stop anything from disabling it and give the OS
enough disk-backed virtual memory to page against safely.

**What this means in practice:** it will *work*, but expect single-digit
tokens/second at best on an NVMe SSD, and potentially <1 tok/s on a
HDD or a heavily fragmented drive, because every expert-switch and every
context-window growth can trigger fresh page faults from disk. Your
current `qwen2.5-coder:7b` (fits fully in RAM) will *feel* faster for
short prompts even though `qwen3-coder:30b` is the stronger model
per-token. If the pipeline needs to stay interactive, keep reading to the
"Recommended fallback" section — a 30B model in 16 GB RAM CPU-only is
usable for offline/batch runs (leave it running overnight/during a break),
not snappy back-and-forth iteration.

---

## 1. Config changes (this is literally all the code needs)

### 1.1 `config.yaml` — change the model

```diff
 ollama:
   host: "http://localhost:11434"
-  model: "qwen2.5-coder:7b"
+  model: "qwen3-coder:30b"
   embedding_model: "nomic-embed-text"
```

### 1.2 `config.yaml` — shrink context windows to save RAM

KV-cache size scales with `num_ctx`. On a model this size and this RAM
budget, keep context windows as small as each agent can tolerate. Your
existing values are already conservative (4096–6144); I'd trim further:

```diff
 agents:
   analyzer:
-    num_ctx: 4096
+    num_ctx: 2048
     temperature: 0.05
     ...
   architect:
-    num_ctx: 4096
+    num_ctx: 2048
     temperature: 0.1
     ...
   refactoring:
-    num_ctx: 6144
+    num_ctx: 4096
     temperature: 0.2
     ...
   test_gen:
-    num_ctx: 4096
+    num_ctx: 2048
     temperature: 0.15
     ...
```

No other files need editing — `agents/*.py` all pull `num_ctx` and the
model name from `Config`/`self.agent_config`, so this propagates
everywhere automatically.

### 1.3 `core/config.py` — fix the stale fallback default

This isn't used once `config.yaml` exists, but it's what a fresh clone
falls back to if the YAML is missing, and it's misleading:

```diff
 _DEFAULT_CONFIG = {
     "ollama": {
         "host": "http://localhost:11434",
-        "model": "qwen2.5-coder:7b",
+        "model": "qwen3-coder:30b",
         "embedding_model": "nomic-embed-text",
     },
```
(Or leave it as the small model as an explicit "safe default" — your
call — just don't let it silently disagree with `config.yaml` and the
README the way it currently does.)

---

## 2. Pull the model

```bash
ollama pull qwen3-coder:30b
```

This downloads the ~19 GB Q4_K_M GGUF. Make sure you actually have ~25 GB
of *free disk space* (download + Ollama's blob store overhead), not just
19 GB.

If Q4_K_M still runs into trouble, there's a smaller/faster community
quant worth trying instead — same architecture, lower precision:

```bash
ollama pull qwen3-coder:30b-a3b-q4_K_M     # this is what "qwen3-coder:30b" points to today, ~19GB — same as above
```

There isn't currently a meaningfully smaller *official* quant of the 30B
tag on Ollama's library (Q8_0 is *larger*, 32 GB, not smaller). If you
want something that actually fits in RAM without paging, see the
fallback section below.

---

## 3. Making CPU-only + mmap paging survivable

These are OS/Ollama-level settings, not code changes — apply them before
running the pipeline.

### 3.1 Environment variables for Ollama

Set these where you start the Ollama service (or in your shell profile /
Windows env vars before `ollama serve`):

```bash
# Only ever load one model at a time — critical with 16GB RAM
OLLAMA_MAX_LOADED_MODELS=1

# Don't run multiple concurrent requests against the model —
# each parallel request needs its own KV-cache slice
OLLAMA_NUM_PARALLEL=1

# Force CPU (no discrete GPU to offload layers to anyway, but be explicit)
OLLAMA_NUM_GPU=0

# Quantize the KV-cache itself (cuts KV-cache RAM ~2-4x with small
# quality loss) — needs a reasonably recent Ollama build
OLLAMA_KV_CACHE_TYPE=q4_0

# Unload the model from RAM as soon as a pipeline stage finishes
# instead of keeping it "warm" — trades reload time for headroom,
# worth it when you're this RAM-constrained
OLLAMA_KEEP_ALIVE=30s
```

Windows (PowerShell), if you're on Windows per your `venv\Scripts\activate`
setup:
```powershell
setx OLLAMA_MAX_LOADED_MODELS 1
setx OLLAMA_NUM_PARALLEL 1
setx OLLAMA_NUM_GPU 0
setx OLLAMA_KV_CACHE_TYPE q4_0
setx OLLAMA_KEEP_ALIVE 30s
```
(Restart the terminal / Ollama service after `setx` for it to take effect.)

### 3.2 Give the OS enough virtual memory to page against

mmap paging still needs somewhere to spill anonymous allocations (KV
cache, activation buffers) that *aren't* the read-only mmap'd weights.
With only 16 GB physical RAM, increase your swap/pagefile as a safety
net so the process gets OOM-killed less often, at the cost of it getting
slow instead of crashing:

- **Windows:** System Properties → Advanced → Performance Settings →
  Advanced → Virtual Memory → set a custom size, e.g. **Initial 16384 MB /
  Maximum 32768 MB**, ideally on your fastest/SSD drive.
- **Linux:** if you don't already have a large swapfile:
  ```bash
  sudo fallocate -l 24G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```

### 3.3 Close everything else you can

Before a real run, close the browser, IDE extensions, etc. On a 16 GB
machine running a 19 GB model, every spare GB of physical RAM directly
translates into fewer disk page-faults per token, which is the single
biggest lever you have.

### 3.4 Sanity-check before running the full pipeline

```bash
ollama run qwen3-coder:30b "write a one-line python function that adds two numbers"
```
Time this. If a trivial prompt takes well over a minute, the pipeline's
`refactoring` and `test_gen` stages (which pass full function bodies, not
just structure) will be very slow — budget accordingly, or use
`--skip-hitl` and let it run unattended.

---

## 4. Recommended fallback (worth trying first)

Given true 16 GB RAM / CPU-only, before committing to `qwen3-coder:30b`
for the whole pipeline, it's worth benchmarking against models that
**actually fit in RAM without paging**:

| Model | Disk size (Q4) | Fits in 16GB RAM w/ headroom? |
|---|---|---|
| `qwen2.5-coder:7b` (current) | ~4.7 GB | Yes, comfortably |
| `qwen2.5-coder:14b` | ~9 GB | Yes, tight but workable |
| `qwen3:8b` | ~5 GB | Yes, comfortably |
| `qwen3-coder:30b` | ~19 GB | No — relies on disk paging |

A reasonable strategy: use `qwen3-coder:30b` (with the settings above)
for the `refactoring` and `test_gen` agents only — where output quality
matters most and per-run latency is less painful because you're not
iterating live — and keep `qwen2.5-coder:14b` or `qwen3:8b` for
`analyzer`/`architect`, which run more often during HITL iteration. That
would mean giving each agent its own model in config, which *does*
require a small code change (see below) since `config.yaml` currently
has one global `ollama.model` shared by all agents.

### Optional: per-agent model override (small code change)

```diff
 # config.yaml
 agents:
   analyzer:
     num_ctx: 2048
     temperature: 0.05
+    model: "qwen3:8b"          # fast, fits in RAM
     ...
   refactoring:
     num_ctx: 4096
     temperature: 0.2
+    model: "qwen3-coder:30b"   # slow, better code quality
     ...
```

```diff
 # core/config.py, inside get_agent_config()
     return {
         "num_ctx": agent_cfg.get("num_ctx", 4096),
         "temperature": agent_cfg.get("temperature", 0.1),
+        "model": agent_cfg.get("model", self.ollama_model),
         "rag_categories": agent_cfg.get("rag_categories", []),
         "rag_top_k": agent_cfg.get("rag_top_k", 3),
         "description": agent_cfg.get("description", ""),
     }
```

Then in each agent's `_call_llm`, change:
```diff
- model=self.config.ollama_model,
+ model=self.agent_config["model"],
```
This is a one-line change repeated in `agents/analyzer_agent.py`,
`architect_agent.py`, `refactoring_agent.py`, `test_gen_agent.py` (search
each file for `ollama_client.chat(` and `model=self.config.ollama_model`).

---

## 5. Other bugs / repo hygiene issues found while reading the code

These aren't related to the model swap but are worth fixing:

1. **README's "Customization" section documents a config schema that
   doesn't exist.** It shows:
   ```yaml
   models:
     llm: "llama3"
     embeddings: "nomic-embed-text"
     api_base: "http://localhost:11434"
   ```
   but the real, working schema (per `config.yaml` and `core/config.py`)
   is:
   ```yaml
   ollama:
     model: "qwen3-coder:30b"
     embedding_model: "nomic-embed-text"
     host: "http://localhost:11434"
   ```
   Anyone following the README to customize their model will silently
   fail (the app will just fall back to defaults, no error). Fix the
   README snippet to match the actual `ollama:` key.

2. **README's setup instructions tell you to `ollama pull llama3`**, but
   nothing in the codebase ever references `llama3` — the real default is
   `qwen2.5-coder:7b`. Update the setup section to pull whatever
   `config.yaml` actually points to.

3. **Committed build/runtime artifacts.** `audit.db`, `cache_db/`,
   `chroma_db/`, and every `__pycache__/*.pyc` are committed to the repo.
   These are regenerated on every run and will cause merge noise / stale
   SQLite conflicts for anyone cloning the repo. Add a `.gitignore`:
   ```gitignore
   __pycache__/
   *.pyc
   audit.db
   cache_db/
   chroma_db/
   venv/
   .venv/
   ```
   then `git rm -r --cached __pycache__ audit.db cache_db chroma_db` and
   commit.

4. **`requirements.txt` has a no-op fake dependency:**
   ```
   hashlib-additional>=1.0.0; python_version < "0"
   ```
   The environment marker `python_version < "0"` is always false, so pip
   silently skips it — harmless, but confusing for anyone reading the
   file. Just delete the line; `hashlib` is stdlib and needs no package.

---

## 6. Summary of concrete file edits

| File | Change |
|---|---|
| `config.yaml` | `ollama.model` → `qwen3-coder:30b`; lower `num_ctx` per agent |
| `core/config.py` | (optional) update fallback default model string; (optional) add per-agent `model` override support |
| `agents/*.py` | (only if doing per-agent models) swap `self.config.ollama_model` → `self.agent_config["model"]` |
| `README.md` | Fix `Customization` snippet to match real `ollama:` schema; fix `ollama pull llama3` instruction |
| `.gitignore` (new) | Ignore `__pycache__/`, `audit.db`, `cache_db/`, `chroma_db/`, venvs |
| `requirements.txt` | Remove the no-op `hashlib-additional` line |
