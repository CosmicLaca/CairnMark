"""Daily Git update discovery and detached updater orchestration."""

import os
import re
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

from config import PROJECT_ROOT
from models.update_storage import UPDATE_STORAGE


UPDATE_REPOSITORY = "https://github.com/CosmicLaca/CairnMark.git"
UPDATE_BRANCH = "main"
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40,64}$")


class ApplicationUpdateError(RuntimeError):
    """Raised when the application cannot safely start an update."""


class ApplicationUpdateService:
    """Compare Git commits once daily and launch a safe updater process."""

    def __init__(self, storage=UPDATE_STORAGE, project_root=PROJECT_ROOT):
        self.storage = storage
        self.project_root = Path(project_root)
        self._check_lock = threading.Lock()

    @property
    def git_directory(self):
        return self.project_root / ".git"

    def daily_status(self, enabled=True):
        """Return cached status, checking the fixed remote once per date."""
        status = self.storage.status()
        if not enabled or not self.git_directory.is_dir():
            return {**status, "supported": False, "update_available": False}

        today = date.today().isoformat()
        if status["last_checked_date"] == today:
            return {**status, "supported": True}

        with self._check_lock:
            status = self.storage.status()
            if status["last_checked_date"] == today:
                return {**status, "supported": True}
            return self._perform_daily_check(today)

    def _perform_daily_check(self, today):
        """Perform the network comparison while the daily lock is held."""

        local_commit = ""
        remote_commit = ""
        error = ""
        try:
            branch = self._git("rev-parse", "--abbrev-ref", "HEAD").strip()
            if branch != UPDATE_BRANCH:
                raise ApplicationUpdateError(
                    f"Automatic updates require the {UPDATE_BRANCH} branch."
                )
            local_commit = self._git("rev-parse", "HEAD").strip()
            remote_output = self._run(
                "git",
                "ls-remote",
                UPDATE_REPOSITORY,
                f"refs/heads/{UPDATE_BRANCH}",
                timeout=10,
            )
            remote_commit = remote_output.split(maxsplit=1)[0].strip()
            if not COMMIT_PATTERN.fullmatch(local_commit):
                raise ApplicationUpdateError("The local Git commit is invalid.")
            if not COMMIT_PATTERN.fullmatch(remote_commit):
                raise ApplicationUpdateError("The remote Git commit is unavailable.")
        except (ApplicationUpdateError, OSError, subprocess.SubprocessError) as exc:
            error = str(exc)

        status = self.storage.record_check(
            today,
            local_commit,
            remote_commit,
            error,
        )
        return {**status, "supported": True}

    def cached_status(self):
        """Return status without contacting GitHub."""
        status = self.storage.status()
        return {
            **status,
            "supported": self.git_directory.is_dir(),
        }

    def start_update(self, *, dev_mode=False):
        """Validate the worktree and start the detached update helper."""
        if not self.git_directory.is_dir():
            raise ApplicationUpdateError(
                "Automatic updates require a Git clone of CairnMark."
            )
        status = self.storage.status()
        if status["update_in_progress"]:
            raise ApplicationUpdateError("An application update is already running.")
        if not status["update_available"]:
            raise ApplicationUpdateError("No application update is available.")

        branch = self._git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch != UPDATE_BRANCH:
            raise ApplicationUpdateError(
                f"Automatic updates require the {UPDATE_BRANCH} branch."
            )

        dirty = self._git("status", "--porcelain", "--untracked-files=no").strip()
        if dirty:
            raise ApplicationUpdateError(
                "Update blocked because tracked application files have local changes."
            )

        command = [
            sys.executable,
            "-m",
            "services.application_updater",
            "--parent-pid",
            str(os.getpid()),
            "--project-root",
            str(self.project_root),
            "--database",
            str(self.storage.store.path()),
        ]
        if dev_mode:
            command.append("--dev")

        popen_options = {
            "cwd": self.project_root,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            popen_options["creationflags"] = (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            popen_options["start_new_session"] = True
        try:
            subprocess.Popen(command, **popen_options)
        except OSError as error:
            raise ApplicationUpdateError(
                f"Could not start the application updater: {error}"
            ) from error
        self.storage.mark_started()
        return self.cached_status()

    def _git(self, *arguments, timeout=10):
        return self._run("git", *arguments, timeout=timeout)

    def _run(self, *command, timeout):
        options = {
            "cwd": self.project_root,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout,
            "check": False,
        }
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run(command, **options)
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip()
            raise ApplicationUpdateError(message or "Git command failed.")
        return completed.stdout


APPLICATION_UPDATES = ApplicationUpdateService()
