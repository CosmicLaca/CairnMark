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
    parser.add_argument("--dev", action="store_true")
    return parser.parse_args()


def hidden_process_options(*, new_process_group=False):
    """Return Windows flags that prevent helper console windows."""
    if os.name != "nt":
        return {}
    creationflags = subprocess.CREATE_NO_WINDOW
    if new_process_group:
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return {"creationflags": creationflags}


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
                **hidden_process_options(),
            )
    for _attempt in range(50):
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.1)


def git_pull(project_root, output):
    """Fast-forward the fixed public repository and return the new commit."""
    run_options = hidden_process_options()
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
        **run_options,
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
        **run_options,
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


def restart(project_root, dev_mode, output):
    """Start CairnMark again through its platform startup script."""
    if os.name == "nt":
        start_script = project_root / "run.bat"
        command = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(start_script),
        ]
    else:
        start_script = project_root / "run.sh"
        command = [str(start_script)]
    if not start_script.is_file():
        raise OSError(f"Startup script not found: {start_script}")
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
        options.update(hidden_process_options(new_process_group=True))
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


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
            server_process = restart(
                project_root,
                arguments.dev,
                output,
            )
        except OSError as exc:
            restart_error = f"Could not restart CairnMark: {exc}"
            output.write(f"{restart_error}\n")
            try:
                record_result(database, error=restart_error)
            except sqlite3.Error as database_error:
                output.write(f"Could not save restart failure: {database_error}\n")
            output.flush()
            return 1
        time.sleep(1)
        return_code = server_process.poll()
        if return_code is not None:
            restart_error = (
                "Could not restart CairnMark: the startup script exited "
                f"with status {return_code}."
            )
            output.write(f"{restart_error}\n")
            try:
                record_result(database, error=restart_error)
            except sqlite3.Error as database_error:
                output.write(f"Could not save restart failure: {database_error}\n")
            output.flush()
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
