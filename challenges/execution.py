import base64
import json
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

from django.conf import settings


DEFAULT_TIMEOUT = int(getattr(settings, "CHALLENGE_EXECUTION_TIMEOUT_SECONDS", 5))

LANGUAGE_TEMPLATES = {
    "python": (
        "def solve(raw_input: str) -> str:\n"
        "    lines = raw_input.strip().splitlines()\n"
        "    # Write your solution here.\n"
        "    return \"\"\n"
    ),
    "java": (
        "import java.io.BufferedReader;\n"
        "import java.io.InputStreamReader;\n"
        "import java.util.stream.Collectors;\n"
        "\n"
        "public class Main {\n"
        "    public static String solve(String rawInput) {\n"
        "        return \"\";\n"
        "    }\n"
        "\n"
        "    public static void main(String[] args) throws Exception {\n"
        "        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));\n"
        "        String rawInput = reader.lines().collect(Collectors.joining(\"\\n\"));\n"
        "        System.out.print(solve(rawInput));\n"
        "    }\n"
        "}\n"
    ),
}


def _execution_workspace_root():
    configured_root = getattr(settings, "CHALLENGE_TEMP_DIR", None)
    root = Path(configured_root) if configured_root else Path.cwd() / ".tmp" / "challenge-execution"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalize_output(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value).strip()


def _execution_result(
    *,
    language,
    verdict,
    is_correct,
    execution_time,
    passed_count,
    failed_count,
    output="",
    error_output="",
    results=None,
    supported=True,
    runner="docker",
):
    return {
        "language": language,
        "supported": supported,
        "runner": runner,
        "verdict": verdict,
        "is_correct": is_correct,
        "execution_time": execution_time,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "output": output,
        "error_output": error_output,
        "results": results or [],
    }


