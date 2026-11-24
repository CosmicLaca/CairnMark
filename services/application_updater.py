"""Detached helper that replaces files and restarts the local application."""

import argparse
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import date
from pathlib import Path


UPDATE_REPOSITORY = "https://github.com/CosmicLaca/CairnMark.git"
UPDATE_BRANCH = "main"


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--dev", action="store_true")
    return parser.parse_args()


def stop_parent(pid):
    """Stop the server after its update response has reached the browser."""
    time.sleep(1.25)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=False,
                capture_output=True,
            )
    for _attempt in range(50):
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.1)


def git_pull(project_root, output):
    """Fast-forward the fixed public repository and return the new commit."""
    completed = subprocess.run(
        [
            "git",
            "pull",
            "--ff-only",
            UPDATE_REPOSITORY,
            UPDATE_BRANCH,
        ],
        cwd=project_root,
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Git pull failed. See instance/application-update.log.")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if commit.returncode != 0:
        raise RuntimeError("The updated Git commit could not be read.")
    return commit.stdout.strip()


def record_result(database, *, commit="", error=""):
    """Record updater completion without importing potentially replaced code."""
    with sqlite3.connect(database, timeout=10) as connection:
        if error:
            connection.execute(
                """
                UPDATE application_updates
                SET update_in_progress = 0,
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (error,),
            )
        else:
            connection.execute(
                """
                UPDATE application_updates
                SET last_checked_date = ?,
                    local_commit = ?,
                    remote_commit = ?,
                    update_available = 0,
                    update_in_progress = 0,
                    last_error = '',
                    last_update_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (date.today().isoformat(), commit, commit),
            )


def restart(project_root, python_executable, dev_mode, output):
    """Start CairnMark again using the existing Python environment."""
    command = [python_executable, "app.py"]
    if dev_mode:
        command.append("--dev")
    options = {
        "cwd": project_root,
        "stdin": subprocess.DEVNULL,
        "stdout": output,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        options["start_new_session"] = True
    subprocess.Popen(command, **options)


def main():
    arguments = parse_arguments()
    project_root = Path(arguments.project_root).resolve()
    database = Path(arguments.database).resolve()
    log_path = project_root / "instance" / "application-update.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stop_parent(arguments.parent_pid)
    error = ""
    commit = ""
    with log_path.open("a", encoding="utf-8") as output:
        output.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Update started\n")
        output.flush()
        try:
            commit = git_pull(project_root, output)
        except Exception as exc:  # noqa: BLE001 - persist helper failures
            error = str(exc)
            output.write(f"Update failed: {error}\n")
        try:
            record_result(database, commit=commit, error=error)
        except sqlite3.Error as exc:
            output.write(f"Could not save update status: {exc}\n")
        output.flush()
        try:
            restart(
                project_root,
                arguments.python,
                arguments.dev,
                output,
            )
        except OSError as exc:
            output.write(f"Could not restart CairnMark: {exc}\n")
            output.flush()
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
