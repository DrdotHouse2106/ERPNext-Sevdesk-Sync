"""Tiny .env file loader (no third-party dependency required)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union


def load_env_file(path: Union[str, "os.PathLike[str]"], *, override: bool = False) -> None:
    """Load ``KEY=VALUE`` pairs from a .env-style file into ``os.environ``.

    Does nothing if the file does not exist. Existing environment variables
    are kept unless ``override=True``, so real environment variables always
    win over a checked-in ``.env`` file.
    """
    file_path = Path(path)
    if not file_path.is_file():
        return

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]

        key, sep, value = line.partition("=")
        if not sep:
            continue

        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        if not override and key in os.environ:
            continue
        os.environ[key] = value
