import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path

from django.conf import settings


DEFAULT_MEMORY_LIMIT = getattr(settings, "CHALLENGE_DOCKER_MEMORY", "128m")
DEFAULT_CPU_LIMIT = str(getattr(settings, "CHALLENGE_DOCKER_CPUS", "0.50"))
DEFAULT_TIMEOUT = int(getattr(settings, "CHALLENGE_EXECUTION_TIMEOUT_SECONDS", 5))
DEFAULT_IMAGE = getattr(settings, "CHALLENGE_DOCKER_IMAGE", "python:3.11-alpine")


def _runner_source():
    return textwrap.dedent(
        """
        import importlib.util
        import inspect
        import json
        import time
        import traceback
        from pathlib import Path

        def normalize_output(value):
            if value is None:
                return ""
            if isinstance(value, (list, tuple, dict)):
                return json.dumps(value, sort_keys=True)
            return str(value).strip()

        tests = json.loads(Path("tests.json").read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location("user_code", "user_code.py")
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except Exception:
            print(json.dumps({
                "verdict": "error",
                "is_correct": False,
                "execution_time": 0.0,
                "output": "",
                "error_output": traceback.format_exc(),
            }))
            raise SystemExit(0)

        solve = getattr(module, "solve", None)
        if solve is None or not callable(solve):
            print(json.dumps({
                "verdict": "error",
                "is_correct": False,
                "execution_time": 0.0,
                "output": "",
                "error_output": "Your submission must define solve(raw_input).",
            }))
            raise SystemExit(0)

        parameter_count = len(inspect.signature(solve).parameters)
        if parameter_count != 1:
            print(json.dumps({
                "verdict": "error",
                "is_correct": False,
                "execution_time": 0.0,
                "output": "",
                "error_output": "solve(raw_input) must accept exactly one argument.",
            }))
            raise SystemExit(0)

        max_execution_time = 0.0
        last_output = ""
        for test in tests:
            try:
                start = time.perf_counter()
                result = solve(test.get("input", ""))
                elapsed = time.perf_counter() - start
            except Exception:
                print(json.dumps({
                    "verdict": "error",
                    "is_correct": False,
                    "execution_time": max_execution_time,
                    "output": last_output,
                    "error_output": traceback.format_exc(),
                }))
                raise SystemExit(0)

            max_execution_time = max(max_execution_time, elapsed)
            last_output = normalize_output(result)
            expected_output = normalize_output(test.get("output", ""))
            if last_output != expected_output:
                print(json.dumps({
                    "verdict": "wrong",
                    "is_correct": False,
                    "execution_time": max_execution_time,
                    "output": last_output,
                    "error_output": "",
                }))
                raise SystemExit(0)

        print(json.dumps({
            "verdict": "correct",
            "is_correct": True,
            "execution_time": max_execution_time,
            "output": last_output,
            "error_output": "",
        }))
        """
    ).strip()


def _docker_command(temp_dir):
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        DEFAULT_MEMORY_LIMIT,
        "--cpus",
        DEFAULT_CPU_LIMIT,
        "-v",
        f"{temp_dir}:/workspace",
        "-w",
        "/workspace",
        DEFAULT_IMAGE,
        "python",
        "runner.py",
    ]


def _subprocess_command():
    return [sys.executable, "runner.py"]


def _execution_workspace_root():
    configured_root = getattr(settings, "CHALLENGE_TEMP_DIR", None)
    if configured_root:
        root = Path(configured_root)
    else:
        root = Path.cwd() / ".tmp" / "challenge-execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def execute_python_code(code, test_cases):
    if not test_cases:
        return {
            "verdict": "error",
            "is_correct": False,
            "execution_time": 0.0,
            "output": "",
            "error_output": "No fixed test cases are configured for this challenge.",
        }

    docker_enabled = getattr(settings, "CHALLENGE_USE_DOCKER", True)
    docker_available = docker_enabled and shutil.which("docker")

    workspace = _execution_workspace_root() / f"codearena-challenge-{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=False)

    try:
        (workspace / "user_code.py").write_text(code, encoding="utf-8")
        (workspace / "runner.py").write_text(_runner_source(), encoding="utf-8")
        (workspace / "tests.json").write_text(json.dumps(test_cases), encoding="utf-8")

        command = _docker_command(str(workspace)) if docker_available else _subprocess_command()
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "verdict": "error",
                "is_correct": False,
                "execution_time": float(DEFAULT_TIMEOUT),
                "output": "",
                "error_output": "Execution timed out.",
            }

        stdout = (completed.stdout or "").strip()
        if stdout:
            try:
                return json.loads(stdout.splitlines()[-1])
            except json.JSONDecodeError:
                pass

        stderr = (completed.stderr or "").strip()
        return {
            "verdict": "error",
            "is_correct": False,
            "execution_time": 0.0,
            "output": stdout,
            "error_output": stderr or "The execution runner did not return a valid result.",
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)



