"""Start only the CDC local recording instance; no upload or remote mutation."""
from pathlib import Path
import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[2]
SERVER = REPO / "server"
DEFAULT_RUNTIME = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "CDC-Food/local-demo"
PYTHON = SERVER / ".venv/Scripts/python.exe"
PORT = 18121
ORIGINAL_SURVEY_TYPES = frozenset({
    "weight_visit_registration", "weight_basic_info", "weight_clinic_first",
    "weight_anti_obesity", "weight_clinic_follow",
})


def _windows_arguments(command_line):
    """Parse Windows quoting without executing or printing a process command."""
    import ctypes
    from ctypes import wintypes

    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    arguments = parse(command_line, ctypes.byref(count))
    if not arguments:
        raise OSError("Unable to inspect local process arguments")
    release = ctypes.windll.kernel32.LocalFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_void_p
    try:
        return [arguments[index] for index in range(count.value)]
    finally:
        release(arguments)


def _owns_local_listener(runtime):
    """Fail closed unless this runtime's marked uvicorn owns the loopback port."""
    if os.name != "nt":
        return False
    try:
        marker_pid = int((runtime / "api.pid").read_text(encoding="ascii").strip())
        if not 0 < marker_pid < 2 ** 32:
            return False
        inspect_environment = os.environ.copy()
        inspect_environment["CDC_LOCAL_DEMO_PID"] = str(marker_pid)
        inspect_environment["CDC_LOCAL_DEMO_PORT"] = str(PORT)
        command = r"""$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$marker = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $env:CDC_LOCAL_DEMO_PID)
if ($null -eq $marker) { throw 'Marked process not found' }
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort ([int]$env:CDC_LOCAL_DEMO_PORT))
$ownership = @($listeners | ForEach-Object {
    $owner = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $_.OwningProcess)
    if ($null -eq $owner) { throw 'Listener process not found' }
    [pscustomobject]@{
        Address = $_.LocalAddress
        ProcessId = [long]$owner.ProcessId
        ParentProcessId = [long]$owner.ParentProcessId
    }
})
[pscustomobject]@{
    ProcessId = [long]$marker.ProcessId
    CommandLine = [string]$marker.CommandLine
    Listeners = $ownership
} | ConvertTo-Json -Depth 4 -Compress
"""
        executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run(
            [str(executable), "-NoProfile", "-NonInteractive", "-Command", command],
            env=inspect_environment, capture_output=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            return False
        process = json.loads(result.stdout.decode("utf-8-sig"))
        arguments = _windows_arguments(process.get("CommandLine", ""))
        if not arguments or os.path.normcase(str(Path(arguments[0]).resolve())) != os.path.normcase(str(PYTHON.resolve())):
            return False
        if arguments[1:] != ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)]:
            return False
        listeners = process.get("Listeners", [])
        return process.get("ProcessId") == marker_pid and bool(listeners) and all(
            listener.get("Address") == "127.0.0.1" and marker_pid in (
                listener.get("ProcessId"), listener.get("ParentProcessId")
            )
            for listener in listeners
        )
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        return False


def _has_original_forms():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/survey/templates", timeout=3) as response:
        templates = json.load(response)
    return isinstance(templates, list) and len(templates) == len(ORIGINAL_SURVEY_TYPES) and all(
        isinstance(template, dict) for template in templates
    ) and {template.get("type") for template in templates} == ORIGINAL_SURVEY_TYPES


def main():
    parser = argparse.ArgumentParser(description="Start the CDC recording API locally; never upload or deploy.")
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    options = parser.parse_args()
    runtime = options.runtime.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        occupied = sock.connect_ex(("127.0.0.1", PORT)) == 0
    if occupied:
        try:
            if not _owns_local_listener(runtime):
                raise ValueError("Local process ownership could not be verified")
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as response:
                healthy = json.load(response)
            if healthy.get("status") == "ok" and healthy.get("env") == "development" and _has_original_forms():
                print(f"CDC local demo already running on 127.0.0.1:{PORT}.")
                return
        except Exception:
            pass
        raise SystemExit("Local demo port is occupied; no process was changed.")

    cfg = dotenv_values(SERVER / ".env")
    env = os.environ.copy()
    for key in ("QWEN_API_KEY", "WECHAT_APPID", "WECHAT_SECRET"):
        if cfg.get(key):
            env[key] = cfg[key]
    jwt_file = runtime / "jwt.secret"
    if not jwt_file.exists():
        jwt_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    env.update(
        APP_ENV="development", APP_HOST="127.0.0.1", APP_PORT=str(PORT),
        DATABASE_URL="sqlite:///" + (runtime / "demo.sqlite3").as_posix(),
        JWT_SECRET=jwt_file.read_text(encoding="utf-8"),
        QWEN_MODEL="qwen3.8-27b",
        QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ENABLE_CLINICAL_SERVICES="false",
        APP_LOG_DIR=str(runtime / "logs"), MEDIA_STORAGE_BACKEND="local",
        MEDIA_STORAGE_DIR=str(runtime / "uploads"),
        ADMIN_BOOTSTRAP_USERNAME="", ADMIN_BOOTSTRAP_PASSWORD="",
        PYTHONIOENCODING="utf-8",
    )
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    for arguments in (["-m", "alembic", "upgrade", "head"],):
        result = subprocess.run([str(PYTHON), *arguments], cwd=SERVER, env=env,
                                capture_output=True, creationflags=flags)
        if result.returncode:
            (runtime / "initialization-error.log").write_bytes(result.stderr)
            raise SystemExit("Local database migration failed; see local initialization log.")
    marker = runtime / "seed.complete"
    if not marker.exists():
        result = subprocess.run([str(PYTHON), "-m", "app.db.init_db"], cwd=SERVER, env=env,
                                capture_output=True, creationflags=flags)
        if result.returncode:
            (runtime / "initialization-error.log").write_bytes(result.stderr)
            raise SystemExit("Local form initialization failed; see local initialization log.")
        marker.write_text("Original Word forms and development reference articles only.\n", encoding="utf-8")
    with (runtime / "api.stdout.log").open("ab") as stdout, (runtime / "api.stderr.log").open("ab") as stderr:
        process = subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=SERVER, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=flags, close_fds=True,
        )
    (runtime / "api.pid").write_text(str(process.pid), encoding="ascii")
    for _ in range(30):
        if process.poll() is not None:
            raise SystemExit("Local API exited; see api.stderr.log in the runtime directory.")
        try:
            if _has_original_forms():
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        raise SystemExit("Local API is not ready; see api.stderr.log in the runtime directory.")
    print(f"CDC local demo started, PID {process.pid}, API http://127.0.0.1:{PORT}/api/v1.")


if __name__ == "__main__":
    main()
