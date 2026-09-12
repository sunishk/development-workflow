import os
import shutil
import subprocess
from pathlib import Path


_BATCH_SUFFIXES = {".bat", ".cmd"}


def _is_windows() -> bool:
    return os.name == "nt"


def prepare_command(command: list[str], cwd: Path | str | None = None) -> list[str]:
    """Prepare a command for safe shell-free execution on macOS/Linux and Windows."""
    if not command or any(not part for part in command):
        raise ValueError("Command must contain non-empty arguments")

    prepared = list(command)
    executable = prepared[0]
    working_dir = Path(cwd).resolve() if cwd is not None else None

    executable_path = Path(executable)
    has_path_separator = "/" in executable or "\\" in executable

    if working_dir is not None and not executable_path.is_absolute():
        candidate = (working_dir / executable_path).resolve()
        if candidate.exists():
            prepared[0] = str(candidate)
        elif not has_path_separator:
            resolved = shutil.which(executable)
            if resolved:
                prepared[0] = resolved
    elif not has_path_separator:
        resolved = shutil.which(executable)
        if resolved:
            prepared[0] = resolved

    if _is_windows() and Path(prepared[0]).suffix.lower() in _BATCH_SUFFIXES:
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return [comspec, "/d", "/s", "/c", subprocess.list2cmdline(prepared)]

    return prepared
