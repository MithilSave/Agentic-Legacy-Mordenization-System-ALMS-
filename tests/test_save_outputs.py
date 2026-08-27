"""Tests for main._save_outputs — the pipeline's on-disk artifact writer.

Intent under test: EVERY service folder referenced by the generated
docker-compose.yml must contain a runnable ``generated.py`` that defines a
module-level ``app`` (the Dockerfile always runs ``uvicorn generated:app``).
"""

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

# Load main.py as a module without executing its CLI.
_MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"
_spec = importlib.util.spec_from_file_location("capston_main", _MAIN_PATH)
main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(main)


def _file(filename, content):
    return SimpleNamespace(filename=filename, content=content)


def _unit(service_name, files=None, refactoring=True):
    ref = (
        SimpleNamespace(service_name=service_name, files=files or [])
        if refactoring
        else None
    )
    return SimpleNamespace(
        service=SimpleNamespace(name=service_name),
        refactoring_output=ref,
        test_gen_output=None,
        needs_human_review=False,
    )


def _state(units):
    return SimpleNamespace(
        analyzer_output=None,
        architect_output=None,
        service_units=units,
        project_id="test",
        source_path="src",
        current_phase=SimpleNamespace(value="complete"),
        errors=[],
        human_approvals=[],
    )


def _run(tmp_path, units):
    source = tmp_path / "sample_monolith"
    source.mkdir()
    main._save_outputs(_state(units), str(source / "code"))
    out = source / "migration_output"
    compose = yaml.safe_load((out / "docker-compose.yml").read_text())
    return out, compose


# Intent: `uvicorn generated:app` must resolve — either generated.py defines
# `app` directly, or it re-exports it from a sibling module.
_APP_RE = re.compile(
    r"^\s*app\s*=\s*FastAPI\s*\(|^\s*from\s+\S+\s+import\s+.*\bapp\b",
    re.MULTILINE,
)


def _assert_every_compose_folder_is_runnable(out, compose):
    assert compose["services"], "docker-compose.yml has no services"
    for name, cfg in compose["services"].items():
        folder = (out / cfg["build"].lstrip("./")).resolve()
        gen = folder / "generated.py"
        assert gen.exists(), f"{name}: {cfg['build']}/generated.py missing"
        assert _APP_RE.search(gen.read_text()), f"{name}: generated.py exposes no `app`"
        # Dockerfile's entrypoint must resolve
        assert "generated:app" in (folder / "Dockerfile").read_text()


def test_service_with_no_files_still_gets_runnable_generated_py(tmp_path):
    """LLM returned zero files -> folder must still boot (stub)."""
    out, compose = _run(tmp_path, [_unit("payments-request-service", files=[])])
    _assert_every_compose_folder_is_runnable(out, compose)


def test_missing_refactoring_output_still_produces_folder(tmp_path):
    out, compose = _run(tmp_path, [_unit("orphan-service", refactoring=False)])
    _assert_every_compose_folder_is_runnable(out, compose)
    assert len(compose["services"]) == 1


def test_real_generated_py_is_preserved(tmp_path):
    code = "from fastapi import FastAPI\napp = FastAPI()\n"
    out, compose = _run(
        tmp_path, [_unit("user-service", files=[_file("generated.py", code)])]
    )
    _assert_every_compose_folder_is_runnable(out, compose)
    folder = (out / "user-service").resolve()
    assert folder.joinpath("generated.py").read_text() == code  # untouched


def test_app_in_other_module_gets_shim(tmp_path):
    code = "from fastapi import FastAPI\napp = FastAPI()\n"
    out, compose = _run(
        tmp_path, [_unit("order-service", files=[_file("service_main.py", code)])]
    )
    _assert_every_compose_folder_is_runnable(out, compose)
    shim = (out / "order-service" / "generated.py").read_text()
    assert "from service_main import app" in shim


def test_stub_services_recorded_in_summary(tmp_path):
    import json

    out, _ = _run(tmp_path, [_unit("sqlite3-cursor-service", files=[])])
    summary = json.loads((out / "pipeline_summary.json").read_text())
    assert summary["stub_services"] == ["sqlite3-cursor-service"]


def test_mixed_batch_all_folders_runnable(tmp_path):
    good = "from fastapi import FastAPI\napp = FastAPI()\n"
    units = [
        _unit("user-service", files=[_file("generated.py", good)]),
        _unit("payments-request-service", files=[]),
        _unit("models-service", refactoring=False),
        _unit("order-service", files=[_file("service_main.py", good)]),
    ]
    out, compose = _run(tmp_path, units)
    _assert_every_compose_folder_is_runnable(out, compose)
    assert len(compose["services"]) == 4
