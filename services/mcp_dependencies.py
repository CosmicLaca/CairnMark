"""Supervise optional API processes required by enabled MCP services."""

import atexit
import os
import signal
import subprocess
import threading
from pathlib import Path


START_COMMAND_KEY = "dependency_start_command"
STOP_COMMAND_KEY = "dependency_stop_command"
STOP_TIMEOUT_SECONDS = 30
INTERRUPT_TIMEOUT_SECONDS = 10


class McpDependencyManager:
    """Start and stop only dependency processes launched by CairnMark."""

    def __init__(self, popen=None, runner=None):
        self._popen = popen or subprocess.Popen
        self._runner = runner or subprocess.run
        self._managed = {}
        self._lock = threading.RLock()

    @staticmethod
    def _command_path(settings, key):
        value = str((settings or {}).get(key) or "").strip()
        if not value:
            return None
        path = Path(value).expanduser()
        if not path.is_absolute() or not path.is_file():
            raise ValueError(f"{key} must be an existing absolute file path.")
        return path

    @staticmethod
    def _command(path):
        if os.name == "nt" and path.suffix.lower() in {".bat", ".cmd"}:
            command_processor = os.environ.get("COMSPEC", "cmd.exe")
            return [command_processor, "/d", "/s", "/c", str(path)]
        return [str(path)]

    @staticmethod
    def _popen_options(path):
        options = {
            "cwd": str(path.parent),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            options["creationflags"] = (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            options["start_new_session"] = True
        return options

    @staticmethod
    def _run_options(path):
        options = {
            "cwd": str(path.parent),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "timeout": STOP_TIMEOUT_SECONDS,
            "check": False,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        return options

    def start(self, service_name, settings):
        """Start a configured dependency and remember CairnMark owns it."""
        start_path = self._command_path(settings, START_COMMAND_KEY)
        if start_path is None:
            return False
        with self._lock:
            if service_name in self._managed:
                return True
            process = self._popen(
                self._command(start_path),
                **self._popen_options(start_path),
            )
            self._managed[service_name] = {
                "process": process,
                "settings": dict(settings or {}),
            }
        return True

    def owns(self, service_name):
        """Return whether CairnMark launched this dependency process."""
        with self._lock:
            return service_name in self._managed

    def stop(self, service_name, settings=None):
        """Stop one dependency only when CairnMark previously launched it."""
        with self._lock:
            managed = self._managed.pop(service_name, None)
        if managed is None:
            return False
        saved_settings = dict(managed["settings"])
        saved_settings.update(settings or {})
        stop_path = self._command_path(saved_settings, STOP_COMMAND_KEY)
        if stop_path is not None:
            try:
                self._runner(
                    self._command(stop_path),
                    **self._run_options(stop_path),
                )
            finally:
                self._terminate_process_tree(managed["process"])
        else:
            self._interrupt_process_tree(managed["process"])
        return True

    def _interrupt_process_tree(self, process):
        """Send a Ctrl+C-style interrupt before using forced termination."""
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGINT)
            process.wait(timeout=INTERRUPT_TIMEOUT_SECONDS)
            return
        except (
            AttributeError,
            OSError,
            ProcessLookupError,
            subprocess.TimeoutExpired,
        ):
            self._terminate_process_tree(process)

    def _terminate_process_tree(self, process):
        if process is None or process.poll() is not None:
            return
        if os.name == "nt":
            self._runner(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=STOP_TIMEOUT_SECONDS,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=INTERRUPT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return

    def shutdown(self):
        """Stop every dependency launched during this application process."""
        with self._lock:
            service_names = list(self._managed)
        for service_name in service_names:
            try:
                self.stop(service_name)
            except (OSError, subprocess.SubprocessError, ValueError):
                continue


MCP_DEPENDENCIES = McpDependencyManager()
atexit.register(MCP_DEPENDENCIES.shutdown)