def _python_runner_source():
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
                "passed_count": 0,
                "failed_count": len(tests),
                "output": "",
                "error_output": traceback.format_exc(),
                "results": [],
            }))
            raise SystemExit(0)

        solve = getattr(module, "solve", None)
        if solve is None or not callable(solve):
            print(json.dumps({
                "verdict": "error",
                "is_correct": False,
                "execution_time": 0.0,
                "passed_count": 0,
                "failed_count": len(tests),
                "output": "",
                "error_output": "Your submission must define solve(raw_input).",
                "results": [],
            }))
            raise SystemExit(0)

        parameter_count = len(inspect.signature(solve).parameters)
        if parameter_count != 1:
            print(json.dumps({
                "verdict": "error",
                "is_correct": False,
                "execution_time": 0.0,
                "passed_count": 0,
                "failed_count": len(tests),
                "output": "",
                "error_output": "solve(raw_input) must accept exactly one argument.",
                "results": [],
            }))
            raise SystemExit(0)

        max_execution_time = 0.0
        results = []
        passed_count = 0
        last_output = ""
        last_error = ""

        for index, test in enumerate(tests, start=1):
            try:
                start = time.perf_counter()
                result = solve(test.get("input", ""))
                elapsed = time.perf_counter() - start
                actual_output = normalize_output(result)
                expected_output = normalize_output(test.get("expected", ""))
                passed = actual_output == expected_output
                error_output = ""
            except Exception:
                elapsed = 0.0
                actual_output = ""
                expected_output = normalize_output(test.get("expected", ""))
                passed = False
                error_output = traceback.format_exc()

            max_execution_time = max(max_execution_time, elapsed)
            last_output = actual_output
            last_error = error_output
            if passed:
                passed_count += 1

            results.append({
                "index": index,
                "input": test.get("input", ""),
                "expected_output": expected_output,
                "actual_output": actual_output,
                "passed": passed,
                "is_sample": bool(test.get("is_sample", False)),
                "execution_time": elapsed,
                "error_output": error_output,
            })

            if error_output:
                break

        failed_count = len(results) - passed_count
        verdict = "correct" if results and failed_count == 0 and len(results) == len(tests) else "wrong"
        if last_error:
            verdict = "error"

        print(json.dumps({
            "verdict": verdict,
            "is_correct": verdict == "correct",
            "execution_time": max_execution_time,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "output": last_output,
            "error_output": last_error,
            "results": results,
        }))
        """
    ).strip()


def _java_string_literal(value):
    return json.dumps(str(value)).replace("</", "<\\/")


def _java_runner_source(test_cases):
    inputs = ", ".join(_java_string_literal(case["input"]) for case in test_cases)
    expected = ", ".join(_java_string_literal(case["expected"]) for case in test_cases)
    samples = ", ".join("true" if case.get("is_sample") else "false" for case in test_cases)
    return textwrap.dedent(
        f'''
        import java.nio.charset.StandardCharsets;
        import java.util.Base64;

        public class JudgeRunner {{
            private static final String[] INPUTS = new String[] {{{inputs}}};
            private static final String[] EXPECTED = new String[] {{{expected}}};
            private static final boolean[] SAMPLES = new boolean[] {{{samples}}};

            private static String encode(String value) {{
                if (value == null) {{
                    value = "";
                }}
                return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
            }}

            private static String normalizeOutput(Object value) {{
                if (value == null) {{
                    return "";
                }}
                return String.valueOf(value).trim();
            }}

            public static void main(String[] args) {{
                StringBuilder results = new StringBuilder();
                results.append("[");
                double maxExecutionTime = 0.0;
                int passedCount = 0;
                int executedCount = 0;
                String lastOutput = "";
                String lastError = "";

                for (int index = 0; index < INPUTS.length; index++) {{
                    String actualOutput = "";
                    String expectedOutput = normalizeOutput(EXPECTED[index]);
                    String errorOutput = "";
                    boolean passed = false;
                    double elapsed = 0.0;

                    try {{
                        long start = System.nanoTime();
                        actualOutput = normalizeOutput(Main.solve(INPUTS[index]));
                        long end = System.nanoTime();
                        elapsed = (end - start) / 1_000_000_000.0;
                        passed = actualOutput.equals(expectedOutput);
                    }} catch (Throwable error) {{
                        errorOutput = error.toString();
                    }}

                    executedCount++;
                    maxExecutionTime = Math.max(maxExecutionTime, elapsed);
                    lastOutput = actualOutput;
                    lastError = errorOutput;
                    if (passed) {{
                        passedCount++;
                    }}

                    if (index > 0) {{
                        results.append("\\n");
                    }}
                    results
                        .append("CASE|")
                        .append(index + 1).append("|")
                        .append(encode(INPUTS[index])).append("|")
                        .append(encode(expectedOutput)).append("|")
                        .append(encode(actualOutput)).append("|")
                        .append(passed ? "true" : "false").append("|")
                        .append(SAMPLES[index] ? "true" : "false").append("|")
                        .append(elapsed).append("|")
                        .append(encode(errorOutput));

                    if (!errorOutput.isEmpty()) {{
                        break;
                    }}
                }}

                int failedCount = executedCount - passedCount;
                String verdict = executedCount > 0 && failedCount == 0 && executedCount == INPUTS.length ? "correct" : "wrong";
                if (!lastError.isEmpty()) {{
                    verdict = "error";
                }}

                System.out.println(
                    "SUMMARY|"
                    + verdict + "|"
                    + ("correct".equals(verdict) ? "true" : "false") + "|"
                    + maxExecutionTime + "|"
                    + passedCount + "|"
                    + failedCount + "|"
                    + encode(lastOutput) + "|"
                    + encode(lastError)
                );
                if (results.length() > 0) {{
                    System.out.println(results);
                }}
            }}
        }}
        '''
    ).strip()


def starter_code_for(language):
    return LANGUAGE_TEMPLATES.get(language, LANGUAGE_TEMPLATES["python"])


def available_language_options():
    return [
        {"value": "python", "label": "Python"},
        {"value": "java", "label": "Java"},
    ]


def serialize_test_cases(test_cases):
    serialized = []
    for test_case in test_cases or []:
        if isinstance(test_case, dict):
            serialized.append(
                {
                    "input": str(test_case.get("input", "")),
                    "expected": str(test_case.get("output", test_case.get("expected_output", ""))),
                    "is_sample": bool(test_case.get("is_public", test_case.get("is_sample", False))),
                }
            )
        else:
            serialized.append(
                {
                    "input": str(getattr(test_case, "input_data", "")),
                    "expected": str(getattr(test_case, "expected_output", "")),
                    "is_sample": bool(getattr(test_case, "is_sample", False)),
                }
            )
    return serialized


def _unsupported_language_result(language, test_cases, *, runner="local"):
    total = len(test_cases)
    message = f"{language.title()} execution is not enabled yet."
    return _execution_result(
        language=language,
        supported=False,
        runner=runner,
        verdict="error",
        is_correct=False,
        execution_time=0.0,
        passed_count=0,
        failed_count=total,
        output="",
        error_output=message,
        results=[
            {
                "index": index,
                "input": item["input"],
                "expected_output": item["expected"],
                "actual_output": "",
                "passed": False,
                "is_sample": item.get("is_sample", False),
                "execution_time": 0.0,
                "error_output": message,
            }
            for index, item in enumerate(test_cases, start=1)
        ],
    )


def _write_workspace(workspace, *, language, code, test_cases):
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / "tests.json").write_text(json.dumps(test_cases), encoding="utf-8")
    if language == "python":
        (workspace / "user_code.py").write_text(code, encoding="utf-8")
        (workspace / "runner.py").write_text(_python_runner_source(), encoding="utf-8")
    elif language == "java":
        (workspace / "Main.java").write_text(code, encoding="utf-8")
        (workspace / "JudgeRunner.java").write_text(_java_runner_source(test_cases), encoding="utf-8")


def _decode_java_field(value):
    return base64.b64decode(value.encode("utf-8")).decode("utf-8") if value else ""


def _parse_java_runner_payload(stdout, *, language, test_cases, runner):
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("SUMMARY|"):
        return _execution_result(
            language=language,
            supported=True,
            runner=runner,
            verdict="error",
            is_correct=False,
            execution_time=0.0,
            passed_count=0,
            failed_count=len(test_cases),
            output=stdout,
            error_output="The execution runner did not return a valid result.",
        )

    summary = lines[0].split("|", 7)
    if len(summary) != 8:
        return _execution_result(
            language=language,
            supported=True,
            runner=runner,
            verdict="error",
            is_correct=False,
            execution_time=0.0,
            passed_count=0,
            failed_count=len(test_cases),
            output=stdout,
            error_output="The Java execution summary was malformed.",
        )

    results = []
    for line in lines[1:]:
        if not line.startswith("CASE|"):
            continue
        parts = line.split("|", 8)
        if len(parts) != 9:
            continue
        results.append(
            {
                "index": int(parts[1]),
                "input": _decode_java_field(parts[2]),
                "expected_output": _decode_java_field(parts[3]),
                "actual_output": _decode_java_field(parts[4]),
                "passed": parts[5] == "true",
                "is_sample": parts[6] == "true",
                "execution_time": float(parts[7]),
                "error_output": _decode_java_field(parts[8]),
            }
        )

    return {
        "language": language,
        "supported": True,
        "runner": runner,
        "verdict": summary[1],
        "is_correct": summary[2] == "true",
        "execution_time": float(summary[3]),
        "passed_count": int(summary[4]),
        "failed_count": int(summary[5]),
        "output": _decode_java_field(summary[6]),
        "error_output": _decode_java_field(summary[7]),
        "results": results,
    }


def _parse_runner_payload(stdout, *, language, test_cases, runner):
    if language == "java":
        return _parse_java_runner_payload(stdout, language=language, test_cases=test_cases, runner=runner)
    if stdout:
        try:
            payload = json.loads(stdout.splitlines()[-1])
            payload["language"] = language
            payload["supported"] = True
            payload["runner"] = runner
            return payload
        except json.JSONDecodeError:
            pass

    return _execution_result(
        language=language,
        supported=True,
        runner=runner,
        verdict="error",
        is_correct=False,
        execution_time=0.0,
        passed_count=0,
        failed_count=len(test_cases),
        output=stdout,
        error_output="The execution runner did not return a valid result.",
    )


def _timeout_result(language, test_cases, timeout_seconds, *, runner):
    return _execution_result(
        language=language,
        supported=True,
        runner=runner,
        verdict="error",
        is_correct=False,
        execution_time=float(timeout_seconds),
        passed_count=0,
        failed_count=len(test_cases),
        output="",
        error_output="Execution timed out.",
    )


def _docker_mount_path(workspace):
    return str(workspace.resolve()).replace("\\", "/")


def _docker_image_for(language):
    if language == "java":
        return getattr(settings, "CHALLENGE_DOCKER_JAVA_IMAGE", getattr(settings, "CHALLENGE_DOCKER_IMAGE", "eclipse-temurin:21-jdk-alpine"))
    return getattr(settings, "CHALLENGE_DOCKER_PYTHON_IMAGE", getattr(settings, "CHALLENGE_DOCKER_IMAGE", "python:3.11-alpine"))


def _docker_command(workspace, language):
    workdir = "/workspace"
    command = ["python", "runner.py"] if language == "python" else ["sh", "-lc", "javac Main.java JudgeRunner.java && java JudgeRunner"]
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        str(getattr(settings, "CHALLENGE_DOCKER_MEMORY", "128m")),
        "--cpus",
        str(getattr(settings, "CHALLENGE_DOCKER_CPUS", "0.50")),
        "--pids-limit",
        "128",
        "-v",
        f"{_docker_mount_path(workspace)}:{workdir}",
        "-w",
        workdir,
        _docker_image_for(language),
        *command,
    ]


def _run_command(command, *, cwd, timeout_seconds):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds + 2,
        check=False,
    )


def _run_python_locally(code, test_cases, timeout_seconds):
    workspace = _execution_workspace_root() / f"codearena-py-{uuid.uuid4().hex}"
    try:
        _write_workspace(workspace, language="python", code=code, test_cases=test_cases)
        try:
            completed = _run_command([sys.executable, "runner.py"], cwd=workspace, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return _timeout_result("python", test_cases, timeout_seconds, runner="local")

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode and stderr:
            return _execution_result(
                language="python",
                supported=True,
                runner="local",
                verdict="error",
                is_correct=False,
                execution_time=0.0,
                passed_count=0,
                failed_count=len(test_cases),
                output=stdout,
                error_output=stderr,
            )
        payload = _parse_runner_payload(stdout, language="python", test_cases=test_cases, runner="local")
        if stderr and not payload.get("error_output"):
            payload["error_output"] = stderr
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _run_java_locally(code, test_cases, timeout_seconds):
    if not shutil.which("javac") or not shutil.which("java"):
        return _unsupported_language_result("java", test_cases, runner="local")

    workspace = _execution_workspace_root() / f"codearena-java-{uuid.uuid4().hex}"
    try:
        _write_workspace(workspace, language="java", code=code, test_cases=test_cases)
        try:
            compile_result = _run_command(["javac", "Main.java", "JudgeRunner.java"], cwd=workspace, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return _timeout_result("java", test_cases, timeout_seconds, runner="local")
        if compile_result.returncode != 0:
            return _execution_result(
                language="java",
                supported=True,
                runner="local",
                verdict="error",
                is_correct=False,
                execution_time=0.0,
                passed_count=0,
                failed_count=len(test_cases),
                error_output=(compile_result.stderr or compile_result.stdout or "Compilation failed.").strip(),
            )

        try:
            completed = _run_command(["java", "JudgeRunner"], cwd=workspace, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired:
            return _timeout_result("java", test_cases, timeout_seconds, runner="local")

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode and stderr:
            return _execution_result(
                language="java",
                supported=True,
                runner="local",
                verdict="error",
                is_correct=False,
                execution_time=0.0,
                passed_count=0,
                failed_count=len(test_cases),
                output=stdout,
                error_output=stderr,
            )
        payload = _parse_runner_payload(stdout, language="java", test_cases=test_cases, runner="local")
        if stderr and not payload.get("error_output"):
            payload["error_output"] = stderr
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _run_dockerized(code, language, test_cases, timeout_seconds):
    workspace = _execution_workspace_root() / f"codearena-docker-{language}-{uuid.uuid4().hex}"
    try:
        _write_workspace(workspace, language=language, code=code, test_cases=test_cases)
        try:
            completed = _run_command(_docker_command(workspace, language), cwd=workspace, timeout_seconds=timeout_seconds)
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return _timeout_result(language, test_cases, timeout_seconds, runner="docker")

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            return _execution_result(
                language=language,
                supported=True,
                runner="docker",
                verdict="error",
                is_correct=False,
                execution_time=0.0,
                passed_count=0,
                failed_count=len(test_cases),
                output=stdout,
                error_output=stderr or "Execution failed inside Docker.",
            )
        payload = _parse_runner_payload(stdout, language=language, test_cases=test_cases, runner="docker")
        if stderr and not payload.get("error_output"):
            payload["error_output"] = stderr
        return payload
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _run_locally(code, language, test_cases, timeout_seconds):
    if language == "python":
        return _run_python_locally(code, test_cases, timeout_seconds)
    if language == "java":
        return _run_java_locally(code, test_cases, timeout_seconds)
    return _unsupported_language_result(language, test_cases)


def evaluate_code(code, language, test_cases, timeout_seconds=None):
    normalized_cases = serialize_test_cases(test_cases)
    if not normalized_cases:
        return _execution_result(
            language=language,
            supported=language in {"python", "java"},
            runner="none",
            verdict="error",
            is_correct=False,
            execution_time=0.0,
            passed_count=0,
            failed_count=0,
            error_output="No test cases are configured for this problem.",
        )

    timeout = timeout_seconds or DEFAULT_TIMEOUT
    if language not in {"python", "java"}:
        return _unsupported_language_result(language, normalized_cases)

    if getattr(settings, "CHALLENGE_USE_DOCKER", True):
        docker_result = _run_dockerized(code, language, normalized_cases, timeout)
        if docker_result is not None:
            return docker_result

    return _run_locally(code, language, normalized_cases, timeout)
